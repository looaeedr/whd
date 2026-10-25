# -*- coding: utf-8 -*-
"""#1503: independent LEFT/RIGHT DXF CHECK-only readback, never MFG release."""
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine.receiving_fixed_plate_side_check_dxf import (
    export_receiving_ear_side_check_only_dxf,
)
from tests.test_issue1503_real_ear_side_weld_skin_mating import _real_world
from tests.test_issue1050_receiving_mother_plate_marking import (
    _full_receiving_geometry,
)
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


def _actual(factory):
    snapshot, _world = _real_world(factory)
    return snapshot, _full_receiving_geometry(snapshot)


def _export(snapshot, geometry, directory, *, overwrite=False):
    return export_receiving_ear_side_check_only_dxf(
        snapshot, geometry, directory,
        dimensions=(800., 1600., 350.), sheet_thickness=2.,
        overwrite=overwrite,
    )


@pytest.mark.parametrize("factory,part_count,lines", (
    (_assembled, 2, 6),
    (_two_tier, 4, 12),
))
def test_real_w800_signed_ear_skin_side_uv_saved_dxf_matches_exact_lines(
    tmp_path, factory, part_count, lines,
):
    snapshot, geometry = _actual(factory)
    before = tuple(tuple(piece.render_data.scene.primitives)
        for piece in geometry.part("box_body").render_data.pieces)
    receipt = _export(snapshot, geometry, tmp_path)
    assert receipt.status == "RECEIVING_EAR_SIDE_CHECK_DXF_ONLY"
    assert receipt.saved_dxf_roundtrip_verified
    assert not receipt.manufacturing_ready
    assert not receipt.welding_workmanship_certified
    assert len(receipt.part_ids) == part_count
    assert receipt.marking_lines_verified == lines
    assert receipt.physical_contact_area_mm2 == pytest.approx(part_count * 5632.)
    assert {owner for owner, _ in receipt.output_paths} == {
        "box_body:left_side", "box_body:right_side",
    }
    for owner, filepath in receipt.output_paths:
        file = Path(filepath)
        assert file.exists()
        assert "CHECK_ONLY" in file.name
        doc = ezdxf.readfile(file)
        marks = [
            e for e in doc.modelspace()
            if e.dxftype() == "LINE" and e.dxf.layer.upper() == "MARKING"
        ]
        assert len(marks) >= lines//2
        assert len(doc.modelspace()) > len(marks)
    after = tuple(tuple(piece.render_data.scene.primitives)
        for piece in geometry.part("box_body").render_data.pieces)
    assert before == after


def test_export_refuses_unsubmitted_or_stale_input_before_creating_any_dir(tmp_path):
    snap, geom = _actual(_assembled)
    output = tmp_path / "never-created"
    with pytest.raises(ValueError, match="MATCHING_SUBMITTED"):
        _export({**snap, "nfb_config_submitted": False}, geom, output)
    assert not output.exists()
    with pytest.raises(ValueError, match="MATCHING_SUBMITTED"):
        export_receiving_ear_side_check_only_dxf(
            snap, geom, output,
            dimensions=(750., 1600., 350.), sheet_thickness=2.,
        )
    assert not output.exists()


def test_both_files_atomic_and_no_overwrite_by_default(tmp_path):
    snap, geom = _actual(_assembled)
    first = _export(snap, geom, tmp_path)
    original = {owner: Path(path).read_bytes() for owner, path in first.output_paths}
    with pytest.raises(FileExistsError, match="CHECK_ONLY"):
        _export(snap, geom, tmp_path)
    assert all(Path(path).read_bytes() == original[owner] for owner,path in first.output_paths)
    second = _export(snap, geom, tmp_path, overwrite=True)
    assert set(dict(first.output_paths)) == set(dict(second.output_paths))
    assert all(Path(path).exists() for _, path in second.output_paths)


def test_reopen_failure_cannot_publish_only_one_side(tmp_path, monkeypatch):
    import ae_engine.receiving_fixed_plate_side_check_dxf as check
    snap, geom = _actual(_assembled)
    real_verify = check.verify_saved_part_render_data_dxf
    calls = []
    def fail_right(render, path, **kwargs):
        calls.append(str(path))
        if "RIGHT_SIDE" in str(path):
            return SimpleNamespace(ok=False)
        return real_verify(render, path, **kwargs)
    monkeypatch.setattr(check, "verify_saved_part_render_data_dxf", fail_right)
    with pytest.raises(ValueError, match="ROUNDTRIP_FAILED"):
        _export(snap, geom, tmp_path)
    assert len(calls) == 2
    assert not list(tmp_path.glob("*.dxf"))
    assert not list(tmp_path.glob(".whd-ear-check-stage-*"))


def test_extra_or_wrong_saved_mark_coordinates_fail_even_when_dxf_openable(
    tmp_path, monkeypatch,
):
    import ae_engine.receiving_fixed_plate_side_check_dxf as check
    snap, geom = _actual(_assembled)
    real_save = check.save_part_render_data_dxf
    def corrupt_one_mark(render, filepath, *, overwrite=False):
        result = real_save(render, filepath, overwrite=overwrite)
        file = ezdxf.readfile(filepath)
        mark = next(e for e in file.modelspace()
                    if e.dxftype() == "LINE" and e.dxf.layer.upper() == "MARKING")
        mark.dxf.start = (
            float(mark.dxf.start.x) + 3.,
            float(mark.dxf.start.y),
            float(mark.dxf.start.z),
        )
        file.saveas(filepath)
        return result
    # Force the independent line-coordinate readback to carry the tamper
    # failure even if generic DXF acceptance otherwise returns OK.
    monkeypatch.setattr(check, "save_part_render_data_dxf", corrupt_one_mark)
    monkeypatch.setattr(
        check, "verify_saved_part_render_data_dxf",
        lambda *args, **kwargs: SimpleNamespace(ok=True),
    )
    with pytest.raises(ValueError, match="SAVED_MARKING_UV_LINE_MISSING"):
        _export(snap, geom, tmp_path)
    assert not list(tmp_path.glob("*.dxf"))
