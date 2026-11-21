"""#3317 declared R/BA/R-hole dimensions use the *real* Factory material.

These numbers are SYNTHETIC TEST INPUTS, not actual shop measurements.
This cannot qualify production CUTTING/BEND/MARKING/DXF or shop fit.
"""
from __future__ import annotations

from dataclasses import replace
import math

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry_core import GeometryError
from ae_engine.v_miter_corner_source import VMiterReliefMode
from ae_engine.v_miter_factory_relief_check import (
    project_v_miter_factory_bottom_relief_default_check,
)
from ae_engine.v_miter_factory_radius_ba_check import (
    project_v_miter_factory_radius_ba_default_check,
)
from ae_engine.v_miter_material_trial import _single_source_material
from ae_engine.v_miter_operator_gui_check import _physical_corner_bends


def _real_door():
    import tkinter as tk
    import gui

    root = tk.Tk()
    app = gui.BoxCalculatorGUI(root)
    app.baseline_var.set("自訂")
    app.workspace_controller.set_active_part("door")
    app.select_manual_corner("bottom_left")
    app.set_v_miter_gui_check_choice()
    snap = app._make_original_fold_designer_snapshot()
    spec, _ = app._fold_designer_part_spec_from_payload("door", snap)
    render = app._query_fold_designer_render_data("door", snap)
    live = api.project_operator_v_miter_live_corner_check(spec, render, "bottom_left")
    return root, app, spec, render, live


def _close(root, app):
    designer = getattr(app, "fold_designer_app", None)
    if designer is not None:
        try:
            designer.root.destroy()
        except Exception:
            pass
    root.destroy()


def _sources(spec, render, live):
    material = _single_source_material(render.scene)
    x, y, _, _, _, _, real_x, real_y = _physical_corner_bends(
        render.scene, material, "bottom_left",
    )
    stations = (x, y) if live.first_bend_axis == "x" else (y, x)
    actual = (real_x, real_y) if live.first_bend_axis == "x" else (real_y, real_x)
    return (*actual, *stations)


def _declared(spec, live, mode):
    t = spec.thickness
    return api.VMiterFactoryMeasuredInputs(
        part_key="door", corner_key="bottom_left",
        thickness_mm=t,
        second_fold_angle_deg=live.second_fold_angle_deg,
        relief_mode=VMiterReliefMode(mode),
        relief_dimension_mm=t * (1.0 if mode == "ROUND_R" else 2.0),
        first_inner_radius_mm=t,
        second_inner_radius_mm=t,
        first_bend_allowance_mm=(math.pi / 2) * 1.33 * t,
        second_bend_allowance_mm=math.radians(live.second_fold_angle_deg) * 1.33 * t,
        measurement_reference="SYNTHETIC_TEST_ONLY_NOT_SHOP_EVIDENCE",
    )


@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_actual_door_factory_source_accepts_declared_geometry_without_releasing_dxf(mode):
    root, app, spec, render, live = _real_door()
    try:
        original_primitives = tuple(render.scene.primitives)
        measured = _declared(spec, live, mode)
        # R/hole selection is physically part of the ideal provenance,
        # not a string silently changed on an existing 90-degree source.
        choice = api.project_operator_v_miter_live_corner_check(
            spec, render, "bottom_left", relief_mode=mode,
        )
        actual_first, actual_second, station_first, station_second = (
            _sources(spec, render, choice)
        )
        relief = project_v_miter_factory_bottom_relief_default_check(
            spec, render, "bottom_left", choice.ideal,
            choice.material_check, choice.factory_precut_fold_check,
            actual_first, actual_second, measured, choice.factory_mother_check,
        )
        result = project_v_miter_factory_radius_ba_default_check(
            spec, render, "bottom_left", choice.ideal,
            choice.material_check, choice.factory_precut_fold_check,
            actual_first, actual_second, station_first, station_second,
            measured, choice.factory_mother_check, relief_check=relief,
        )
        assert result.formed_source_outline == relief.corrected_remaining_outline
        assert result.first_inner_radius_mm == measured.first_inner_radius_mm
        assert result.second_bend_allowance_mm == measured.second_bend_allowance_mm
        assert result.first_curved_skin_triangles and result.second_curved_skin_triangles
        assert result.first_thick_solid_triangles and result.second_thick_solid_triangles
        assert result.manufacturing_status == "V_MITER_FACTORY_R_BA_MEASURED_INPUT_UNCERTIFIED"
        assert tuple(render.scene.primitives) == original_primitives
        assert api.VMiterFactoryMeasuredInputs is not None
        from ae_engine import VMiterFactoryMeasuredInputs as RootInputs
        assert RootInputs is api.VMiterFactoryMeasuredInputs
        # The normal export must still refuse until real fit/relief/shop
        # calibration and certified manufacture are *actually* proved.
        with pytest.raises(GeometryError, match="CHECK_ONLY_UNCERTIFIED"):
            api.require_no_operator_v_miter_gui_check_for_export({
                "v_miter_gui_check_corners": {
                    "door": {"bottom_left": "V_MITER_CHECK"}
                }
            })
    finally:
        _close(root, app)


