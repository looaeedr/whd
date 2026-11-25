"""#3317: new V Factory Fold receives 20/50 CHECK strokes, not old C01 marks.

Independent source identity is proved in the Factory-fold owner; short-stroke
layout is exactly the existing Engine MARKING projector, then recast as
CHECK so an un-certified V cannot escape to manufacturing DXF.
"""
from __future__ import annotations

import math

import ezdxf
import pytest
from shapely.geometry import LineString, Polygon

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import LinePrimitive
from ae_engine.v_miter_bend_marking import project_v_miter_bend_markings


def _axis_line(row):
    return LineString(((row.p1.x, row.p1.y), (row.p2.x, row.p2.y)))


@pytest.mark.parametrize("part_key", ("door", "head", "tail"))
@pytest.mark.parametrize("physical_corner", ("bottom_left", "bottom_right"))
def test_typed_factory_post_v_fold_marked_20_50_without_machine_layers(
    part_key, physical_corner, tmp_path,
):
    import tkinter as tk
    import gui

    root = tk.Tk()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("自訂")
        app.workspace_controller.set_active_part(part_key)
        app.select_manual_corner(physical_corner)
        app.set_v_miter_gui_check_choice()
        app.v_miter_first_bend_axis_var.set("x")
        app.set_v_miter_gui_first_bend_axis()
        snapshot = app._make_original_fold_designer_snapshot()
        original = app._query_fold_designer_render_data(part_key, snapshot)
        old_primitives = tuple(original.scene.primitives)
        live = app._project_v_miter_gui_check_for_corner(
            part_key, physical_corner,
        )
        factory = live.factory_precut_fold_check
        assert factory is not None, live.factory_precut_fold_failure
        assert live.material_check is not None
        assert live.full_sheet_check_scene is not None
        remaining = Polygon(
            (p.x, p.y) for p in live.material_check.remaining_outline
        )
        all_segments = (
            factory.first_proposed_segments,
            factory.second_proposed_segments,
        )
        all_marks = (
            factory.first_proposed_alignment_marks,
            factory.second_proposed_alignment_marks,
        )
        assert all_marks[0] and all_marks[1]
        for side_segments, side_marks in zip(all_segments, all_marks):
            expected = []
            for candidate in side_segments:
                # The *independent* old Engine marking algorithm is the
                # actual 20/50 oracle, not a second GUI-side formula.
                bend = LinePrimitive(candidate.p1, candidate.p2, "BEND")
                expected.extend(
                    project_v_miter_bend_markings(
                        bend, stroke_mm=20.0, clear_gap_mm=50.0,
                    )
                )
            assert len(side_marks) == len(expected)
            for mark, raw in zip(side_marks, expected):
                assert mark.layer == "CHECK"
                assert mark.color == 3
                assert (mark.p1, mark.p2) == (raw.p1, raw.p2)
                assert 0 < _axis_line(mark).length <= 20.0 + 1e-7
                assert remaining.buffer(1e-6).covers(_axis_line(mark))
                assert any(
                    _axis_line(segment).buffer(1e-6).covers(_axis_line(mark))
                    for segment in side_segments
                )
        in_scene = tuple(
            p for p in live.full_sheet_check_scene.primitives
            if isinstance(p, LinePrimitive) and p.layer == "CHECK"
            and p.color == 3
        )
        assert in_scene == all_marks[0] + all_marks[1]

        path = tmp_path / f"{part_key}_{physical_corner}_V_FOLD_CHECK_ONLY.dxf"
        api.save_v_miter_whole_sheet_check_dxf(
            live.full_sheet_check_scene, path,
        )
        doc = ezdxf.readfile(path)
        drawn = tuple(
            e for e in doc.modelspace()
            if e.dxftype() == "LINE" and e.dxf.layer == "CHECK"
            and e.dxf.color == 3
        )
        assert len(drawn) == len(in_scene)
        for entity, line in zip(drawn, in_scene):
            assert (entity.dxf.start.x, entity.dxf.start.y) == pytest.approx(
                (line.p1.x, line.p1.y),
            )
            assert (entity.dxf.end.x, entity.dxf.end.y) == pytest.approx(
                (line.p2.x, line.p2.y),
            )
        assert not any(e.dxf.layer in {"CUTTING", "BEND", "MARKING"}
                       for e in doc.modelspace())
        assert tuple(original.scene.primitives) == old_primitives
        assert factory.manufacturing_status.endswith("UNCERTIFIED")
    finally:
        if app is not None:
            designer = getattr(app, "fold_designer_app", None)
            if designer is not None:
                try:
                    designer.root.destroy()
                except Exception:
                    pass
        root.destroy()
