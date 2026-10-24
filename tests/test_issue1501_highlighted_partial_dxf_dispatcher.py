# -*- coding: utf-8 -*-
"""#1501 real Receiving selection -> verified inner-door partial DXF dispatcher.

These tests exercise actual staging/publishing and scope ownership. Manufacturing
geometry/source revalidation itself is already covered by #1635/#1643 writer
tests; here the writer port is replaced with a deterministic typed fake.
"""
from pathlib import Path
import os

import pytest

from ae_engine.receiving_nfb_export_manifest import (
    NfbManifestRow, NfbPartialExportManifest, INNER_DOOR,
)
from ae_engine.receiving_nfb_part_readiness import NfbPhysicalScope, READY
from gui_modules.application import receiving_nfb_partial_batch_dispatcher as batch


def _ports(*, fail_bay=None, changed_source=False):
    calls = []
    def scope(index):
        return NfbPhysicalScope(
            "set-A", f"bay-{index}", f"v{index}", True, f"part-{index}",
        )
    def live_manifest(index):
        physical = scope(index)
        part = NfbManifestRow(
            *physical.identity, physical.inner_door_part_id,
            INNER_DOOR, READY, (), 1, True,
        )
        return NfbPartialExportManifest(
            physical, (part,), ("PAD_EAR_DEFERRED",), True, False,
        )
    def report(set_index, bay_index):
        assert set_index == 0
        if changed_source and bay_index == 1:
            return {"status":"BLOCKED","reason":"source SHA stale"}
        return dict(live_manifest(bay_index).report(),status="PARTIAL_ONLY")
    def export(set_index, bay_index, output_path):
        calls.append((set_index, bay_index, output_path))
        if bay_index == fail_bay:
            raise ValueError("real DXF source changed")
        Path(output_path).write_bytes(b"0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n")
        return str(output_path), live_manifest(bay_index)
    return {"manifest":report,"partial_export":export}, calls


def test_highlighted_bays_write_only_verified_partial_dxfs_atomically(tmp_path):
    ports,calls=_ports()
    done=batch.export_highlighted_nfb_inner_doors(
        ports,set_index=0,bay_indices=(0,1),output_directory=tmp_path,
    )
    assert len(done)==2
    assert len(calls)==2
    assert [Path(p).name for p,_ in done]==[
        "nfb_set1_bay1_inner_partial.dxf",
        "nfb_set1_bay2_inner_partial.dxf",
    ]
    assert all(Path(p).is_file() for p,_ in done)
    assert [m.scope.bay_id for _,m in done]==["bay-0","bay-1"]
    assert [m.scope.version_id for _,m in done]==["v0","v1"]
    assert all(m.partial_only for _,m in done)
    assert not list(tmp_path.glob(".whd-nfb-partial-stage-*"))


def test_one_bad_bay_leaves_no_partial_files_and_no_skipped_quantity(tmp_path):
    ports,calls=_ports(fail_bay=1)
    with pytest.raises(ValueError,match="real DXF source changed"):
        batch.export_highlighted_nfb_inner_doors(
            ports,set_index=0,bay_indices=(0,1),output_directory=tmp_path,
        )
    assert len(calls)==2
    assert list(tmp_path.iterdir())==[]


def test_stale_source_preflight_blocks_before_first_writer(tmp_path):
    ports,calls=_ports(changed_source=True)
    with pytest.raises(ValueError,match="fresh submitted DXF proof"):
        batch.export_highlighted_nfb_inner_doors(
            ports,set_index=0,bay_indices=(0,1),output_directory=tmp_path,
        )
    assert calls==[]
    assert list(tmp_path.iterdir())==[]


def test_duplicate_empty_and_invalid_highlights_cannot_export(tmp_path):
    ports,calls=_ports()
    for values in ((),(0,0),(True,),(-1,)):
        with pytest.raises(ValueError,match="unique highlighted"):
            batch.export_highlighted_nfb_inner_doors(
                ports,set_index=0,bay_indices=values,output_directory=tmp_path,
            )
    with pytest.raises(ValueError,match="Set index"):
        batch.export_highlighted_nfb_inner_doors(
            ports,set_index=True,bay_indices=(0,),output_directory=tmp_path,
        )
    assert calls==[]


