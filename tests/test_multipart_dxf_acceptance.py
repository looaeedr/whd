# -*- coding: utf-8 -*-
from types import SimpleNamespace

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
from ae_engine.sheetmetal_drawing import DrawingScene, PolylinePrimitive
from ae_engine.sheetmetal_geometry import Vec2


def _render(width=100.0, height=60.0):
    scene = DrawingScene()
    scene.add(PolylinePrimitive(
        points=(Vec2(0, 0), Vec2(width, 0), Vec2(width, height), Vec2(0, height)),
        layer="CUTTING",
        closed=True,
    ))
    return api.PartRenderData(
        scene=scene,
        material=api.material_polygon_from_final_scene(scene),
        fold_guides=(),
    )


def _resolved():
    left = SimpleNamespace(key="left_side", role="left_side", render_data=_render(20, 60))
    back = SimpleNamespace(key="back", role="back", render_data=_render(60, 60))
    right = SimpleNamespace(key="right_side", role="right_side", render_data=_render(20, 60))
    box = SimpleNamespace(pieces=(left, back, right))
    return ResolvedManufacturingGeometry(parts=(
        ResolvedManufacturingPart("box_body", box),
        ResolvedManufacturingPart("door_c1_r1", _render(80, 50)),
        ResolvedManufacturingPart("box_body:divider:0", _render(40, 50)),
    ))


def _group_verifier():
    verifier = getattr(api, "verify_saved_resolved_manufacturing_geometry_dxf", None)
    assert callable(verifier), (
        "R4: missing physical-part DXF acceptance seam; "
        "resolved multipart/dynamic exports cannot currently be reopened and checked as one set"
    )
    return verifier


def test_resolved_export_uses_stable_physical_piece_ids(tmp_path):
    outputs = api.save_resolved_manufacturing_geometry_dxf(
        _resolved(), tmp_path, overwrite=True
    )

    assert set(outputs) == {
        "box_body:left_side",
        "box_body:back",
        "box_body:right_side",
        "door_c1_r1",
        "box_body:divider:0",
    }
    assert {p.name for p in tmp_path.glob("*.dxf")} == {
        "box_body__left_side.dxf",
        "box_body__back.dxf",
        "box_body__right_side.dxf",
        "door_c1_r1.dxf",
        "box_body_divider_0.dxf",
    }


def test_resolved_saved_dxf_acceptance_reopens_every_physical_part(tmp_path):
    resolved = _resolved()
    api.save_resolved_manufacturing_geometry_dxf(resolved, tmp_path, overwrite=True)

    result = _group_verifier()(resolved, tmp_path)

    assert result.ok is True
    assert result.issues == ()
    assert set(result.part_results) == {
        "box_body:left_side",
        "box_body:back",
        "box_body:right_side",
        "door_c1_r1",
        "box_body:divider:0",
    }


def test_resolved_saved_dxf_acceptance_rejects_stale_extra_file(tmp_path):
    resolved = _resolved()
    api.save_resolved_manufacturing_geometry_dxf(resolved, tmp_path, overwrite=True)
    stale = tmp_path / "door_c9_r9.dxf"
    api.save_part_render_data_dxf(_render(10, 10), stale, overwrite=True)

    result = _group_verifier()(resolved, tmp_path)

    assert result.ok is False
    assert any(issue.category == "EXTRA_PART" for issue in result.issues)
