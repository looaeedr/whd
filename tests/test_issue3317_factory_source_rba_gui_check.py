"""#3317: actual GUI fifth V option can opt into source-bound R/BA/T CHECK.

The generic R/K/relief defaults never become Factory calibration or CNC
authorization. Only an explicit GUI trial may run the costly curved mesh.
"""
from __future__ import annotations

from dataclasses import replace
import math
from types import SimpleNamespace

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
            spec, render, "bottom_left",
        )
        assert no_trial.factory_true_t_check is not None
        assert no_trial.factory_radius_ba_check is None
        assert no_trial.factory_radius_ba_failure is None
        calculated = api.project_operator_v_miter_live_corner_check(
            spec, render, "bottom_left", run_radius_ba_trial=True,
        )
        assert calculated.factory_true_t_check is not None
        assert calculated.trial_defaults is not None
        assert calculated.trial_defaults.first_inner_radius_mm == pytest.approx(spec.thickness)
        assert calculated.trial_defaults.first_bend_allowance_mm == pytest.approx(
            math.pi / 2 * 1.33 * spec.thickness,
        )
        # Real factory/tolerance/mesh may reject a default trial; a genuine
        # rejection must be surfaced, not silently projected as 0 collisions.
        if calculated.factory_radius_ba_check is None:
            assert calculated.factory_radius_ba_failure
        else:
            proposal = calculated.factory_radius_ba_check
            assert proposal.manufacturing_status.endswith("UNCERTIFIED")
            assert proposal.full_sheet.manufacturing_status.endswith("UNCERTIFIED")
            assert proposal.full_sheet.trial.trimmed_surface_interference_pairs == 0
            assert proposal.first_formed_perimeter_edges
            assert proposal.second_formed_perimeter_edges
            assert any(getattr(row, "semantic_id", None) ==
                       "v_miter_engine_r_ba_uncertified_only"
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
            spec, render, "bottom_left",
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


def test_factory_rba_stage_reuses_proven_source_and_calls_real_solver(monkeypatch):
    """Prove the EXACT solver receives Factory source stock, not GUI geometry."""
    import ae_engine.v_miter_factory_radius_ba_check as owner

    root, app, spec, render = _real_factory_v_gui()
    try:
        live = api.project_operator_v_miter_live_corner_check(
            spec, render, "bottom_left",
        )
        mat = _single_source_material(render.scene)
        x, y, _, _, _, _, real_x, real_y = _physical_corner_bends(
            render.scene, mat, "bottom_left",
        )
        roles = (x, y) if live.first_bend_axis == "x" else (y, x)
        actuals = (real_x, real_y) if live.first_bend_axis == "x" else (real_y, real_x)
        source = tuple(render.scene.primitives)
        observed = []

        def checked_solver(scene, first, second, **params):
            observed.append((scene, first, second, params))
            assert scene is not render.scene
            assert first in scene.primitives and second in scene.primitives
            mother = Polygon((p.x, p.y) for p in live.material_check.remaining_outline).union(
                Polygon((p.x, p.y) for p in live.material_check.removed_corner_outline),
            )
            assert _single_source_material(scene).symmetric_difference(mother).area < 1e-6
            assert params["thickness_mm"] == spec.thickness
            assert params["first_inner_radius_mm"] == spec.thickness
            assert params["second_bend_allowance_mm"] == pytest.approx(
                live.trial_defaults.second_bend_allowance_mm,
            )
            assert params["max_permitted_edge_trim_mm"] > 0
            points = tuple(type(roles[0].p1)(float(x), float(y))
                           for x, y in mother.exterior.coords)
            return SimpleNamespace(
                corrected_check_outline=points,
                trial=SimpleNamespace(
                    first_formed_skin_triangles=(((0., 0., 0.), (1., 0., 0.), (0., 1., 0.)),),
                    second_formed_skin_triangles=(((0., 0., 1.), (1., 0., 1.), (0., 1., 1.)),),
                ),
            )

        monkeypatch.setattr(owner, "project_v_miter_radius_ba_full_sheet_check", checked_solver)
        output = owner.project_v_miter_factory_radius_ba_default_check(
            spec, render, "bottom_left", live.ideal, live.material_check,
            live.factory_precut_fold_check,
            *actuals, *roles,
            live.trial_defaults, live.factory_mother_check,
        )
        assert len(observed) == 1
        assert output.manufacturing_status.endswith("UNCERTIFIED")
        assert tuple(render.scene.primitives) == source
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
