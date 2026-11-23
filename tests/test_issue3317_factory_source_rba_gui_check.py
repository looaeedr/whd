"""#3317: actual GUI fifth V option can opt into source-bound R/BA/T CHECK.

The generic R/K/relief defaults never become Factory calibration or CNC
authorization. Only an explicit GUI trial may run the costly curved mesh.
"""
from __future__ import annotations

from dataclasses import replace
import math

import pytest
from shapely.geometry import Polygon

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry_core import GeometryError
from ae_engine.v_miter_factory_radius_ba_check import (
    project_v_miter_factory_radius_ba_default_check,
)
from ae_engine.v_miter_material_trial import _single_source_material
from ae_engine.v_miter_operator_gui_check import _physical_corner_bends


def _real_factory_v_gui(part_key="door", corner="bottom_left"):
    import tkinter as tk
    import gui

    root = tk.Tk()
    app = gui.BoxCalculatorGUI(root)
    app.baseline_var.set("自訂")
    app.workspace_controller.set_active_part(part_key)
    app.select_manual_corner(corner)
    app.set_v_miter_gui_check_choice()
    app.v_miter_first_bend_axis_var.set("x")
    app.set_v_miter_gui_first_bend_axis()
    snap = app._make_original_fold_designer_snapshot()
    spec, _ = app._fold_designer_part_spec_from_payload(part_key, snap)
    render = app._query_fold_designer_render_data(part_key, snap)
    return root, app, spec, render


def _destroy(root, app):
    if app is not None:
        designer = getattr(app, "fold_designer_app", None)
        if designer is not None:
            try:
                designer.root.destroy()
            except Exception:
                pass
    root.destroy()


@pytest.mark.parametrize("part_key", ["door", "head"])
def test_opt_in_real_factory_v_uses_original_part_and_default_rba(part_key):
    root, app, spec, render = _real_factory_v_gui(part_key)
    try:
        source = tuple(render.scene.primitives)
        no_trial = api.project_operator_v_miter_live_corner_check(
            spec, render, "bottom_left", first_bend_axis="x",
        )
        assert no_trial.factory_true_t_check is not None
        assert no_trial.factory_radius_ba_check is None
        assert no_trial.factory_radius_ba_failure is None
        calculated = api.project_operator_v_miter_live_corner_check(
            spec, render, "bottom_left", first_bend_axis="x", run_radius_ba_trial=True,
        )
        assert calculated.factory_true_t_check is not None
        assert calculated.trial_defaults is not None
        assert calculated.trial_defaults.first_inner_radius_mm == pytest.approx(spec.thickness)
        assert calculated.trial_defaults.first_bend_allowance_mm == pytest.approx(
            math.pi / 2 * 1.33 * spec.thickness,
        )
        # Real factory/tolerance/mesh may reject a default trial; a genuine
        # rejection must be surfaced, not silently projected as 0 collisions.
        if part_key == "door":
            # A genuine installed Factory source must prove that R/BA
            # reaches actual curved finite-T geometry, not just text labels.
            assert calculated.factory_radius_ba_check is not None, (
                calculated.factory_radius_ba_failure
            )
        if calculated.factory_radius_ba_check is None:
            assert calculated.factory_radius_ba_failure
        else:
            proposal = calculated.factory_radius_ba_check
            assert proposal.manufacturing_status.endswith("UNCERTIFIED")
            assert proposal.first_formed_perimeter_edges
            assert proposal.second_formed_perimeter_edges
            assert proposal.first_curved_skin_triangles
            assert proposal.second_curved_skin_triangles
            assert proposal.first_thick_solid_triangles
            assert proposal.second_thick_solid_triangles
            # #3390 corrected Factory R/hole stock is the actual R/BA source.
            assert proposal.relief_application_status.endswith("RELIEF_APPLIED_UNCERTIFIED")
            assert proposal.trim_application_status.endswith("NOT_YET_SOLVED")
            assert all(getattr(row, "semantic_id", None)
                       != "v_miter_engine_r_ba_uncertified_only"
                       for row in calculated.full_sheet_check_scene.primitives)
        assert tuple(render.scene.primitives) == source
        assert all(row.layer in {"CHECK", "DATUM"}
                   for row in calculated.full_sheet_check_scene.primitives)
        with pytest.raises(GeometryError, match="CHECK_ONLY_UNCERTIFIED"):
            api.require_no_operator_v_miter_gui_check_for_export({
                "v_miter_gui_check_corners": {
                    part_key: {"bottom_left": "V_MITER_CHECK"}
                }
            })
    finally:
        _destroy(root, app)