def test_factory_measurement_cannot_be_reused_for_wrong_part_corner_or_thickness():
    root, app, spec, render, live = _real_door()
    try:
        measured = _declared(spec, live, "ROUND_R")
        api.require_v_miter_factory_measurement_source(
            measured, spec, "bottom_left", live.ideal,
        )
        for stale in (
            replace(measured, corner_key="bottom_right"),
            replace(measured, thickness_mm=measured.thickness_mm * 1.01),
            replace(measured, second_fold_angle_deg=120.0,
                    second_bend_allowance_mm=math.radians(120) * 1.33 * spec.thickness),
        ):
            with pytest.raises(GeometryError, match="MEASUREMENT_SOURCE_CHANGED"):
                api.require_v_miter_factory_measurement_source(
                    stale, spec, "bottom_left", live.ideal,
                )
        with pytest.raises(GeometryError, match="MEASUREMENT_REFERENCE_REQUIRED"):
            replace(measured, measurement_reference=" ")
        with pytest.raises(GeometryError, match="MEASUREMENT_FIRST_BA_INVALID"):
            replace(measured, first_bend_allowance_mm=-1.0)
        with pytest.raises(GeometryError, match="MEASUREMENT_R_BA_INCONSISTENT"):
            replace(measured, first_bend_allowance_mm=measured.first_inner_radius_mm * .01)
        with pytest.raises(GeometryError, match="MEASUREMENT_RELIEF_MODE_INVALID"):
            replace(measured, relief_mode="ROUND_R")
    finally:
        _close(root, app)


def test_declared_relief_dimension_is_not_forced_to_generic_one_t(monkeypatch):
    root, app, spec, render, live = _real_door()
    try:
        import ae_engine.v_miter_factory_relief_check as owner

        measured = replace(_declared(spec, live, "ROUND_R"),
                           relief_dimension_mm=spec.thickness * .9)
        old = owner._rounded_v_notch_polygon
        observed = []

        def inspect(apex, first, second, arc, radius):
            observed.append(radius)
            return old(apex, first, second, arc, radius)

        monkeypatch.setattr(owner, "_rounded_v_notch_polygon", inspect)
        actual_first, actual_second, _, _ = _sources(spec, render, live)
        relief = owner.project_v_miter_factory_bottom_relief_default_check(
            spec, render, "bottom_left", live.ideal,
            live.material_check, live.factory_precut_fold_check,
            actual_first, actual_second, measured, live.factory_mother_check,
        )
        assert observed == [pytest.approx(.9 * spec.thickness)]
        assert relief.relief_dimension_mm == pytest.approx(.9 * spec.thickness)
        assert relief.manufacturing_status.endswith("UNCERTIFIED")
    finally:
        _close(root, app)


@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_factory_first_edge_trim_uses_same_measured_source_for_2d_and_3d(mode):
    """A bounded one-sided correction is a physically sourced CHECK only.

    This exercise uses SYNTHETIC TEST VALUES. No machine calibration, seam
    clearance verdict, production CornerType or manufacturing DXF is granted.
    """
    from shapely.geometry import Polygon

    root, app, spec, render, live = _real_door()
    try:
        choice = api.project_operator_v_miter_live_corner_check(
            spec, render, "bottom_left", relief_mode=mode,
        )
        first_real, second_real, first_station, second_station = (
            _sources(spec, render, choice)
        )
        declared = _declared(spec, choice, mode)
        relief = project_v_miter_factory_bottom_relief_default_check(
            spec, render, "bottom_left", choice.ideal,
            choice.material_check, choice.factory_precut_fold_check,
            first_real, second_real, declared, choice.factory_mother_check,
        )
        def project(trim, inputs=declared, source_relief=relief):
            return project_v_miter_factory_radius_ba_default_check(
                spec, render, "bottom_left", choice.ideal,
                choice.material_check, choice.factory_precut_fold_check,
                first_real, second_real, first_station, second_station,
                inputs, choice.factory_mother_check,
                relief_check=source_relief,
                first_edge_trim_mm=trim,
            )
        untrimmed = project(0)
        corrected = project(0.1)
        assert untrimmed.formed_source_outline == relief.corrected_remaining_outline
        assert corrected.first_edge_trim_mm == pytest.approx(0.1)
        assert corrected.additional_source_removed_area_mm2 > 0
        assert corrected.trim_application_status.endswith("APPLIED_UNCERTIFIED")
        prior = Polygon((p.x, p.y) for p in relief.corrected_remaining_outline)
        after = Polygon((p.x, p.y) for p in corrected.formed_source_outline)
        assert after.is_valid and not after.interiors
        assert after.difference(prior).area == pytest.approx(0, abs=1e-6)
        assert prior.area - after.area == pytest.approx(
            corrected.additional_source_removed_area_mm2, abs=1e-5,
        )
        assert corrected.first_thick_solid_triangles
        assert corrected.second_thick_solid_triangles
        assert corrected.manufacturing_status.endswith("UNCERTIFIED")
        with pytest.raises(GeometryError, match="MEASURED_SOURCE_REQUIRED"):
            project_v_miter_factory_radius_ba_default_check(
                spec, render, "bottom_left", choice.ideal,
                choice.material_check, choice.factory_precut_fold_check,
                first_real, second_real, first_station, second_station,
                choice.trial_defaults, choice.factory_mother_check,
                relief_check=choice.factory_bottom_relief_check,
                first_edge_trim_mm=0.1,
            )
        with pytest.raises(GeometryError, match="RELIEF_SOURCE_REQUIRED"):
            project(0.1, source_relief=None)
        for invalid in (-0.1, float("nan"), float("inf"), True, "0.1"):
            with pytest.raises(GeometryError, match="FIRST_EDGE_TRIM_INVALID"):
                project(invalid)
        with pytest.raises(GeometryError, match="CHECK_ONLY_UNCERTIFIED"):
            api.require_no_operator_v_miter_gui_check_for_export({
                "v_miter_gui_check_corners": {
                    "door": {"bottom_left": "V_MITER_CHECK"},
                }
            })
    finally:
        _close(root, app)
