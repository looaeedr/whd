"""#3317 real surviving BEND material -> 20/50 CHECK stroke projection.

Machine MARKING is deliberately not emitted until CUTTING and formed
true-T / shop relief have a certified common source.
"""
from __future__ import annotations

import math

import ezdxf
import pytest
from shapely.geometry import LineString, Polygon

from ae_engine import manufacturing_api
from ae_engine.sheetmetal_drawing import (
    DrawingScene, LinePrimitive, PolylinePrimitive,
)
from ae_engine.sheetmetal_geometry_core import GeometryError, Vec2
from ae_engine.v_miter_material_trial import VMiterSourceBoundSharpCheck
from ae_engine.v_miter_source_marking_check import (
    project_v_miter_source_bend_marking_check,
)


def _one_piece_stock_and_candidate():
    outline = (Vec2(0, 0), Vec2(200, 0),
               Vec2(200, 200), Vec2(0, 200))
    first = LinePrimitive(Vec2(20, 20), Vec2(20, 180), "BEND")
    second = LinePrimitive(Vec2(20, 20), Vec2(180, 20), "BEND")
    scene = DrawingScene([PolylinePrimitive(outline, "CUTTING", closed=True),
                          first, second])
    # An explicit physical notch in the chosen corner; x+y >= 40
    # survives, including all original inward fold coverage.
    remaining = Polygon((
        (40, 0), (200, 0), (200, 200), (0, 200), (0, 40),
    ))
    removed = Polygon(((0, 0), (40, 0), (0, 40)))
    check = VMiterSourceBoundSharpCheck(
        source_material_area_mm2=40000,
        removed_material_area_mm2=removed.area,
        remaining_material_area_mm2=remaining.area,
        removed_corner_outline=tuple(
            Vec2(*xy) for xy in removed.exterior.coords
        ),
        remaining_outline=tuple(
            Vec2(*xy) for xy in remaining.exterior.coords
        ),
        first_perimeter_hit=Vec2(40, 0),
        second_perimeter_hit=Vec2(0, 40),
        first_perimeter_to_ideal_reach_ratio=1.0,
        second_perimeter_to_ideal_reach_ratio=1.0,
    )
    return scene, first, second, check, remaining


def _segment_length(segment):
    return math.hypot(segment.p2.x-segment.p1.x,
                      segment.p2.y-segment.p1.y)


def test_20_mm_end_strokes_and_middle_strokes_are_on_real_surviving_bend():
    scene, first, second, check, remaining = _one_piece_stock_and_candidate()
    original = tuple(scene.primitives)
    result = project_v_miter_source_bend_marking_check(
        scene, first, second, check,
    )
    assert result.manufacturing_status.endswith("UNCERTIFIED")
    assert result.first_source_span_mm == 160
    assert result.second_source_span_mm == 160
    assert result.first_surviving_crease_mm == pytest.approx(160, abs=1e-5)
    assert result.second_surviving_crease_mm == pytest.approx(160, abs=1e-5)
    assert result.first_source_stroke_count >= 2
    assert result.second_source_stroke_count >= 2
    assert len(result.check_strokes) == (
        result.first_source_stroke_count + result.second_source_stroke_count
    )
    for stroke in result.check_strokes:
        assert stroke.layer == "CHECK"
        assert stroke.color == 4
        assert _segment_length(stroke) == pytest.approx(20)
        line = LineString(((stroke.p1.x, stroke.p1.y),
                           (stroke.p2.x, stroke.p2.y)))
        assert remaining.buffer(1e-6).covers(line)
        assert (
            LineString(((first.p1.x, first.p1.y),
                        (first.p2.x, first.p2.y))).buffer(1e-6).covers(line)
            or LineString(((second.p1.x, second.p1.y),
                           (second.p2.x, second.p2.y))).buffer(1e-6).covers(line)
        )
    assert tuple(scene.primitives) == original
    assert not any(p.layer == "MARKING" for p in scene.primitives)


