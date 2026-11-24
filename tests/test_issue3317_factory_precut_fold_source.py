"""#3317 authoritative pre-corner Factory Fold clipped to the new V sheet.

Not a manufacturing BEND: the old C01/C04 FinalScene has shortened BEND
geometry, but the Engine's independent Factory topology still knows the
source axes. Both the source stock and the old BEND must be checked first.
"""
from __future__ import annotations

from dataclasses import replace
import math

import ezdxf
import pytest
from shapely.geometry import LineString, Polygon

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_geometry_core import GeometryError
from ae_engine.v_miter_factory_fold_check import (
    project_v_miter_factory_precut_fold_check,
)
from ae_engine.v_miter_operator_gui_check import _physical_corner_bends
from ae_engine.v_miter_material_trial import _single_source_material


@pytest.mark.parametrize("part_key", ("door", "head", "tail"))
@pytest.mark.parametrize("corner", ("bottom_left", "bottom_right"))
def test_real_factory_precorner_bend_from_typed_spec_not_visual_straight_line(
    part_key, corner, tmp_path,
):
    import tkinter as tk
    import gui

    root = tk.Tk()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("自訂")
        app.workspace_controller.set_active_part(part_key)
        app.select_manual_corner(corner)
        app.set_v_miter_gui_check_choice()
        snapshot = app._make_original_fold_designer_snapshot()
        spec, _ = app._fold_designer_part_spec_from_payload(part_key, snapshot)
        render = app._query_fold_designer_render_data(part_key, snapshot)
        original_primitives = tuple(render.scene.primitives)
        live = app._project_v_miter_gui_check_for_corner(part_key, corner)
        checked = live.factory_precut_fold_check
        assert live.material_check is not None
        assert checked is not None, live.factory_precut_fold_failure
        assert checked.manufacturing_status.endswith("UNCERTIFIED")
        assert checked.geometry_model.startswith("FACTORY_PRE_CORNER")
        assert checked.first_original_bend_mm > 0
        assert checked.second_original_bend_mm > 0
        assert checked.first_surviving_factory_fold_mm > 0
        assert checked.second_surviving_factory_fold_mm > 0
        assert checked.first_additional_factory_fold_mm >= 0
        assert checked.second_additional_factory_fold_mm >= 0
        assert checked.first_proposed_segments
        assert checked.second_proposed_segments

        remaining = Polygon((p.x, p.y) for p in live.material_check.remaining_outline)
        geometry = (*checked.first_proposed_segments,
                    *checked.second_proposed_segments)
        assert all(p.layer == "CHECK" and p.color == 5 for p in geometry)
        for segment in geometry:
            line = LineString(((segment.p1.x, segment.p1.y),
                               (segment.p2.x, segment.p2.y)))
            assert line.length > 0
            assert remaining.buffer(1e-6).covers(line)
            assert line.difference(remaining.boundary.buffer(1e-7)).length > 0
        assert live.full_sheet_check_scene is not None
        assert tuple(x for x in live.full_sheet_check_scene.primitives
                     if getattr(x, "color", None) == 5) == geometry

        dest = tmp_path / f"{part_key}_{corner}_FOLD_CHECK_ONLY.dxf"
        api.save_v_miter_whole_sheet_check_dxf(live.full_sheet_check_scene, dest)
        reopened = tuple(ezdxf.readfile(dest).modelspace())
        proposed = tuple(e for e in reopened
                         if e.dxf.layer == "CHECK" and e.dxftype() == "LINE"
                         and e.dxf.color == 5)
        assert len(proposed) == len(geometry)
        for entity, candidate in zip(proposed, geometry):
            assert (entity.dxf.start.x, entity.dxf.start.y) == pytest.approx(
                (candidate.p1.x, candidate.p1.y)
            )
            assert (entity.dxf.end.x, entity.dxf.end.y) == pytest.approx(
                (candidate.p2.x, candidate.p2.y)
            )
        assert not any(e.dxf.layer in {"CUTTING", "BEND", "MARKING"}
                       for e in reopened)
        assert tuple(render.scene.primitives) == original_primitives

        # The factory reprojection must reject even a nominally similar
        # PartSpec whose true Fold changed after the original FinalScene.
        source = _single_source_material(render.scene)
        info = _physical_corner_bends(render.scene, source, corner)
        real_x, real_y = info[-2:]
        altered = replace(spec, fold_left=spec.fold_left + 1)
        with pytest.raises(GeometryError, match="DIFFERS_FROM_FACTORY"):
            project_v_miter_factory_precut_fold_check(
                altered, render, corner, live.material_check,
                real_x, real_y, live.factory_mother_check,
            )
    finally:
        if app is not None:
            designer = getattr(app, "fold_designer_app", None)
            if designer is not None:
                try:
                    designer.root.destroy()
                except Exception:
                    pass
        root.destroy()


def test_no_factory_cut_contour_can_sneak_missing_stock_into_fold_witness():
    """Copied/bent source objects and forged stock never grant a new BEND."""
    import tkinter as tk
    import gui

    root = tk.Tk()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("自訂")
        app.workspace_controller.set_active_part("door")
        app.select_manual_corner("bottom")
        app.set_v_miter_gui_check_choice()
        snapshot = app._make_original_fold_designer_snapshot()
        spec, _ = app._fold_designer_part_spec_from_payload("door", snapshot)
        render = app._query_fold_designer_render_data("door", snapshot)
        source = _single_source_material(render.scene)
        original = _physical_corner_bends(render.scene, source, "bottom_left")
        real_x, real_y = original[-2:]
        live = app._project_v_miter_gui_check_for_corner("door", "bottom")
        assert live.material_check is not None
        from ae_engine.sheetmetal_drawing import LinePrimitive
        forged = LinePrimitive(real_x.p1, real_x.p2, "BEND")
        with pytest.raises(GeometryError, match="BEND_IDENTITY"):
            project_v_miter_factory_precut_fold_check(
                spec, render, "bottom_left", live.material_check,
                forged, real_y, live.factory_mother_check,
            )
        false_source = replace(live.material_check,
                               source_material_area_mm2=1)
        with pytest.raises(GeometryError, match="AREA_MISMATCH"):
            project_v_miter_factory_precut_fold_check(
                spec, render, "bottom_left", false_source,
                real_x, real_y, live.factory_mother_check,
            )
    finally:
        if app is not None:
            designer = getattr(app, "fold_designer_app", None)
            if designer is not None:
                try:
                    designer.root.destroy()
                except Exception:
                    pass
        root.destroy()
