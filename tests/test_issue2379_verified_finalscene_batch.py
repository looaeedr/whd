# -*- coding: utf-8 -*-
"""#2379 actual WHD FinalScene -> DXF -> independent reload -> atomic commit.

Internal manufacturing boundary only. Not a public Worker export capability.
"""
from pathlib import Path
import ezdxf
import pytest
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import DrawingScene, PolylinePrimitive, LinePrimitive, CirclePrimitive
from ae_engine.sheetmetal_geometry import Vec2


def _canonical_render():
    scene = DrawingScene()
    scene.add(PolylinePrimitive(
        points=(Vec2(0, 0), Vec2(100, 0), Vec2(100, 60), Vec2(0, 60)),
        layer="CUTTING", closed=True))
    scene.add(LinePrimitive(Vec2(20, 0), Vec2(20, 60), "BEND"))
    scene.add(CirclePrimitive(Vec2(50, 30), 5.0, "CUTTING"))
    return api.PartRenderData(
        scene=scene,
        material=api.material_polygon_from_final_scene(scene),
        fold_guides=api.fold_guides_from_final_scene(scene),
    )


def _rows(count):
    return [(f"whd-door-{i:02d}", _canonical_render()) for i in range(count)]


def test_20_real_dxf_parts_are_saved_reloaded_verified_before_commit(tmp_path):
    target = tmp_path / "manufacturing"
    guards = []
    result = api.save_verified_final_scene_batch_dxf(
        _rows(20), target, pre_commit_guard=lambda: guards.append("checked"))
    assert len(result) == 20
    assert guards == ["checked", "checked"]
    assert {p.name for p in target.glob("*.dxf")} == {
        f"whd-door-{i:02d}.dxf" for i in range(20)}
    for path in result.values():
        doc = ezdxf.readfile(path)
        layers = [e.dxf.layer for e in doc.modelspace()]
        assert "CUTTING" in layers and "BEND" in layers
        assert len(list(doc.modelspace().query('CIRCLE[layer=="CUTTING"]'))) == 1
        assert api.verify_saved_part_render_data_dxf(_canonical_render(), path).ok


def test_stale_guard_after_reloading_keeps_every_old_dxf(tmp_path):
    target = tmp_path / "manufacturing"
    target.mkdir()
    old = {f"whd-door-{i:02d}.dxf": b"old-production-bytes" for i in range(2)}
    for name, data in old.items():
        (target / name).write_bytes(data)
    calls = []
    def guard():
        calls.append(True)
        if len(calls) == 2:
            raise ValueError("WHD_PREPARE_STALE")
    with pytest.raises(ValueError, match="WHD_PREPARE_STALE"):
        api.save_verified_final_scene_batch_dxf(
            _rows(2), target, pre_commit_guard=guard, overwrite=True)
    assert len(calls) == 2
    assert {p.name: p.read_bytes() for p in target.glob("*.dxf")} == old
    assert not list(target.glob(".whd-dxf-stage-*"))


def test_tampered_second_staged_dxf_fails_with_no_partial_commit(tmp_path, monkeypatch):
    from ae_engine import manufacturing_verification
    target = tmp_path / "manufacturing"
    target.mkdir()
    previous = target / "whd-door-00.dxf"
    previous.write_bytes(b"previous-customer-file")
    real = manufacturing_verification.verify_saved_part_render_data_dxf
    called = []
    def corrupt_second(render, staged):
        called.append(staged)
        if len(called) == 2:
            doc = ezdxf.readfile(staged)
            circles = list(doc.modelspace().query('CIRCLE[layer=="CUTTING"]'))
            assert circles
            doc.modelspace().delete_entity(circles[0])
            doc.saveas(staged)
        return real(render, staged)
    monkeypatch.setattr(manufacturing_verification, "verify_saved_part_render_data_dxf", corrupt_second)
    with pytest.raises(ValueError, match="WHD_STAGED_DXF_ROUNDTRIP_FAILED"):
        api.save_verified_final_scene_batch_dxf(
            _rows(2), target, pre_commit_guard=lambda: None, overwrite=True)
    assert len(called) == 2
    assert previous.read_bytes() == b"previous-customer-file"
    assert {p.name for p in target.glob("*.dxf")} == {"whd-door-00.dxf"}


@pytest.mark.parametrize("bad", [
    "empty", "oversize", "traversal", "duplicate", "win_colon",
    "win_reserved", "win_reserved_dot", "win_com", "win_lpt", "casefold_duplicate",
])
def test_invalid_inventory_cannot_make_output_directory(tmp_path, bad):
    target = tmp_path / "manufacturing"
    if bad == "empty":
        records = []
    elif bad == "oversize":
        records = _rows(21)
    elif bad == "traversal":
        records = [("../escape", _canonical_render())]
    elif bad == "duplicate":
        records = [("part", _canonical_render()), ("part", _canonical_render())]
    elif bad == "win_colon":
        records = [("invalid:name", _canonical_render())]
    elif bad == "win_reserved":
        records = [("CON", _canonical_render())]
    elif bad == "win_reserved_dot":
        records = [("nul.backup", _canonical_render())]
    elif bad == "win_com":
        records = [("Com1", _canonical_render())]
    elif bad == "win_lpt":
        records = [("lpt9", _canonical_render())]
    else:
        records = [("Door", _canonical_render()), ("door", _canonical_render())]
    with pytest.raises(ValueError):
        api.save_verified_final_scene_batch_dxf(
            records, target, pre_commit_guard=lambda: None)
    assert not target.exists()


def test_missing_trusted_guard_cannot_write(tmp_path):
    target = tmp_path / "out"
    with pytest.raises(ValueError, match="WHD_PRECOMMIT_GUARD_REQUIRED"):
        api.save_verified_final_scene_batch_dxf(
            _rows(1), target, pre_commit_guard=None)
    assert not target.exists()


def test_real_wHD_door_finalscene_staged_roundtrip(tmp_path):
    from ae_engine.contracts import DoorPartSpec, ManufacturingContext
    resource_root = Path(__file__).resolve().parents[1]
    spec = DoorPartSpec(
        width=500, height=600, thickness=2, frame_width=25, model_name="金庫型")
    render = api.build_part_render_data(
        spec, ManufacturingContext(resource_root=resource_root))
    path = api.save_verified_final_scene_batch_dxf(
        [("whd-real-door", render)], tmp_path / "verified",
        pre_commit_guard=lambda: None)["whd-real-door"]
    assert api.verify_saved_part_render_data_dxf(render, path).ok
