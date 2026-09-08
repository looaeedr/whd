# -*- coding: utf-8 -*-
import importlib
import importlib.util

import pytest
from shapely.geometry import Polygon

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import (
    CirclePrimitive,
    DrawingScene,
    PolylinePrimitive,
    TextPrimitive,
    resolved_features_to_primitives,
)
from ae_engine.sheetmetal_features import ResolvedCircle
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
    spec = importlib.util.find_spec("ae_engine.drawing_annotations")
    assert spec is not None, (
        "R1: missing canonical Annotation Planner module; "
        "2D/engineering annotations cannot currently be derived from PartRenderData"
    )
    annotations = importlib.import_module("ae_engine.drawing_annotations")
    planner = getattr(annotations, "plan_part_annotations", None)
    assert callable(planner), (
        "R1: missing plan_part_annotations public seam; "
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


def _render_with_rounded_corner():
    # 100 x 60 blank with a true sampled R10 top-right quarter arc.
    outline = (
        Vec2(0, 0), Vec2(100, 0), Vec2(100, 50),
        Vec2(99.238795, 53.826834),
        Vec2(97.071068, 57.071068),
        Vec2(93.826834, 59.238795),
        Vec2(90, 60), Vec2(0, 60),
    )
    scene = DrawingScene()
    scene.add(PolylinePrimitive(outline, "CUTTING", closed=True))
    return api.PartRenderData(
        scene=scene,
        material=api.material_polygon_from_final_scene(scene),
        fold_guides=(),
    )


def test_annotation_plan_measures_radius_from_final_material_arc():
    render = _render_with_rounded_corner()

    plan = _planner()(render)

    assert len(plan.radius_callouts) == 1
    radius = plan.radius_callouts[0]
    assert abs(radius.radius - 10.0) <= 1e-4
    assert radius.label == "R10"
    assert radius.center.x == pytest.approx(90.0, abs=1e-4)
    assert radius.center.y == pytest.approx(50.0, abs=1e-4)


def test_resolved_circle_source_metadata_reaches_annotation_planner():
    scene = DrawingScene()
    scene.add(PolylinePrimitive(
        (Vec2(0, 0), Vec2(100, 0), Vec2(100, 60), Vec2(0, 60)),
        "CUTTING",
        closed=True,
    ))
    scene.extend(resolved_features_to_primitives((
        ResolvedCircle(
            center=Vec2(30, 20),
            radius=4.0,
            layer="CUTTING",
            source_type="mounting_hole",
        ),
    )))
    render = api.PartRenderData(
        scene=scene,
        material=api.material_polygon_from_final_scene(scene),
        fold_guides=(),
    )

    plan = _planner()(render)

    hole = next(item for item in plan.feature_callouts if item.source_type == "mounting_hole")
    assert hole.anchor == Vec2(30.0, 20.0)
    assert hole.label == "⌀8"
