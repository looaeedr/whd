"""#3317 only source-identified V cut sidewalls may produce seam gap bounds.

The original formed zero-R seam datum is NOT a factory acceptance limit;
absence of real cut-face triangles is UNKNOWN, never a zero-gap certificate.
"""
from __future__ import annotations

import math

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.v_miter_factory_true_t_check import (
    project_v_miter_factory_post_v_true_t_check,
)
from ae_engine.v_miter_material_trial import _single_source_material
from ae_engine.v_miter_operator_gui_check import _physical_corner_bends
from ae_engine.v_miter_source_cut_face_trial import VMiterSourceCutFaceTrial


@pytest.mark.parametrize("part_key", ("door", "head", "tail"))
def test_real_live_v_cut_face_intervals_never_invent_gap_when_source_missing(
    part_key,
):
    import tkinter as tk
    import gui

    root = tk.Tk()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("自訂")
        app.workspace_controller.set_active_part(part_key)
        app.select_manual_corner("bottom_left")
        app.set_v_miter_gui_check_choice()
        snap = app._make_original_fold_designer_snapshot()
        render = app._query_fold_designer_render_data(part_key, snap)
        original = tuple(render.scene.primitives)
        live = app._project_v_miter_gui_check_for_corner(
            part_key, "bottom_left",
        )
        thick = live.factory_true_t_check
        assert thick is not None, live.factory_true_t_failure
        trial = thick.source_cut_face_continuity
        if trial is None:
            assert thick.source_cut_face_continuity_failure
            assert thick.manufacturing_status.endswith("UNCERTIFIED")
        else:
            assert trial.manufacturing_status.endswith("UNCERTIFIED")
            assert trial.intervals
            assert sum(row.length_mm for row in trial.intervals) == pytest.approx(
                trial.seam_length_mm, abs=1e-5,
            )
            assert trial.both_face_interval_count + trial.missing_face_interval_count == len(
                trial.intervals,
            )
            assert all(
                row.midpoint_section.status in {
                    "MEASURED", "FIRST_MISSING",
                    "SECOND_MISSING", "BOTH_MISSING",
                }
                for row in trial.intervals
            )
            if trial.missing_face_interval_count:
                assert trial.gap_bound_status != "CONSERVATIVE_SOURCE_MESH_ENVELOPE_CHECK"
                assert trial.max_gap_upper_bound_mm is None
        assert tuple(render.scene.primitives) == original
        assert all(p.layer in {"CHECK", "DATUM"}
                   for p in live.full_sheet_check_scene.primitives)
        label = app.manual_corner_param_summary.cget("text")
        assert ("真實 V 厚度側面" in label
                or "原 V 切邊" in label)
        assert "未認證" in label
    finally:
        if app is not None:
            designer = getattr(app, "fold_designer_app", None)
            if designer is not None:
                try:
                    designer.root.destroy()
                except Exception:
                    pass
        root.destroy()


@pytest.mark.parametrize("two_tagged", (True, False))
def test_intervals_are_called_only_with_both_proven_source_cut_faces(
    monkeypatch, two_tagged,
):
    from tests.test_issue3317_factory_post_v_true_t_gui import (
        _real_selected_live, _close,
    )
    import ae_engine.v_miter_factory_true_t_check as owner

    root, app, spec, render, live = _real_selected_live("door", "bottom_left")
    try:
        assert live.factory_precut_fold_check is not None
        geom = _single_source_material(render.scene)
        first, second, _, _, _, _, real_first, real_second = (
            _physical_corner_bends(render.scene, geom, "bottom_left")
        )
        tri = (((0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (0.0, 2.0, 0.0)),)
        calls = []
        def traced(*args, **kwargs):
            calls.append(("trace", kwargs["thickness_mm"]))
            source_mesh = tri if (two_tagged or len(calls) == 2) else ()
            return VMiterSourceCutFaceTrial(
                source_new_v_cut_length_mm=1,
                selected_flat_v_cut_length_mm=1 if source_mesh else 0,
                formed_boundary_edge_count=1 if source_mesh else 0,
                true_cut_face_triangles=source_mesh,
            )
        sentinel = object()
        def continuity(first_faces, second_faces, **kwargs):
            calls.append(("continuity", len(first_faces), len(second_faces)))
            assert first_faces == tri
            assert second_faces == tri
            assert kwargs["formed_seam_start"] == live.ideal.formed_seam_start
            assert kwargs["formed_seam_end"] == live.ideal.formed_seam_end
            return sentinel

        monkeypatch.setattr(owner, "trace_v_miter_source_true_t_cut_faces", traced)
        monkeypatch.setattr(
            owner, "project_v_miter_true_cut_face_continuity_trial", continuity,
        )
        actual = project_v_miter_factory_post_v_true_t_check(
            spec, render, "bottom_left", live.ideal, live.material_check,
            live.factory_precut_fold_check, real_first, real_second,
            first, second, live.factory_mother_check,
        )
        assert len(tuple(c for c in calls if c[0] == "trace")) == 2
        if two_tagged:
            assert actual.source_cut_face_continuity is sentinel
            assert actual.source_cut_face_continuity_failure is None
            assert len(tuple(c for c in calls if c[0] == "continuity")) == 1
        else:
            assert actual.source_cut_face_continuity is None
            assert actual.source_cut_face_continuity_failure == (
                "V_MITER_FACTORY_T_CUT_FACE_LINEAGE_UNPROVEN"
            )
            assert not any(c[0] == "continuity" for c in calls)
    finally:
        _close(root, app)
