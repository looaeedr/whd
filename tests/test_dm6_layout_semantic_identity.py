# -*- coding: utf-8 -*-
from dataclasses import replace

from shapely.geometry import Polygon

from ae_engine.drawing_annotations import plan_part_annotations
from ae_engine.drawing_annotation_layout import AnnotationRegion, resolve_annotation_collisions
from ae_engine.manufacturing_api import PartRenderData
from ae_engine.sheetmetal_drawing import CirclePrimitive, DrawingScene, PolylinePrimitive, TextPrimitive
from ae_engine.sheetmetal_geometry import Vec2


def _render_square_with_two_equal_holes():
    scene = DrawingScene()
    scene.add(PolylinePrimitive(
        (Vec2(0, 0), Vec2(100, 0), Vec2(100, 100), Vec2(0, 100)),
        "CUTTING",
        closed=True,
    ))
    scene.add(CirclePrimitive(
        Vec2(20, 20), 5.0, "CUTTING",
        source_type="mounting_hole", source_id="H1",
    ))
    scene.add(CirclePrimitive(
        Vec2(80, 20), 5.0, "CUTTING",
        source_type="mounting_hole", source_id="H2",
    ))
    return PartRenderData(
        scene=scene,
        material=Polygon(((0, 0), (100, 0), (100, 100), (0, 100))),
        fold_guides=(),
    )


def _annotation_texts(plan):
    return tuple(p for p in plan.primitives if isinstance(p, TextPrimitive))


def test_dm6_t2_red_planner_text_primitives_carry_semantic_identity():
    plan = plan_part_annotations(_render_square_with_two_equal_holes())

    texts = _annotation_texts(plan)
    assert texts
    missing = [p.text for p in texts if not getattr(p, "semantic_id", None)]

    assert missing == [], (
        "DM6 T2 RED: Planner->Layout seam drops semantic identity on presentation "
        f"text primitives: {missing!r}"
    )


def test_dm6_t2_red_dimension_layout_survives_display_text_mutation():
    plan = plan_part_annotations(_render_square_with_two_equal_holes())
    x_semantic = next(item for item in plan.overall_dimensions if item.axis == "x")
    x_text_index = next(
        i for i, primitive in enumerate(plan.primitives)
        if isinstance(primitive, TextPrimitive)
        and primitive.layer == "DIMENSION"
        and primitive.text == x_semantic.label
        and abs(float(primitive.insert.y) + 15.0) <= 1e-9
    )
    original = plan.primitives[x_text_index]
    semantic_id = getattr(original, "semantic_id", None)
    assert semantic_id, (
        "DM6 T2 RED: dimension presentation primitive must carry Planner semantic identity"
    )

    mutated = replace(original, text="100.0 mm")
    primitives = list(plan.primitives)
    primitives[x_text_index] = mutated
    mutated_plan = replace(plan, primitives=tuple(primitives))
    blocker = AnnotationRegion(
        min_x=42.0, min_y=-18.0, max_x=58.0, max_y=-12.0, kind="TITLE"
    )

    result = resolve_annotation_collisions(mutated_plan, reserved_regions=(blocker,))
    moved = result.primitives[x_text_index]

    assert getattr(moved, "semantic_id", None) == semantic_id
    assert moved.insert.y == original.insert.y
    assert moved.insert.x != original.insert.x
    assert result.unresolved_collisions == ()


def test_dm6_t2_red_duplicate_callout_layout_keeps_source_anchor_by_identity():
    plan = plan_part_annotations(_render_square_with_two_equal_holes())
    h1 = next(item for item in plan.feature_callouts if item.source_id == "H1")
    h2 = next(item for item in plan.feature_callouts if item.source_id == "H2")
    callout_indices = [
        i for i, primitive in enumerate(plan.primitives)
        if isinstance(primitive, TextPrimitive)
        and primitive.layer == "TEXT"
        and primitive.text == "⌀10"
    ]
    assert len(callout_indices) == 2

    keyed = {
        getattr(plan.primitives[i], "semantic_id", None): i
        for i in callout_indices
    }
    assert h1.semantic_id in keyed and h2.semantic_id in keyed, (
        "DM6 T2 RED: duplicate display labels must be bound to source semantic ids "
        "before Layout; distance/label guessing is not authority"
    )

    h1_index = keyed[h1.semantic_id]
    original = plan.primitives[h1_index]
    blocker = AnnotationRegion(
        min_x=float(original.insert.x) - 3.0,
        min_y=float(original.insert.y) - 3.0,
        max_x=float(original.insert.x) + 20.0,
        max_y=float(original.insert.y) + 8.0,
        kind="TECH",
    )
    result = resolve_annotation_collisions(plan, reserved_regions=(blocker,), step=5.0, max_steps=20)
    moved = result.primitives[h1_index]
    leaders = [p for p in result.primitives if getattr(p, "layer", None) == "TEXT" and hasattr(p, "p1")]

    assert getattr(moved, "semantic_id", None) == h1.semantic_id
    assert any(line.p1 == h1.anchor and line.p2 == moved.insert for line in leaders)
    assert not any(line.p1 == h2.anchor and line.p2 == moved.insert for line in leaders)
    assert result.unresolved_collisions == ()
