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