def test_existing_output_never_overwritten_even_after_source_validation(tmp_path):
    ports,calls=_ports()
    original=tmp_path/"nfb_set1_bay1_inner_partial.dxf"
    original.write_bytes(b"OWNER ORIGINAL")
    with pytest.raises(FileExistsError,match="already exists"):
        batch.export_highlighted_nfb_inner_doors(
            ports,set_index=0,bay_indices=(0,1),output_directory=tmp_path,
        )
    assert original.read_bytes()==b"OWNER ORIGINAL"
    assert calls==[]


def test_commit_io_failure_rolls_back_all_published_parts(tmp_path,monkeypatch):
    ports,calls=_ports()
    real_link=os.link
    linked=[]
    def broken_link(src,dst):
        if linked:
            raise OSError("publication stopped")
        real_link(src,dst)
        linked.append(dst)
    monkeypatch.setattr(batch.os,"link",broken_link)
    with pytest.raises(OSError,match="publication stopped"):
        batch.export_highlighted_nfb_inner_doors(
            ports,set_index=0,bay_indices=(0,1),output_directory=tmp_path,
        )
    assert len(calls)==2
    assert list(tmp_path.iterdir())==[]


def test_stale_or_untyped_writer_result_does_not_publish(tmp_path):
    ports,calls=_ports()
    def invalid_writer(si,bi,path):
        Path(path).write_bytes(b"not a validated release")
        return str(path), {"may_export":True,"whole_ready":True}
    ports["partial_export"]=invalid_writer
    with pytest.raises(ValueError,match="typed manifest"):
        batch.export_highlighted_nfb_inner_doors(
            ports,set_index=0,bay_indices=(0,),output_directory=tmp_path,
        )
    assert list(tmp_path.iterdir())==[]


def test_explicit_partial_selection_exports_ready_bay_and_reports_held_source(tmp_path):
    import json
    ports, calls = _ports(changed_source=True)
    assert batch.require_highlighted_nfb_inner_doors(
        ports, 0, (0, 1), allow_held=True,
    ) == (0,)
    done = batch.export_highlighted_nfb_inner_doors(
        ports, set_index=0, bay_indices=(0, 1), output_directory=tmp_path,
        allow_held=True,
    )
    assert len(done) == 1 and [call[1] for call in calls] == [0]
    report = json.loads((tmp_path / "nfb_set1_partial_manifest.json").read_text())
    assert report["actual_export_count"] == 1
    assert report["whole_cabinet_complete"] is False
    assert report["not_exported_bays"][0]["bay_index"] == 1
    assert report["not_exported_bays"][0]["reason"] == "source SHA stale"
    assert not (tmp_path / "nfb_set1_bay2_inner_partial.dxf").exists()


def test_partial_manifest_publication_failure_rolls_back_dxfs(tmp_path, monkeypatch):
    ports, calls = _ports(changed_source=True)
    original = os.link
    def fail_report(source, destination):
        if Path(destination).suffix == ".json":
            raise OSError("manifest publication failed")
        return original(source, destination)
    monkeypatch.setattr(batch.os, "link", fail_report)
    with pytest.raises(OSError, match="manifest publication failed"):
        batch.export_highlighted_nfb_inner_doors(
            ports, set_index=0, bay_indices=(0, 1), output_directory=tmp_path,
            allow_held=True,
        )
    assert not list(tmp_path.iterdir())


