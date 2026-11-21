"""#3317 actual PartSpec T + verified post-V Factory Fold -> 3D collision.

No measured inside R, BA, factory gap, certified bevel or production DXF
is available. These are real physical-thickness CHECK witness tests, never
acceptance tests that authorize an unverified fifth CornerType.
"""
from __future__ import annotations

from dataclasses import replace
import math

import pytest
from shapely.geometry import Polygon

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry_core import GeometryError
from ae_engine.v_miter_factory_true_t_check import (
    project_v_miter_factory_post_v_true_t_check,
)
from ae_engine.v_miter_material_trial import _single_source_material
from ae_engine.v_miter_operator_gui_check import _physical_corner_bends


def _real_selected_live(part_key, corner):
    import tkinter as tk
    import gui

    root = tk.Tk()
    app = gui.BoxCalculatorGUI(root)
    app.baseline_var.set("自訂")
    app.workspace_controller.set_active_part(part_key)
    app.select_manual_corner(corner)
    app.set_v_miter_gui_check_choice()
    snapshot = app._make_original_fold_designer_snapshot()
    spec, _ = app._fold_designer_part_spec_from_payload(part_key, snapshot)
    original = app._query_fold_designer_render_data(part_key, snapshot)
    live = app._project_v_miter_gui_check_for_corner(part_key, corner)
    return root, app, spec, original, live


def _close(root, app):
    designer = getattr(app, "fold_designer_app", None)
    if designer is not None:
        try:
            designer.root.destroy()
        except Exception:
            pass
    root.destroy()


@pytest.mark.parametrize("part_key", ("door", "head", "tail"))
@pytest.mark.parametrize("corner", ("bottom_left", "bottom_right"))
def test_real_gui_factory_v_reconstructs_true_t_mesh_and_detects_collisions(
    part_key, corner,
):
    root, app, spec, original, live = _real_selected_live(part_key, corner)
    try:
        before = tuple(original.scene.primitives)
        assert live.factory_precut_fold_check is not None
        assert live.material_check is not None
        solid = live.factory_true_t_check
        assert solid is not None, live.factory_true_t_failure
        assert solid.manufacturing_status.endswith("UNCERTIFIED")
        assert solid.thickness_mm == pytest.approx(spec.thickness)
        assert solid.thickness_mm > 0
        assert solid.first_source_flange_area_mm2 > 0
        assert solid.second_source_flange_area_mm2 > 0
        assert solid.first_source_component_count >= 1
        assert solid.second_source_component_count >= 1
        assert solid.first_formed_skin_triangles
        assert solid.second_formed_skin_triangles
        assert solid.first_thick_solid_triangles
        assert solid.second_thick_solid_triangles
        assert solid.first_formed_perimeter_edges
        assert solid.second_formed_perimeter_edges
        assert solid.surface_interference_pair_count >= 0
        for mesh in (solid.first_thick_solid_triangles,
                     solid.second_thick_solid_triangles):
            for triangle in mesh:
                assert len(triangle) == 3
                assert all(math.isfinite(c) for point in triangle for c in point)
        for edge in (*solid.first_formed_perimeter_edges,
                     *solid.second_formed_perimeter_edges):
            assert all(math.isfinite(c) for point in edge for c in point)
        assert solid.first_source_fold_max_axial_mm > 0
        assert solid.second_source_fold_max_axial_mm > 0
        assert tuple(original.scene.primitives) == before
        assert all(row.layer in {"CHECK", "DATUM"}
                   for row in live.full_sheet_check_scene.primitives)
        assert len(app.v_miter_check_3d_preview_canvas.find_all()) > 5
        # A missing physical relief R/BA cannot certify a zero-hit mesh.
        assert "零R" in app.manual_corner_param_summary.cget("text")
        assert "未認證" in app.manual_corner_param_summary.cget("text")
    finally:
        _close(root, app)


def test_factory_true_t_rejects_forged_thickness_and_unproven_fold():
    root, app, spec, render, live = _real_selected_live("door", "bottom_left")
    try:
        source = _single_source_material(render.scene)
        x_virtual, y_virtual, _, _, _, _, x_real, y_real = (
            _physical_corner_bends(render.scene, source, "bottom_left")
        )
        assert live.factory_true_t_check is not None, live.factory_true_t_failure
        with pytest.raises(GeometryError, match="ACTUAL_THICKNESS_MISMATCH"):
            project_v_miter_factory_post_v_true_t_check(
                replace(spec, thickness=spec.thickness + 1), render,
                "bottom_left", live.ideal, live.material_check,
                live.factory_precut_fold_check, x_real, y_real,
                x_virtual, y_virtual, live.factory_mother_check,
            )
        forged = replace(
            live.factory_precut_fold_check,
            first_additional_factory_fold_mm=8e9,
        )
        with pytest.raises(GeometryError, match="FOLD_PROVENANCE_MISMATCH"):
            project_v_miter_factory_post_v_true_t_check(
                spec, render, "bottom_left", live.ideal, live.material_check,
                forged, x_real, y_real, x_virtual, y_virtual,
                live.factory_mother_check,
            )
        missing = replace(
            live.material_check, source_material_area_mm2=1,
        )
        with pytest.raises(GeometryError, match="SOURCE_AREA_MISMATCH|AREA_MISMATCH"):
            project_v_miter_factory_post_v_true_t_check(
                spec, render, "bottom_left", live.ideal, missing,
                live.factory_precut_fold_check, x_real, y_real,
                x_virtual, y_virtual, live.factory_mother_check,
            )
    finally:
        _close(root, app)
