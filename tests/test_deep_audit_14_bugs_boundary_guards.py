# -*- coding: utf-8 -*-
"""Boundary guards for the deep-audit 14 repair lane.

These exercise cases that the original 13 focused test functions did not
cover: source-owned Bay migration, semantic outer-boundary retention,
overlapping non-outer contours, duplicate segmented/closed outlines, all
nine MTEXT anchors, and degenerate open/closed polylines.
"""
from __future__ import annotations

import pytest
from shapely.geometry import Polygon

from ae_engine.assembly_collision_basic import _scene_with_replaced_primary_cutting
from ae_engine.cutting_material import material_from_cutting_components
from ae_engine.drawing_annotation_layout import _text_region
from ae_engine.manufacturing_render_data import (
    _translated_scene,
    material_polygon_from_final_scene,
)
from ae_engine.receiving_layout import (
    ensure_receiving_layout,
    new_receiving_layout,
    project_receiving_bay_legacy_aliases,
    resize_receiving_bays,
)
from ae_engine.receiving_pairing_marking import _existing_conflict_geometry
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive, TextPrimitive
from ae_engine.sheetmetal_geometry import Vec2


def _square(x0, y0, x1, y1):
    return tuple(Vec2(x, y) for x, y in (
        (x0, y0), (x1, y0), (x1, y1), (x0, y1)
    ))


def _border_lines(x0, y0, x1, y1):
    pts = _square(x0, y0, x1, y1)
    return tuple(LinePrimitive(pts[i], pts[(i + 1) % 4], layer="CUTTING") for i in range(4))


def test_bug4_legacy_root_door_state_migrates_only_into_primary_bay():
    layout = resize_receiving_bays(
        new_receiving_layout(width=600.0, height=1800.0, depth=500.0),
        set_index=0, bay_count=2,
    )
    # Simulate an older root-based project with two independent Bays.
    primary, other = layout["sets"][0]["bays"]
    primary.pop("door_state", None)
    other.pop("door_state", None)
    snapshot = {
        "model": "受電箱",
        "w": 600.0, "h": 1800.0, "d": 500.0,
        "multi_door_enabled": True,
        "door_layout_columns": [(600.0, (1800.0,))],
        "receiving_layout": layout,
    }
    migrated = ensure_receiving_layout(snapshot)
    bays = migrated["receiving_layout"]["sets"][0]["bays"]
    assert bays[0]["door_state"]["door_layout_columns"] == [(600.0, (1800.0,))]
    assert "door_state" not in bays[1]
    bay1 = project_receiving_bay_legacy_aliases(
        migrated, set_index=0, bay_index=1, validate_common=True,
    )
    assert bay1["multi_door_enabled"] is True
    assert bay1["door_layout_columns"][0][0] == float(bays[1]["width"])
    # 1800-mm Bay defaults are scaled from the family's 800x1600 template,
    # not the primary Bay's one-row 1800-mm operator override.
    assert bay1["door_layout_columns"] == [[600.0, [1237.5, 562.5]]]
    assert "door_state" not in bay1["receiving_layout"]["sets"][0]["bays"][1]


def test_bug4_primary_migration_when_second_bay_already_configured():
    layout = resize_receiving_bays(
        new_receiving_layout(width=600.0, height=1800.0, depth=500.0),
        set_index=0, bay_count=2,
    )
    primary, other = layout["sets"][0]["bays"]
    primary.pop("door_state", None)
    other["door_state"] = {"multi_door_enabled": False}
    snapshot = {
        "model": "受電箱", "w": 600.0, "h": 1800.0, "d": 500.0,
        "door_layout_columns": [(600.0, (1800.0,))],
        "multi_door_enabled": True, "receiving_layout": layout,
    }
    bays = ensure_receiving_layout(snapshot)["receiving_layout"]["sets"][0]["bays"]
    assert bays[0]["door_state"]["multi_door_enabled"] is True
    assert bays[1]["door_state"]["multi_door_enabled"] is False


def test_bug5_outer_boundary_identity_survives_scene_translation():
    scene = DrawingScene()
    # The cutout intentionally precedes the outer outline.
    scene.add(PolylinePrimitive(_square(40, 40, 60, 60), "CUTTING", closed=True))
    scene.add(PolylinePrimitive(
        _square(0, 0, 200, 100), "CUTTING",
        closed=True, semantic_id="OUTER_BOUNDARY",
    ))
    translated = _translated_scene(scene, 100, 50)
    boundary = translated.primitives[1]
    assert boundary.semantic_id == "OUTER_BOUNDARY"
    assert boundary.points[0] == Vec2(100, 50)
    material = material_polygon_from_final_scene(translated)
    assert float(material.area) == pytest.approx(19600.0)
    assert len(material.interiors) == 1


