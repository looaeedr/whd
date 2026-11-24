"""#3317 real authored EndCap Fold 60/120, not an ideal 90-degree proxy.

Use the actual GUI-selected typed PartSpec and unmodified physical FinalScene;
alter only the authored Fold's angle at the exact physical Y BEND station.
This exercises the same Engine live V polygon, Factory Fold and physical T
mesh with truly asymmetric geometry. CHECK only, never machining approval.
"""
from dataclasses import replace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.v_miter_material_trial import _single_source_material
from ae_engine.v_miter_operator_gui_check import (
    _endcap_existing_fold_angle_sources, _bound_endcap_corner_bends,
)


@pytest.mark.parametrize("part_key", ("head", "tail"))
@pytest.mark.parametrize("corner", ("bottom_left", "bottom_right"))
@pytest.mark.parametrize("requested_second_angle", (60.0, 120.0))
def test_real_head_tail_actual_fold_60_120_preserves_factory_source_and_T(
    part_key, corner, requested_second_angle,
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
        # Actual Tk entry requires the operator's first 90-degree fold.
        # This is distinct from legacy internal readonly Engine preview.
        with pytest.raises(ValueError, match="V_MITER_GUI_FIRST_BEND_REQUIRED"):
            app._project_v_miter_gui_check_for_corner(part_key, corner)
        app.v_miter_first_bend_axis_var.set("x")
        app.set_v_miter_gui_first_bend_axis()
        snap = app._make_original_fold_designer_snapshot()
        spec, _ = app._fold_designer_part_spec_from_payload(part_key, snap)
        render = app._query_fold_designer_render_data(part_key, snap)
        initial = tuple(render.scene.primitives)
        bounds = _single_source_material(render.scene).bounds
        x_profile, y_profile = _endcap_existing_fold_angle_sources(spec, part_key)
        # Real Head has Y return (ytop1) and three distinct finite BENDs.
        # Head lower corner binds "fw", not the closer return "ytop1".
        # Tail lower corner binds "ybottom1", both without hardcoded Y.
        role = "fw" if part_key == "head" else "ybottom1"
        cursor = bounds[1]
        found = []
        new_y = []
        stations = {}
        for row in y_profile:
            cursor += row.length
            stations[row.phase6_key] = cursor
            if row.phase6_key == role:
                found.append(row)
                new_y.append(replace(
                    row, angle=(
                        requested_second_angle if row.angle > 0
                        else -requested_second_angle
                    )
                ))
            else:
                new_y.append(row)
        assert len(found) == 1
        target_y = stations[role]
        assert sum(
            1 for row in render.scene.primitives
            if getattr(row, "layer", None) == "BEND"
            and hasattr(row, "p1") and abs(row.p1.y-row.p2.y) < 1e-7
            and abs(row.p1.y-target_y) < 1e-6
        ) == 1
        if part_key == "head":
            assert target_y != stations["ytop1"]
            assert any(
                abs(row.p1.y - stations["ytop1"]) < 1e-6
                for row in render.scene.primitives
                if getattr(row, "layer", None) == "BEND"
                and hasattr(row, "p1") and abs(row.p1.y-row.p2.y) < 1e-7
            )
        assert len(found) == 1
        assert abs(found[0].angle) == pytest.approx(90)
        edited = replace(
            spec, fold_profile_x=tuple(x_profile),
            fold_profile_y=tuple(new_y),
        )
        live = api.project_operator_v_miter_live_corner_check(
            edited, render, corner, first_bend_axis="x",
        )
        assert live.second_fold_angle_deg == pytest.approx(
            requested_second_angle,
        )
        assert live.second_physical_bend is next(
            row for row in render.scene.primitives
            if getattr(row, "layer", None) == "BEND"
            and hasattr(row, "p1") and abs(row.p1.y-row.p2.y) < 1e-7
            and abs(row.p1.y-target_y) < 1e-6
        )
        assert abs(live.second_signed_fold_angle_deg) == pytest.approx(requested_second_angle)
        with pytest.raises(ValueError, match="SELECTED_FIRST_BEND_NOT_90"):
            api.project_operator_v_miter_live_corner_check(
                edited, render, corner, first_bend_axis="y",
            )
        assert live.ideal.source.second_fold_angle_deg == pytest.approx(
            requested_second_angle,
        )
        assert live.material_check is not None, live.material_check_failure
        assert live.factory_precut_fold_check is not None, live.factory_precut_fold_failure
        assert live.factory_true_t_check is not None, live.factory_true_t_failure
        assert live.factory_true_t_check.thickness_mm == pytest.approx(
            spec.thickness,
        )
        assert live.factory_true_t_check.manufacturing_status.endswith("UNCERTIFIED")
        assert tuple(render.scene.primitives) == initial
    finally:
        if app is not None:
            designer = getattr(app, "fold_designer_app", None)
            if designer is not None:
                try:
                    designer.root.destroy()
                except Exception:
                    pass
        root.destroy()