def test_writer_cannot_substitute_another_bay_scope(tmp_path):
    ports, calls = _ports()
    original = ports["partial_export"]
    def swapped(si, bi, path):
        return original(si, 1, path)
    ports["partial_export"] = swapped
    with pytest.raises(ValueError, match="ownership changed"):
        batch.export_highlighted_nfb_inner_doors(
            ports, set_index=0, bay_indices=(0,), output_directory=tmp_path,
            allow_held=True,
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("allow_held", (False, True))
def test_same_bay_writer_cannot_substitute_inner_door_part(tmp_path, allow_held):
    """Same Set/Bay/version may not conceal another physical door from writer."""
    from dataclasses import replace

    ports, calls = _ports()
    original = ports["partial_export"]

    def wrong_physical_owner(si, bi, path):
        written, manifest = original(si, bi, path)
        other = manifest.scope.inner_door_part_id + "-other-panel"
        scope = replace(manifest.scope, inner_door_part_id=other)
        rows = tuple(
            replace(row, part_id=other) if row.role == INNER_DOOR else row
            for row in manifest.rows
        )
        return written, replace(manifest, scope=scope, rows=rows)

    ports["partial_export"] = wrong_physical_owner
    with pytest.raises(ValueError, match="physical inner-door"):
        batch.export_highlighted_nfb_inner_doors(
            ports, set_index=0, bay_indices=(0,),
            output_directory=tmp_path, allow_held=allow_held,
        )
    assert len(calls) == 1
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("allow_held", (False, True))
def test_partial_door_export_counts_only_actual_selected_sheet(tmp_path, allow_held):
    """Other independently allowed physical pieces are not this door DXF's Q."""
    import json
    from dataclasses import replace
    from ae_engine.receiving_nfb_export_manifest import NfbManifestRow, OTHER
    from ae_engine.receiving_nfb_part_readiness import UNAFFECTED

    ports, calls = _ports()
    original_view = ports["manifest"]
    original_writer = ports["partial_export"]

    def additional_row(identity):
        return NfbManifestRow(
            *identity, "side-panel", OTHER, UNAFFECTED, (), 3, True,
        )

    def view(si, bi):
        existing = original_view(si, bi)
        extra = additional_row((existing["set_id"], existing["bay_id"], existing["version_id"]))
        return {
            **existing,
            "rows": [*existing["rows"], {
                "set_id": extra.set_id, "bay_id": extra.bay_id,
                "version_id": extra.version_id, "part_id": extra.part_id,
                "role": extra.role, "status": extra.status,
                "reasons": list(extra.reasons), "actual_count": extra.actual_count,
                "may_export": True,
            }],
            "actual_export_count": 4,
        }

    def writer(si, bi, path):
        written, manifest = original_writer(si, bi, path)
        extra = additional_row(manifest.scope.identity)
        return written, replace(manifest, rows=manifest.rows + (extra,))

    ports["manifest"] = view
    ports["partial_export"] = writer
    done = batch.export_highlighted_nfb_inner_doors(
        ports, set_index=0, bay_indices=(0,),
        output_directory=tmp_path, allow_held=allow_held,
    )
    assert len(calls) == 1 and len(done) == 1
    assert done[0][1].actual_export_count == 4  # eligible, NOT exported Q
    assert len(list(tmp_path.glob("*.dxf"))) == 1
    assert Path(done[0][0]).is_file()
    if allow_held:
        report = json.loads((tmp_path / "nfb_set1_partial_manifest.json").read_text())
        assert report["actual_export_count"] == 1
        assert report["whole_cabinet_complete"] is False
        assert report["exported"][0]["actual_export_count"] == 1
        assert report["exported"][0]["eligible_physical_piece_count"] == 4
        assert report["exported"][0]["actually_emitted_part_ids"] == ["part-0"]


@pytest.mark.parametrize("corruption", (
    "status", "duplicate_physical_id", "wrong_role", "boolean_count",
))
def test_partial_writer_rejects_forged_door_row_after_preflight(
    tmp_path, corruption,
):
    """A post-preflight typed manifest cannot reclassify a real door owner."""
    from dataclasses import replace
    from ae_engine.receiving_nfb_export_manifest import OTHER
    from ae_engine.receiving_nfb_part_readiness import BLOCKED

    ports, calls = _ports()
    original = ports["partial_export"]

    def corrupted(si, bi, path):
        written, manifest = original(si, bi, path)
        door = manifest.rows[0]
        if corruption == "status":
            rows = (replace(door, status=BLOCKED, may_export=True),)
        elif corruption == "duplicate_physical_id":
            rows = (door, replace(door, role=OTHER, actual_count=2))
        elif corruption == "wrong_role":
            rows = (replace(door, role=OTHER),)
        else:
            rows = (replace(door, actual_count=True),)
        return written, replace(manifest, rows=rows)

    ports["partial_export"] = corrupted
    with pytest.raises(ValueError, match="manufactured part count invalid"):
        batch.export_highlighted_nfb_inner_doors(
            ports, set_index=0, bay_indices=(0,), output_directory=tmp_path,
        )
    assert len(calls) == 1
    assert not list(tmp_path.iterdir())
