"""#3317: one verified Factory R/hole material source feeds 2D and curved R/BA/T 3D.

No made-up source stock, no false 2D->3D parity or factory machining approval.
"""
from __future__ import annotations

from dataclasses import replace

import pytest
from shapely.geometry import Polygon

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry_core import GeometryError
from ae_engine.v_miter_factory_radius_ba_check import (
    project_v_miter_factory_radius_ba_default_check,
)
from ae_engine.v_miter_material_trial import _single_source_material
from ae_engine.v_miter_operator_gui_check import _physical_corner_bends


def _real_gui_source(part_key):
    import tkinter as tk
    import gui
    root = tk.Tk()
    app = gui.BoxCalculatorGUI(root)
    app.baseline_var.set("自訂")
    app.workspace_controller.set_active_part(part_key)
    app.select_manual_corner("bottom_left")
    app.set_v_miter_gui_check_choice()
    snap = app._make_original_fold_designer_snapshot()
    spec, _ = app._fold_designer_part_spec_from_payload(part_key, snap)
    render = app._query_fold_designer_render_data(part_key, snap)
    return root, app, spec, render


def _close(root, app):
    designer = getattr(app, "fold_designer_app", None)
    if designer is not None:
        try:
            designer.root.destroy()
        except Exception:
            pass
    root.destroy()


@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
@pytest.mark.parametrize("part_key", ("door", "head"))
def test_gui_factory_rba_curved_mesh_uses_exact_same_relief_2d_source(part_key, mode):
    root, app, spec, render = _real_gui_source(part_key)
    try:
        original = tuple(render.scene.primitives)
        live = api.project_operator_v_miter_live_corner_check(
            spec, render, "bottom_left", relief_mode=mode,
            run_radius_ba_trial=True,
        )
        relief = live.factory_bottom_relief_check
        assert relief is not None, live.factory_bottom_relief_failure
        # An unmodelled/malformed real source must surface a failure, never
        # fall back to the previous sharp 2D or report a zero collision.
        assert live.factory_radius_ba_check is not None, live.factory_radius_ba_failure
        curved = live.factory_radius_ba_check
        assert curved.manufacturing_status.endswith("UNCERTIFIED")
        assert curved.relief_application_status == (
            "FACTORY_R_BA_SOURCE_RELIEF_APPLIED_UNCERTIFIED"
        )
        assert curved.formed_source_outline == relief.corrected_remaining_outline
        assert curved.sharp_t_surface_interference_pairs >= 0
        assert curved.curved_t_surface_interference_pairs >= 0
        assert curved.first_curved_skin_triangles
        assert curved.second_curved_skin_triangles
        assert curved.first_thick_solid_triangles
        assert curved.second_thick_solid_triangles
        assert all(item.layer in {"DATUM", "CHECK"}
                   for item in live.full_sheet_check_scene.primitives)
        projected = [item for item in live.full_sheet_check_scene.primitives
                     if getattr(item, "semantic_id", None) ==
                     "v_miter_engine_factory_r_or_hole_uncertified"]
        assert len(projected) == 1
        assert projected[0].points == curved.formed_source_outline
        assert tuple(render.scene.primitives) == original
        with pytest.raises(GeometryError, match="CHECK_ONLY_UNCERTIFIED"):
            api.require_no_operator_v_miter_gui_check_for_export({
                "v_miter_gui_check_corners": {
                    part_key: {"bottom_left": "V_MITER_CHECK"}
                }
            })
    finally:
        _close(root, app)


def test_curved_factory_material_witness_rejects_stale_or_forged_relief():
    root, app, spec, render = _real_gui_source("door")
    try:
        live = api.project_operator_v_miter_live_corner_check(
            spec, render, "bottom_left", relief_mode="ROUND_R",
        )
        material = _single_source_material(render.scene)
        x, y, _, _, _, _, real_x, real_y = _physical_corner_bends(
            render.scene, material, "bottom_left"
        )
        first, second = (
            (x, y) if live.first_bend_axis == "x" else (y, x)
        )
        real_first, real_second = (
            (real_x, real_y) if live.first_bend_axis == "x"
            else (real_y, real_x)
        )
        args = (
            spec, render, "bottom_left", live.ideal, live.material_check,
            live.factory_precut_fold_check,
            real_first, real_second, first, second,
            live.trial_defaults, live.factory_mother_check,
        )
        assert live.factory_bottom_relief_check is not None
        forged = replace(live.factory_bottom_relief_check,
                         corrected_remaining_area_mm2=0.0)
        with pytest.raises(GeometryError, match="RELIEF_SOURCE_CHANGED"):
            project_v_miter_factory_radius_ba_default_check(
                *args, relief_check=forged,
            )
        with pytest.raises(GeometryError, match="RELIEF_TYPES_INVALID"):
            project_v_miter_factory_radius_ba_default_check(
                *args, relief_check="ROUND_R",
            )
    finally:
        _close(root, app)


@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_engine_cylindrical_faces_stay_inside_source_backed_2d_relief(mode, monkeypatch):
    import ae_engine.v_miter_factory_radius_ba_check as owner

    root, app, spec, render = _real_gui_source("door")
    try:
        actual = api.project_operator_v_miter_live_corner_check(
            spec, render, "bottom_left", relief_mode=mode,
        )
        material = _single_source_material(render.scene)
        x, y, _, _, _, _, real_x, real_y = _physical_corner_bends(
            render.scene, material, "bottom_left"
        )
        first, second = (x, y) if actual.first_bend_axis == "x" else (y, x)
        real_first, real_second = (
            (real_x, real_y) if actual.first_bend_axis == "x"
            else (real_y, real_x)
        )
        corrected = Polygon(
            (p.x, p.y) for p in
            actual.factory_bottom_relief_check.corrected_remaining_outline
        )
        observed = []
        original = owner._formed_curved_skin

        def proven_source_patch(patch, *args, **kwargs):
            observed.append(patch.area)
            assert patch.area > 0
            assert patch.difference(corrected.buffer(1e-7)).is_empty
            return original(patch, *args, **kwargs)

        monkeypatch.setattr(owner, "_formed_curved_skin", proven_source_patch)
        result = owner.project_v_miter_factory_radius_ba_default_check(
            spec, render, "bottom_left", actual.ideal,
            actual.material_check, actual.factory_precut_fold_check,
            real_first, real_second, first, second, actual.trial_defaults,
            actual.factory_mother_check,
            relief_check=actual.factory_bottom_relief_check,
        )
        assert len(observed) >= 2
        assert result.formed_source_outline == (
            actual.factory_bottom_relief_check.corrected_remaining_outline
        )
    finally:
        _close(root, app)
