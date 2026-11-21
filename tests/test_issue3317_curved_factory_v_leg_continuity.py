"""#3317 R/BA curved physical V sidewalls -> interval-complete CHECK gap.

The measured gap must come from source-tagged *inclined V* CUTTING faces,
never the true bottom R/Ø relief face or a whole-solid nearest point.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from shapely.geometry import LineString, Polygon

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry_core import GeometryError
from ae_engine.v_miter_source_cut_face_trial import (
    trace_v_miter_source_true_t_cut_faces,
)


def _gui(part_key):
    import tkinter as tk
    import gui

    root = tk.Tk()
    app = gui.BoxCalculatorGUI(root)
    app.baseline_var.set("自訂")
    app.workspace_controller.set_active_part(part_key)
    app.select_manual_corner("bottom_left")
    app.set_v_miter_gui_check_choice()
    state = app._make_original_fold_designer_snapshot()
    spec, _ = app._fold_designer_part_spec_from_payload(part_key, state)
    render = app._query_fold_designer_render_data(part_key, state)
    return root, app, spec, render


def _close(root, app):
    designer = getattr(app, "fold_designer_app", None)
    if designer is not None:
        try:
            designer.root.destroy()
        except Exception:
            pass
    root.destroy()


@pytest.mark.parametrize("part_key,mode", (
    ("door", "ROUND_R"), ("door", "RELIEF_HOLE"),
    ("head", "ROUND_R"), ("head", "RELIEF_HOLE"),
))
def test_factory_curved_t_true_v_leg_faces_and_continuity_proof(part_key, mode):
    root, app, spec, render = _gui(part_key)
    try:
        original = tuple(render.scene.primitives)
        live = api.project_operator_v_miter_live_corner_check(
            spec, render, "bottom_left",
            relief_mode=mode, run_radius_ba_trial=True,
        )
        assert live.factory_radius_ba_check is not None, (
            live.factory_radius_ba_failure
        )
        result = live.factory_radius_ba_check
        assert result.manufacturing_status.endswith("UNCERTIFIED")
        assert result.formed_source_outline == (
            live.factory_bottom_relief_check.corrected_remaining_outline
        )
        first = result.first_source_tagged_cut_faces
        second = result.second_source_tagged_cut_faces
        assert first is not None, result.first_cut_face_failure
        assert second is not None, result.second_cut_face_failure
        assert first.has_source_tagged_cut_faces
        assert second.has_source_tagged_cut_faces
        assert first.selected_flat_v_cut_length_mm > 0
        assert second.selected_flat_v_cut_length_mm > 0
        assert len(first.true_cut_face_triangles) % 2 == 0
        assert len(second.true_cut_face_triangles) % 2 == 0
        # Genuine selected inclined faces must yield an interval analysis
        # or a precise GeometryError, never an assumed continuous zero gap.
        continuity = result.source_cut_face_continuity
        assert continuity is not None, result.source_cut_face_continuity_failure
        assert continuity.manufacturing_status.endswith("UNCERTIFIED")
        assert continuity.seam_length_mm == pytest.approx(
            live.ideal.formed_contact_length_mm
        )
        assert continuity.both_face_interval_count + (
            continuity.missing_face_interval_count
        ) == len(continuity.intervals)
        assert continuity.both_face_span_mm + (
            continuity.first_missing_span_mm + continuity.second_missing_span_mm
            + continuity.both_missing_span_mm
        ) == pytest.approx(continuity.seam_length_mm)
        if continuity.missing_face_interval_count:
            assert continuity.max_gap_upper_bound_mm is None
        # An unresolved open interval never qualifies as "zero separation".
        if continuity.max_gap_upper_bound_mm is not None:
            assert continuity.max_gap_upper_bound_mm >= 0
            assert continuity.missing_face_interval_count == 0
        assert tuple(render.scene.primitives) == original
        assert all(p.layer in {"CHECK", "DATUM"}
                   for p in live.full_sheet_check_scene.primitives)
        with pytest.raises(GeometryError, match="CHECK_ONLY_UNCERTIFIED"):
            api.require_no_operator_v_miter_gui_check_for_export(
                {"v_miter_gui_check_corners":
                    {part_key: {"bottom_left": "V_MITER_CHECK"}}}
            )
    finally:
        _close(root, app)


def test_invalid_source_v_legs_rejected_before_face_coverage():
    base = Polygon(((0, 0), (100, 0), (100, 100), (0, 100)))
    corrected = Polygon(((0, 0), (100, 0), (100, 100), (0, 100)))
    for malformed in (
        "not physical lines",
        (LineString(((0, 0), (1, 1))),),
        (LineString(((0, 0), (1, 1))), "not a line"),
        (LineString(((0, 0), (0, 0))), LineString(((0, 0), (1, 1)))),
    ):
        with pytest.raises(GeometryError, match="LEGS_INVALID"):
            trace_v_miter_source_true_t_cut_faces(
                base, corrected, (), (), (),
                thickness_mm=2, physical_v_cut_leg_lines=malformed,
            )


def test_cut_face_lineage_missing_is_not_zero_gap(monkeypatch):
    import ae_engine.v_miter_factory_radius_ba_check as owner

    root, app, spec, render = _gui("door")
    try:
        real = owner.trace_v_miter_source_true_t_cut_faces
        observed = []

        def drop_true_wall(*args, **kwargs):
            observed.append(kwargs["physical_v_cut_leg_lines"])
            row = real(*args, **kwargs)
            return replace(row, true_cut_face_triangles=())

        monkeypatch.setattr(
            owner, "trace_v_miter_source_true_t_cut_faces", drop_true_wall,
        )
        live = api.project_operator_v_miter_live_corner_check(
            spec, render, "bottom_left",
            relief_mode="ROUND_R", run_radius_ba_trial=True,
        )
        curve = live.factory_radius_ba_check
        assert curve is not None, live.factory_radius_ba_failure
        assert len(observed) == 2
        assert all(
            len(legs) == 2 and all(isinstance(x, LineString) for x in legs)
            for legs in observed
        )
        assert curve.first_source_tagged_cut_faces is None
        assert curve.second_source_tagged_cut_faces is None
        assert curve.source_cut_face_continuity is None
        assert "SIDEWALL_INCOMPLETE" in curve.source_cut_face_continuity_failure
        assert curve.curved_t_surface_interference_pairs >= 0
    finally:
        _close(root, app)


def test_no_second_gui_sidewall_or_mating_formula():
    text = (
        Path(__file__).parents[1] /
        "gui_modules/parts/panels/assembly_corner.py"
    ).read_text(encoding="utf-8")
    assert "source_cut_face_continuity" in text
    assert "max_gap_upper_bound_mm" in text
    assert "project_v_miter_true_cut_face_continuity_trial" not in text
    assert "math.sin(" not in text