def test_factory_rba_bridge_rejects_forged_default_and_real_bend_provenance():
    root, app, spec, render = _real_factory_v_gui()
    try:
        live = api.project_operator_v_miter_live_corner_check(
            spec, render, "bottom_left", first_bend_axis="x",
        )
        mat = _single_source_material(render.scene)
        x, y, _, _, _, _, real_x, real_y = _physical_corner_bends(
            render.scene, mat, "bottom_left",
        )
        roles = (x, y) if live.first_bend_axis == "x" else (y, x)
        actuals = (real_x, real_y) if live.first_bend_axis == "x" else (real_y, real_x)
        assert live.factory_precut_fold_check is not None
        defaults = live.trial_defaults
        args = (
            spec, render, "bottom_left", live.ideal, live.material_check,
            live.factory_precut_fold_check,
            *actuals, *roles, defaults, live.factory_mother_check,
        )
        with pytest.raises(GeometryError, match="DEFAULTS_SOURCE_CHANGED"):
            project_v_miter_factory_radius_ba_default_check(
                *args[:-2], replace(defaults, first_inner_radius_mm=3),
                live.factory_mother_check,
            )
        forged_real = type(actuals[0])(actuals[0].p1, actuals[0].p2, "BEND")
        with pytest.raises(GeometryError, match="BEND_IDENTITY"):
            project_v_miter_factory_radius_ba_default_check(
                spec, render, "bottom_left", live.ideal, live.material_check,
                live.factory_precut_fold_check,
                forged_real, actuals[1], *roles,
                defaults, live.factory_mother_check,
            )
    finally:
        _destroy(root, app)


def test_factory_curved_t_stage_uses_actual_post_v_stock_without_fabricating_contour(monkeypatch):
    """Physical curved V trial is computed from existing Factory-clipped sheets."""
    import ae_engine.v_miter_factory_radius_ba_check as owner

    root, app, spec, render = _real_factory_v_gui()
    try:
        live = api.project_operator_v_miter_live_corner_check(
            spec, render, "bottom_left", first_bend_axis="x",
        )
        mat = _single_source_material(render.scene)
        x, y, _, _, _, _, real_x, real_y = _physical_corner_bends(
            render.scene, mat, "bottom_left",
        )
        roles = (x, y) if live.first_bend_axis == "x" else (y, x)
        actuals = (real_x, real_y) if live.first_bend_axis == "x" else (real_y, real_x)
        original = tuple(render.scene.primitives)
        verified_v = Polygon((p.x, p.y) for p in live.material_check.remaining_outline)
        observed = []
        real_curved_skin = owner._formed_curved_skin

        def traced_curved_skin(patch, *args, **kwargs):
            observed.append((patch, kwargs))
            assert patch.difference(verified_v.buffer(1e-7)).is_empty
            assert kwargs["thickness"] == spec.thickness
            assert kwargs["allowance"] > 0
            assert kwargs["inner_r"] == pytest.approx(spec.thickness)
            return real_curved_skin(patch, *args, **kwargs)

        monkeypatch.setattr(owner, "_formed_curved_skin", traced_curved_skin)
        calculated = owner.project_v_miter_factory_radius_ba_default_check(
            spec, render, "bottom_left", live.ideal, live.material_check,
            live.factory_precut_fold_check,
            *actuals, *roles,
            live.trial_defaults, live.factory_mother_check,
        )
        assert len(observed) >= 2
        assert calculated.geometry_model.startswith("FACTORY_PROVEN_POST_V_R_BA")
        assert calculated.sharp_t_surface_interference_pairs >= 0
        assert calculated.curved_t_surface_interference_pairs >= 0
        assert calculated.curved_t_volume_status.endswith("UNCERTIFIED")
        assert tuple(render.scene.primitives) == original
    finally:
        _destroy(root, app)


def test_gui_has_explicit_engine_only_curved_trial_button():
    from pathlib import Path
    source = (Path(__file__).parents[1] /
              "gui_modules/parts/panels/assembly_corner.py").read_text(encoding="utf-8")
    assert "計算預設 R/BA／T（實體 CHECK）" in source
    assert "command=host.run_v_miter_default_radius_ba_check" in source
    assert "run_radius_ba_trial=(" in source
    assert "preset = live.trial_defaults" in source
    assert "project_v_miter_radius_ba_full_sheet_check" not in source
    assert "不含 R/BA" in source
