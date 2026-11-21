"""#3317 real WHD GUI->PartSpec->FinalScene->live V check (not just radio)."""
import tkinter as tk

import pytest

import gui
from ae_engine import manufacturing_api


@pytest.mark.parametrize("part_key", ("door", "head", "tail"))
def test_real_tk_physical_part_live_v_preview_from_current_fold(part_key):
    root = tk.Tk()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("自訂")
        app.workspace_controller.set_active_part(part_key)
        app.select_manual_corner("bottom")
        app.set_v_miter_gui_check_choice()

        assert app.manual_corner_type_var.get() == "V_MITER_CHECK"
        try:
            result = app._project_v_miter_gui_check_for_corner(part_key, "bottom")
        except (ValueError, TypeError) as exc:
            snapshot = app._make_original_fold_designer_snapshot()
            spec, _ = app._fold_designer_part_spec_from_payload(part_key, snapshot)
            render = app._query_fold_designer_render_data(part_key, snapshot)
            bends = [
                ((p.p1.x, p.p1.y), (p.p2.x, p.p2.y))
                for p in render.scene.primitives
                if p.layer == "BEND" and hasattr(p, "p1")
            ]
            raise AssertionError(
                f"{part_key} source={exc}; bounds={render.material.bounds}; "
                f"BEND={bends[:25]}; "
                f"X={getattr(spec, 'fold_profile_x', ())}; "
                f"Y={getattr(spec, 'fold_profile_y', ())}"
            ) from exc
        # #3317: an explicit 90-degree first bend must control X/Y,
        # including two-90-degree corners; Engine may not override it.
        snapshot = app._make_original_fold_designer_snapshot()
        spec, _ = app._fold_designer_part_spec_from_payload(part_key, snapshot)
        render = app._query_fold_designer_render_data(part_key, snapshot)
        for axis in ("x", "y"):
            selected = manufacturing_api.project_operator_v_miter_live_corner_check(
                spec, render, "bottom_left", first_bend_axis=axis,
            )
            assert selected.first_bend_axis == axis
            assert selected.second_bend_axis == ("y" if axis == "x" else "x")
            assert selected.ideal.source.first_fold_angle_deg == 90
        with pytest.raises(ValueError, match="V_MITER_GUI_FIRST_BEND_AXIS_INVALID"):
            manufacturing_api.project_operator_v_miter_live_corner_check(
                spec, render, "bottom_left", first_bend_axis="z",
            )

        assert result.part_key == part_key
        assert result.corner_key == "bottom_left"
        assert result.ideal.formed_contact_length_mm > 0
        assert all(item.layer == "CHECK" for item in result.check_scene.primitives)
        # For a known Custom factory, the Engine must reconstruct the
        # independently re-evaluated uncut mother and replace ONLY this old
        # CornerType, not stop at two ideal lines.
        assert result.material_check is not None, result.material_check_failure
        assert result.factory_mother_check is not None
        assert result.factory_mother_check.restored_corner_material_area_mm2 > 0
        assert result.factory_mother_check.source_kind.startswith("PARTSPEC_REBUILT")
        assert result.check_scene.primitives[0].closed
        assert result.material_check.removed_material_area_mm2 > 0
        assert result.material_check.remaining_material_area_mm2 > 0
        assert result.material_check.source_material_area_mm2 == pytest.approx(
            result.material_check.remaining_material_area_mm2 +
            result.material_check.removed_material_area_mm2
        )
        assert result.material_check_failure is None
        assert app.v_miter_check_3d_preview_canvas is not None
        # A rendered live source must show more than the blank/error message.
        assert len(app.corner_type_preview_canvas.find_all()) > 1
        assert len(app.v_miter_check_3d_preview_canvas.find_all()) > 1
    finally:
        if app is not None:
            designer = getattr(app, "fold_designer_app", None)
            if designer is not None:
                try:
                    designer.root.destroy()
                except Exception:
                    pass
        root.destroy()
