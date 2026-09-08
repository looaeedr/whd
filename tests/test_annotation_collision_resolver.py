# -*- coding: utf-8 -*-
import importlib
import importlib.util
import inspect

from ae_engine.drawing_annotations import AnnotationPlan, LinearDimensionAnnotation
from ae_engine.sheetmetal_drawing import (
    CirclePrimitive,
    DrawingScene,
    LinePrimitive,
    PolylinePrimitive,
    TextPrimitive,
)
from ae_engine.sheetmetal_geometry import Vec2


def _resolver_module():
    spec = importlib.util.find_spec("ae_engine.drawing_annotation_layout")
    assert spec is not None, (
        "R2: missing deterministic annotation collision resolver module"
    )
    return importlib.import_module("ae_engine.drawing_annotation_layout")


def _horizontal_plan():
    dimension = LinearDimensionAnnotation(
        axis="x",
        value=100.0,
        start=Vec2(0.0, 0.0),
        end=Vec2(100.0, 0.0),
        label="100",
    )
    return AnnotationPlan(
        overall_dimensions=(dimension,),
        feature_callouts=(),
        corner_callouts=(),
        radius_callouts=(),
        primitives=(
            LinePrimitive(Vec2(0.0, -15.0), Vec2(100.0, -15.0), "DIMENSION"),
            TextPrimitive("100", Vec2(50.0, -15.0), "DIMENSION", 5.0, 5),
        ),
        diagnostics=(),
    )


def test_horizontal_dimension_text_moves_only_along_dimension_axis_and_is_deterministic():
    layout = _resolver_module()
    region = layout.AnnotationRegion(
        min_x=44.0, min_y=-18.0, max_x=56.0, max_y=-12.0, kind="TITLE"
    )
    plan = _horizontal_plan()

    first = layout.resolve_annotation_collisions(plan, reserved_regions=(region,))
    second = layout.resolve_annotation_collisions(plan, reserved_regions=(region,))

    assert first == second
    moved = next(
        p for p in first.primitives
        if isinstance(p, TextPrimitive) and p.layer == "DIMENSION" and p.text == "100"
    )
    assert moved.insert.y == -15.0
    assert moved.insert.x != 50.0
    assert not region.contains_point(moved.insert)
    assert first.unresolved_collisions == ()


def test_vertical_dimension_text_moves_only_along_dimension_axis():
    layout = _resolver_module()
    dimension = LinearDimensionAnnotation(
        axis="y",
        value=60.0,
        start=Vec2(0.0, 0.0),
        end=Vec2(0.0, 60.0),
        label="60",
    )
    plan = AnnotationPlan(
        overall_dimensions=(dimension,),
        feature_callouts=(),
        corner_callouts=(),
        radius_callouts=(),
        primitives=(
            LinePrimitive(Vec2(-15.0, 0.0), Vec2(-15.0, 60.0), "DIMENSION"),
            TextPrimitive("60", Vec2(-15.0, 30.0), "DIMENSION", 5.0, 5),
        ),
        diagnostics=(),
    )
    region = layout.AnnotationRegion(
        min_x=-18.0, min_y=24.0, max_x=-12.0, max_y=36.0, kind="TECH"
    )

    result = layout.resolve_annotation_collisions(plan, reserved_regions=(region,))

    moved = next(
        p for p in result.primitives
        if isinstance(p, TextPrimitive) and p.layer == "DIMENSION" and p.text == "60"
    )
    assert moved.insert.x == -15.0
    assert moved.insert.y != 30.0
    assert not region.contains_point(moved.insert)
    assert result.unresolved_collisions == ()


def test_resolver_avoids_manufacturing_scene_without_mutating_it():
    layout = _resolver_module()
    dimension = LinearDimensionAnnotation(
        axis="x",
        value=100.0,
        start=Vec2(0.0, 20.0),
        end=Vec2(100.0, 20.0),
        label="100",
    )
    plan = AnnotationPlan(
        overall_dimensions=(dimension,),
        feature_callouts=(),
        corner_callouts=(),
        radius_callouts=(),
        primitives=(
            LinePrimitive(Vec2(0.0, 20.0), Vec2(100.0, 20.0), "DIMENSION"),
            TextPrimitive("100", Vec2(50.0, 20.0), "DIMENSION", 5.0, 5),
        ),
        diagnostics=(),
    )
    scene = DrawingScene()
    scene.add(PolylinePrimitive(
        (Vec2(0.0, 0.0), Vec2(100.0, 0.0), Vec2(100.0, 40.0), Vec2(0.0, 40.0)),
        "CUTTING",
        closed=True,
    ))
    scene.add(LinePrimitive(Vec2(50.0, 0.0), Vec2(50.0, 40.0), "BEND"))
    scene.add(CirclePrimitive(Vec2(60.0, 20.0), 4.0, "CUTTING"))
    before = tuple(scene.primitives)

    signature = inspect.signature(layout.resolve_annotation_collisions)
    assert "manufacturing_scene" in signature.parameters, (
        "R2: resolver must derive CUTTING/BEND/hole obstacle regions from DrawingScene"
    )
    result = layout.resolve_annotation_collisions(
        plan,
        manufacturing_scene=scene,
        step=5.0,
    )

    moved = next(
        p for p in result.primitives
        if isinstance(p, TextPrimitive) and p.layer == "DIMENSION" and p.text == "100"
    )
    assert moved.insert.y == 20.0
    assert moved.insert.x not in {50.0, 55.0, 60.0, 65.0}
    assert result.unresolved_collisions == ()
    assert tuple(scene.primitives) == before
