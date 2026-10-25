# -*- coding: utf-8 -*-
"""#1503: genuine physical SIDE-only manufacturing DXF marking source receipts."""
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine.receiving_ear_side_manufacturing_marking import (
    export_receiving_ear_side_manufacturing_marking_dxf,
)
from tests.test_issue1503_ear_side_check_only_dxf import _actual
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


def _make(snapshot, geometry, folder, *, overwrite=False):
    return export_receiving_ear_side_manufacturing_marking_dxf(
        snapshot, geometry, folder,
        dimensions=(800., 1600., 350.),
        sheet_thickness=2., overwrite=overwrite,
    )


def _marks(filename):
    result = []
    for e in ezdxf.readfile(filename).modelspace():
        if e.dxftype() == "LINE" and e.dxf.layer.upper() == "MARKING":
            p1 = (round(e.dxf.start.x, 6), round(e.dxf.start.y, 6))
            p2 = (round(e.dxf.end.x, 6), round(e.dxf.end.y, 6))
            result.append(tuple(sorted((p1, p2))))
    return tuple(sorted(result))


@pytest.mark.parametrize("factory,count", ((_assembled, 2), (_two_tier, 4)))
def test_real_side_only_mfg_dxf_contains_genuine_uv_marks_and_source_cutting(
    tmp_path, factory, count,
):
    snap, geom = _actual(factory)
    original = tuple(tuple(piece.render_data.scene.primitives)
        for piece in geom.part("box_body").render_data.pieces)
    exported = _make(snap, geom, tmp_path)
    assert exported.status == "EAR_SIDE_ONLY_MFG_MARKING_VERIFIED"
    assert exported.side_only_manufacturing_marking_verified
    assert not exported.whole_cabinet_manufacturing_ready
    assert not exported.welding_workmanship_certified
    assert exported.marking_lines_verified == count * 3
    assert exported.material_skin_contact_area_mm2 == pytest.approx(5632.*count)
    assert len(exported.physical_ear_ids) == count
    paths = dict(exported.output_paths)
    assert set(paths) == {"box_body:left_side", "box_body:right_side"}
    assert {Path(f).name for f in paths.values()} == {
        "box_body__left_side.dxf", "box_body__right_side.dxf",
    }
    assert len(list(tmp_path.glob("*.dxf"))) == 2
    for side, filename in paths.items():
        scene = ezdxf.readfile(filename).modelspace()
        assert len(_marks(filename)) >= 3 * count//2
        assert any(entity.dxftype() != "LINE" or entity.dxf.layer != "MARKING"
                   for entity in scene)
        assert "CHECK_ONLY" not in filename
    after = tuple(tuple(piece.render_data.scene.primitives)
        for piece in geom.part("box_body").render_data.pieces)
    assert after == original


@pytest.mark.parametrize("factory", (_assembled, _two_tier))
def test_part_only_production_marks_match_already_verified_check_dxf(
    tmp_path, factory,
):
    from ae_engine.receiving_fixed_plate_side_check_dxf import (
        export_receiving_ear_side_check_only_dxf,
    )
    snap, geom = _actual(factory)
    check = export_receiving_ear_side_check_only_dxf(
        snap, geom, tmp_path/"check", dimensions=(800,1600,350), sheet_thickness=2.,
    )
    formal = _make(snap, geom, tmp_path/"manufacturing")
    assert {_owner: _marks(path) for _owner,path in formal.output_paths} == {
        _owner: _marks(path) for _owner,path in check.output_paths
    }
    assert not list((tmp_path/"manufacturing").glob("*CHECK_ONLY*"))


def test_missing_approved_physical_data_blocks_without_creating_target(tmp_path):
    snap, geom = _actual(_assembled)
    target = tmp_path/"must-stay-absent"
    with pytest.raises(ValueError, match="REQUIRES_CURRENT_MATCHING_SUBMITTED"):
        _make({**snap,"nfb_config_submitted":False}, geom, target)
    assert not target.exists()
    with pytest.raises(ValueError, match="QUANTITY_REQUIRES_PER_VERSION"):
        _make({**snap,"active_mode":"quantity"}, geom, target)
    assert not target.exists()
    with pytest.raises(ValueError, match="REQUIRES_CURRENT_MATCHING_SUBMITTED"):
        export_receiving_ear_side_manufacturing_marking_dxf(
            snap, geom, target, dimensions=(750,1600,350), sheet_thickness=2.,
        )
    assert not target.exists()


def test_both_real_side_outputs_commit_atomically_and_never_overwrite_default(tmp_path):
    snap, geom = _actual(_assembled)
    first = _make(snap, geom, tmp_path)
    originals = {side:Path(path).read_bytes() for side,path in first.output_paths}
    with pytest.raises(FileExistsError):
        _make(snap, geom, tmp_path)
    assert all(Path(p).read_bytes() == originals[k] for k,p in first.output_paths)
    after = _make(snap, geom, tmp_path, overwrite=True)
    assert set(dict(after.output_paths)) == set(originals)


def test_bad_saved_mark_coordinate_rejects_both_production_sides(tmp_path, monkeypatch):
    import ae_engine.receiving_ear_side_manufacturing_marking as module
    real_save = module.save_part_render_data_dxf
    def tamper(render, path, *, overwrite=False):
        result = real_save(render, path, overwrite=overwrite)
        doc = ezdxf.readfile(result)
        e = next(x for x in doc.modelspace()
                 if x.dxftype()=="LINE" and x.dxf.layer.upper()=="MARKING")
        e.dxf.end = (float(e.dxf.end.x)+7.,float(e.dxf.end.y),float(e.dxf.end.z))
        doc.saveas(result)
        return result
    monkeypatch.setattr(module, "save_part_render_data_dxf", tamper)
    monkeypatch.setattr(module, "verify_saved_part_render_data_dxf",
                        lambda *args,**kwargs: SimpleNamespace(ok=True))
    snap,geom=_actual(_assembled)
    with pytest.raises(ValueError, match="SAVED_MARKING_UV_LINE_MISSING"):
        _make(snap,geom,tmp_path)
    assert not list(tmp_path.glob("*.dxf"))
