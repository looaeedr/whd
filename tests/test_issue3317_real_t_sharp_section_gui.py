"""#3317: existing PartSpec T enters strict sharp-fold local 3D witness.

The 3D bisector is a CHECK-only cross-section, never a full physical seam,
relief design, neutral-axis calibration, CUTTING or production allowance.
"""
import tkinter as tk

import pytest

import gui
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_drawing import DrawingScene, LinePrimitive
from ae_engine.sheetmetal_geometry_core import GeometryError, Vec2


@pytest.mark.parametrize("part_key", ("door", "head", "tail"))
def test_real_gui_t_witness_only_if_original_physical_bend_continuous(part_key):
    root = tk.Tk()
    app = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("自訂")
        app.workspace_controller.set_active_part(part_key)
        app.select_manual_corner("bottom")
        app.set_v_miter_gui_check_choice()
        result = app._project_v_miter_gui_check_for_corner(part_key, "bottom")
        assert result.material_check is not None
        assert result.full_sheet_check_scene is not None
        assert all(p.layer in {"CHECK", "DATUM"}
                   for p in result.full_sheet_check_scene.primitives)
        original_gap = max(
            result.first_bend_source_gap_mm,
            result.second_bend_source_gap_mm,
        )
        if original_gap > 1e-7:
            # EndCap C01 old cuts shorten original BEND; a detached trial
            # station MUST NOT establish a false manufactured T-contact.
            assert result.sharp_t_witness is None
            assert "PHYSICAL_GAP" in result.sharp_t_failure
        else:
            assert result.sharp_t_witness is not None, result.sharp_t_failure
            witness = result.sharp_t_witness
            assert witness.thickness_mm > 0
            assert witness.thickness_mm == pytest.approx(
                app._fold_designer_part_spec_from_payload(
                    part_key, app._make_original_fold_designer_snapshot(),
                )[0].thickness
            )
            assert witness.cross_section_width_mm > 0
            assert witness.manufacturing_status.endswith("UNCERTIFIED")
            assert witness.bounded.needs_independent_material_extension_evidence is False
        canvas = app.v_miter_check_3d_preview_canvas
        assert canvas is not None
        assert len(canvas.find_all()) > 1
    finally:
        if app is not None:
            designer = getattr(app, "fold_designer_app", None)
            if designer is not None:
                try:
                    designer.root.destroy()
                except Exception:
                    pass
        root.destroy()


@pytest.mark.parametrize("angle", (90, 120))
def test_existing_engine_t_bisector_uses_explicit_t_without_r_or_ba(angle):
    first = LinePrimitive(Vec2(-100, 0), Vec2(0, 0), "BEND")
    second = LinePrimitive(Vec2(0, 0), Vec2(0, 100), "BEND")
    source = DrawingScene([first, second])
    result = api.project_v_miter_sharp_thickness_witness(
        source, first, second,
        thickness_mm=2, first_flange_height_mm=20,
        second_flange_height_mm=30, second_fold_angle_deg=angle,
        relief_mode="ROUND_R",
    )
    assert result.thickness_mm == 2
    assert result.cross_section_width_mm > 0
    assert result.manufacturing_status == "V_MITER_SHARP_THICKNESS_UNCERTIFIED"


def test_missing_real_60_degree_crease_cannot_authorize_t_bisector():
    first = LinePrimitive(Vec2(-100, 0), Vec2(0, 0), "BEND")
    second = LinePrimitive(Vec2(0, 0), Vec2(0, 100), "BEND")
    source = DrawingScene([first, second])
    with pytest.raises(GeometryError, match="material extension unverified"):
        api.project_v_miter_sharp_thickness_witness(
            source, first, second, thickness_mm=2,
            first_flange_height_mm=20,
            second_flange_height_mm=30,
            second_fold_angle_deg=60, relief_mode="ROUND_R",
        )
