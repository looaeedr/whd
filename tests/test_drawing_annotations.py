# -*- coding: utf-8 -*-
from copy import deepcopy

from shapely.geometry import Polygon

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import (
    CirclePrimitive,
    DrawingScene,
    PolylinePrimitive,
    TextPrimitive,
)
from ae_engine.sheetmetal_geometry import Vec2


def _render_with_chamfer_and_hole():
    # 100 x 60 final material, with a 10 x 10 top-right relief/chamfer.
    outline = (
        Vec2(0, 0), Vec2(100, 0), Vec2(100, 50),
        Vec2(90, 60), Vec2(0, 60),
    )
    scene = DrawingScene()
    scene.add(PolylinePrimitive(outline, "CUTTING", closed=True))
    scene.add(CirclePrimitive(
        Vec2(40, 20), 5.0, "CUTTING",
        source_type="mounting_hole", source_id="H1",
    ))
    # Deliberately far away: drawing/display bbox must not inflate manufacturing dimensions.
    scene.add(TextPrimitive("CHECK", Vec2(1000, 1000), "CHECK", 12.0, 5))
    return api.PartRenderData(
        scene=scene,
        material=api.material_polygon_from_final_scene(scene),
        fold_guides=(),
    )


def _planner():
    import ae_engine.drawing_annotations as annotations
    planner = getattr(annotations, "plan_part_annotations", None)
    assert callable(planner), (
        "R1: missing canonical Annotation Planner; "
        "2D/engineering annotations cannot currently be derived from PartRenderData"
    )
    return planner


def test_annotation_plan_uses_final_material_bounds_not_drawing_bbox():
    render = _render_with_chamfer_and_hole()

    plan = _planner()(render)

    dims = {(item.axis, item.value) for item in plan.overall_dimensions}
    assert dims == {("x", 100.0), ("y", 60.0)}
    assert all(p.layer not in {"CUTTING", "BEND"} for p in plan.primitives)


def test_annotation_plan_uses_authoritative_hole_metadata():
    render = _render_with_chamfer_and_hole()

    plan = _planner()(render)

    hole = next(item for item in plan.feature_callouts if item.source_id == "H1")
    assert hole.source_type == "mounting_hole"
    assert hole.anchor == Vec2(40.0, 20.0)
    assert hole.label == "⌀10"


def test_annotation_plan_measures_corner_relief_from_final_material():
    render = _render_with_chamfer_and_hole()

    plan = _planner()(render)

    relief = next(item for item in plan.corner_callouts if item.corner == "TOP_RIGHT")
    assert relief.width == 10.0
    assert relief.height == 10.0
    assert "10" in relief.label


def test_annotation_plan_is_deterministic_and_does_not_mutate_canonical_data():
    render = _render_with_chamfer_and_hole()
    before_primitives = tuple(render.scene.primitives)
    before_wkb = bytes(render.material.wkb)

    first = _planner()(render)
    second = _planner()(render)

    assert first == second
    assert tuple(render.scene.primitives) == before_primitives
    assert bytes(render.material.wkb) == before_wkb