def test_bug6_larger_overlapping_contour_is_not_promoted_to_outer():
    # Its area is larger and it covers the original representative point,
    # but it does NOT contain the entire structural stock.
    original = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    overlapping = Polygon([(2, 2), (22, 2), (22, 22), (2, 22)])
    result = material_from_cutting_components(
        primary=original, secondary=(overlapping,),
    )
    assert result.bounds[0] >= -1e-8
    assert result.bounds[2] <= 10 + 1e-8
    assert not result.covers(overlapping.representative_point()) if overlapping.representative_point().x > 10 else result.area < overlapping.area


def test_bug7_closed_outer_and_segmented_duplicate_outer_do_not_double_cut():
    scene = DrawingScene()
    scene.add(PolylinePrimitive(_square(35, 35, 45, 45), "CUTTING", closed=True))
    scene.add(PolylinePrimitive(_square(0, 0, 100, 100), "CUTTING", closed=True))
    scene.extend(_border_lines(0, 0, 100, 100))
    final = Polygon([(0, 0), (90, 0), (90, 10), (100, 10), (100, 100), (0, 100)],
                    holes=[[(35, 35), (45, 35), (45, 45), (35, 45)]])
    fixed = _scene_with_replaced_primary_cutting(scene, final)
    cutting_lines = [
        p for p in fixed.primitives
        if isinstance(p, LinePrimitive) and p.layer.upper() == "CUTTING"
    ]
    assert cutting_lines == []
    closed = [
        p for p in fixed.primitives
        if isinstance(p, PolylinePrimitive) and p.layer.upper() == "CUTTING" and p.closed
    ]
    assert len(closed) == 2
    assert sum(p.semantic_id == "OUTER_BOUNDARY" for p in closed) == 1
    rebuilt = material_polygon_from_final_scene(fixed)
    assert rebuilt.area == pytest.approx(final.area)


def test_bug7_segmented_outer_preserves_inner_closed_and_linework_holes():
    scene = DrawingScene()
    scene.add(PolylinePrimitive(_square(20, 20, 30, 30), "CUTTING", closed=True))
    scene.extend(_border_lines(0, 0, 100, 100))
    # An independent hole is built from CUTTING linework.
    scene.extend(_border_lines(60, 60, 70, 70))
    final = Polygon(
        [(0, 0), (100, 0), (100, 100), (0, 100)],
        holes=[
            [(20, 20), (30, 20), (30, 30), (20, 30)],
            [(60, 60), (70, 60), (70, 70), (60, 70)],
        ],
    )
    fixed = _scene_with_replaced_primary_cutting(scene, final)
    lines = [p for p in fixed.primitives if isinstance(p, LinePrimitive) and p.layer == "CUTTING"]
    assert len(lines) == 4
    assert {(p.p1.x, p.p1.y) for p in lines} == {(60, 60), (70, 60), (70, 70), (60, 70)}
    assert material_polygon_from_final_scene(fixed).area == pytest.approx(final.area)


@pytest.mark.parametrize("attachment", range(1, 10))
def test_bug8_every_mtext_attachment_anchor(attachment):
    point = Vec2(100, 100)
    text = TextPrimitive("TEST", point, "TEXT", char_height=10, attachment_point=attachment)
    box = _text_region(text)
    width, height = 4 * 10 * 0.6, 10
    col = (attachment - 1) % 3
    row = (attachment - 1) // 3
    assert box.min_x == pytest.approx(100 - (0, width / 2, width)[col])
    assert box.min_y == pytest.approx(100 - (height, height / 2, 0)[row])
    assert box.max_x - box.min_x == pytest.approx(width)
    assert box.max_y - box.min_y == pytest.approx(height)


@pytest.mark.parametrize("points,closed", [
    ((), False),
    (((1.0, 1.0),), False),
    (((1.0, 1.0),), True),
    (((1.0, 1.0), (2.0, 1.0)), True),
    (((1.0, 1.0), (1.0, 1.0), (1.0, 1.0)), True),
])
def test_bug10_degenerate_cutting_polyline_does_not_crash(points, closed):
    primitive = PolylinePrimitive(
        tuple(Vec2(x, y) for x, y in points),
        "CUTTING", closed=closed,
    )
    material = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    assert _existing_conflict_geometry(primitive, material) is None