def test_one_source_bend_cut_away_cannot_generate_new_physical_marking():
    scene, first, second, check, remaining = _one_piece_stock_and_candidate()
    # Candidate keeps the upper half only, cutting the bottom BEND entirely.
    high = Polygon(((0, 50), (200, 50), (200, 200), (0, 200)))
    replace = VMiterSourceBoundSharpCheck(
        source_material_area_mm2=40000,
        removed_material_area_mm2=10000,
        remaining_material_area_mm2=high.area,
        removed_corner_outline=(Vec2(0, 0), Vec2(200, 0), Vec2(200, 50), Vec2(0, 50), Vec2(0, 0)),
        remaining_outline=tuple(Vec2(*xy) for xy in high.exterior.coords),
        first_perimeter_hit=Vec2(0, 50),
        second_perimeter_hit=Vec2(200, 50),
        first_perimeter_to_ideal_reach_ratio=1,
        second_perimeter_to_ideal_reach_ratio=1,
    )
    result = project_v_miter_source_bend_marking_check(
        scene, first, second, replace,
    )
    assert result.first_surviving_crease_mm < 160
    assert result.second_surviving_crease_mm == pytest.approx(0)
    assert result.first_source_stroke_count >= 1
    assert result.second_source_stroke_count == 0


def test_detached_bend_identity_must_fail_even_if_coordinates_match():
    scene, first, second, check, _ = _one_piece_stock_and_candidate()
    forged = LinePrimitive(first.p1, first.p2, layer="BEND")
    with pytest.raises(GeometryError, match="ORIGINAL_BEND_IDENTITY_REQUIRED"):
        project_v_miter_source_bend_marking_check(scene, forged, second, check)
    with pytest.raises(GeometryError, match="PHYSICAL_BEND_REQUIRED"):
        project_v_miter_source_bend_marking_check(
            scene, LinePrimitive(first.p1, first.p2, "CHECK"), second, check,
        )


@pytest.mark.parametrize("part_key", ("door", "head", "tail"))
def test_live_whole_sheet_dxf_contains_real_short_check_marks_only(
    part_key, tmp_path,
):
    import tkinter as tk
    import gui

    root = tk.Tk()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("自訂")
        app.workspace_controller.set_active_part(part_key)
        app.select_manual_corner("bottom")
        app.set_v_miter_gui_check_choice()
        live = app._project_v_miter_gui_check_for_corner(part_key, "bottom")
        marks = live.source_bend_marking_check
        assert marks is not None
        assert marks.first_source_span_mm > 0
        assert marks.second_source_span_mm > 0
        assert all(row.layer == "CHECK" and row.color == 4
                   for row in marks.check_strokes)
        assert live.full_sheet_check_scene is not None
        lines = tuple(row for row in live.full_sheet_check_scene.primitives
                      if isinstance(row, LinePrimitive)
                      and row.layer == "CHECK" and row.color == 4)
        assert lines == marks.check_strokes
        original = app._query_fold_designer_render_data(
            part_key, app._make_original_fold_designer_snapshot(),
        )
        before = tuple(original.scene.primitives)
        target = tmp_path / f"{part_key}_MARK_CHECK_ONLY_UNCERTIFIED.dxf"
        manufacturing_api.save_v_miter_whole_sheet_check_dxf(
            live.full_sheet_check_scene, target,
        )
        doc = ezdxf.readfile(target)
        actual = tuple(
            e for e in doc.modelspace()
            if e.dxftype() == "LINE" and e.dxf.layer == "CHECK"
            and e.dxf.color == 4
        )
        assert len(actual) == len(lines)
        assert all(e.dxf.layer != "MARKING"
                   for e in doc.modelspace())
        assert tuple(original.scene.primitives) == before
    finally:
        if app is not None:
            designer = getattr(app, "fold_designer_app", None)
            if designer is not None:
                try:
                    designer.root.destroy()
                except Exception:
                    pass
        root.destroy()
