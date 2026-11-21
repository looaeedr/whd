"""#3317: Factory-authenticated V source R or circular hole CHECK only.

The actual V rays reach the real original CUTTING perimeter, which differs
from the shorter ideal formed seam ray. This trial must preserve exactly one
original sheet, never claim 3D relief or manufacturing permissions.
"""
from __future__ import annotations

from dataclasses import replace

import ezdxf
import pytest
from shapely.geometry import Polygon

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry_core import GeometryError
from ae_engine.v_miter_corner_source import VMiterReliefMode
from ae_engine.v_miter_factory_relief_check import (
    project_v_miter_factory_bottom_relief_default_check,
)
from ae_engine.v_miter_material_trial import _single_source_material
from ae_engine.v_miter_operator_gui_check import _physical_corner_bends


def _actual_gui(part_key, corner):
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


def _close(root, app):
    designer = getattr(app, "fold_designer_app", None)
    if designer is not None:
        try:
            designer.root.destroy()
        except Exception:
            pass
    root.destroy()


@pytest.mark.parametrize("part_key", ("door", "head", "tail"))
@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_actual_factory_v_default_relief_polygon_matches_stock_and_reopens_check_dxf(
    part_key, mode, tmp_path,
):
    root, app, spec, render = _actual_gui(part_key, "bottom_left")
    try:
        originals = tuple(render.scene.primitives)
        live = api.project_operator_v_miter_live_corner_check(
            spec, render, "bottom_left", relief_mode=mode,
        )
        relief = live.factory_bottom_relief_check
        assert relief is not None, live.factory_bottom_relief_failure
        assert relief.manufacturing_status.endswith("UNCERTIFIED")
        assert relief.relief_mode is VMiterReliefMode(mode)
        assert relief.relief_t_factor == (1 if mode == "ROUND_R" else 2)
        assert relief.relief_dimension_mm == pytest.approx(
            spec.thickness * (1 if mode == "ROUND_R" else 2)
        )
        assert relief.relief_radius_mm == pytest.approx(spec.thickness)
        assert relief.source_original_area_mm2 == pytest.approx(
            relief.corrected_remaining_area_mm2 + relief.corrected_removed_area_mm2
        )
        stock = Polygon((p.x, p.y) for p in relief.corrected_remaining_outline)
        removed = Polygon((p.x, p.y) for p in relief.corrected_removed_outline)
        original_sharp = Polygon((p.x, p.y) for p in live.material_check.remaining_outline)
        original_mother = original_sharp.union(
            Polygon((p.x, p.y) for p in live.material_check.removed_corner_outline)
        )
        assert stock.is_valid and not stock.interiors and stock.area > 0
        assert removed.is_valid and not removed.interiors and removed.area > 0
        assert stock.difference(original_mother.buffer(1e-7)).is_empty
        assert removed.difference(original_mother.buffer(1e-7)).is_empty
        assert stock.intersection(removed).area == pytest.approx(0, abs=1e-6)
        if mode == "ROUND_R":
            assert relief.corrected_remaining_area_mm2 > relief.original_sharp_remaining_area_mm2
        else:
            assert relief.corrected_remaining_area_mm2 < relief.original_sharp_remaining_area_mm2
        contour = [
            row for row in live.full_sheet_check_scene.primitives
            if getattr(row, "semantic_id", None) ==
            "v_miter_engine_factory_r_or_hole_uncertified"
        ]
        assert len(contour) == 1
        assert contour[0].layer == "CHECK" and contour[0].closed
        assert contour[0].points == relief.corrected_remaining_outline
        path = tmp_path / f"{part_key}_{mode}_only_CHECK.dxf"
        api.save_v_miter_whole_sheet_check_dxf(
            live.full_sheet_check_scene, path,
        )
        entities = tuple(ezdxf.readfile(path).modelspace())
        assert entities
        assert set(row.dxf.layer for row in entities) <= {"CHECK", "DATUM"}
        assert not any(row.dxf.layer in {"CUTTING", "BEND", "MARKING"} for row in entities)
        assert tuple(render.scene.primitives) == originals
        with pytest.raises(GeometryError, match="CHECK_ONLY_UNCERTIFIED"):
            api.require_no_operator_v_miter_gui_check_for_export(
                {"v_miter_gui_check_corners": {part_key: {"bottom_left": "V_MITER_CHECK"}}}
            )
    finally:
        _close(root, app)


@pytest.mark.parametrize("mode", ("ROUND_R", "RELIEF_HOLE"))
def test_factory_relief_rejects_forged_defaults_and_old_bend_identity(mode):
    from ae_engine.sheetmetal_drawing import LinePrimitive

    root, app, spec, render = _actual_gui("door", "bottom_left")
    try:
        live = api.project_operator_v_miter_live_corner_check(
            spec, render, "bottom_left", relief_mode=mode,
        )
        material = _single_source_material(render.scene)
        virtual_x, virtual_y, _, _, _, _, real_x, real_y = _physical_corner_bends(
            render.scene, material, "bottom_left",
        )
        actuals = (
            (real_x, real_y) if live.first_bend_axis == "x" else (real_y, real_x)
        )
        args = (
            spec, render, "bottom_left", live.ideal, live.material_check,
            live.factory_precut_fold_check,
            *actuals, live.trial_defaults, live.factory_mother_check,
        )
        with pytest.raises(GeometryError, match="DEFAULTS_SOURCE_CHANGED"):
            project_v_miter_factory_bottom_relief_default_check(
                *args[:-2],
                replace(live.trial_defaults, relief_dimension_mm=999),
                live.factory_mother_check,
            )
        forged = LinePrimitive(actuals[0].p1, actuals[0].p2, "BEND")
        with pytest.raises(GeometryError, match="BEND_IDENTITY"):
            project_v_miter_factory_bottom_relief_default_check(
                spec, render, "bottom_left", live.ideal, live.material_check,
                live.factory_precut_fold_check, forged, actuals[1],
                live.trial_defaults, live.factory_mother_check,
            )
    finally:
        _close(root, app)


def test_gui_radio_switch_uses_engine_relief_choice_not_gui_geometry():
    from pathlib import Path

    root, app, spec, render = _actual_gui("door", "bottom_left")
    try:
        assert app.v_miter_relief_mode_var.get() == "ROUND_R"
        for mode in ("RELIEF_HOLE", "ROUND_R"):
            app.v_miter_relief_mode_var.set(mode)
            live = app._project_v_miter_gui_check_for_corner("door", "bottom_left")
            assert live.trial_defaults.relief_mode is VMiterReliefMode(mode)
            assert live.factory_bottom_relief_check is not None, live.factory_bottom_relief_failure
            assert live.factory_bottom_relief_check.relief_mode is VMiterReliefMode(mode)
        panel = (
            Path(__file__).parents[1] / "gui_modules/parts/panels/assembly_corner.py"
        ).read_text(encoding="utf-8")
        assert 'value="ROUND_R"' in panel
        assert '"RELIEF_HOLE"' in panel
        assert "project_v_miter_factory_bottom_relief_default_check" not in panel
        assert "math.tan(" not in panel and "math.cos(" not in panel
    finally:
        _close(root, app)
