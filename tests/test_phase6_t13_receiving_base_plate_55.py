# -*- coding: utf-8 -*-
"""T13 Contract Tests: Receiving Base Plate 55 mm nominal shrink."""

import os
import pytest

from ae_engine.cabinet_types import receiving
from ae_engine.contracts import BasePlatePartSpec
from ae_engine.manufacturing_api import build_part_render_data


def _bounds_size(render_data):
    minx, miny, maxx, maxy = render_data.material.bounds
    return maxx - minx, maxy - miny


def test_r01_receiving_fresh_family_default_is_55_on_all_four_sides():
    snapshot = receiving.apply_family_defaults({})
    assert tuple(snapshot[key] for key in (
        "base_plate_shrink_top",
        "base_plate_shrink_bottom",
        "base_plate_shrink_left",
        "base_plate_shrink_right",
    )) == (55.0, 55.0, 55.0, 55.0)


def test_r01_receiving_nominal_800x1600_plate_resolves_to_720x1520_blank():
    spec = BasePlatePartSpec(
        width=800.0, height=1600.0, thickness=2.0,
        shrink_top=55.0, shrink_bottom=55.0,
        shrink_left=55.0, shrink_right=55.0,
        bend=15.0, model_name="受電箱",
    )
    assert _bounds_size(build_part_render_data(spec)) == pytest.approx((720.0, 1520.0))


def test_r02_local_seam_relief_runs_after_55_shrink_without_eating_nominal_contract():
    spec = BasePlatePartSpec(
        width=800.0, height=1600.0, thickness=2.0,
        shrink_top=55.0, shrink_bottom=55.0,
        shrink_left=55.0, shrink_right=55.0,
        bend=15.0, model_name="受電箱",
        seam_positions=(400.0,),
    )
    render_data = build_part_render_data(spec)
    assert _bounds_size(render_data) == pytest.approx((720.0, 1520.0))

    coords = {(round(x, 6), round(y, 6)) for x, y in render_data.material.exterior.coords}
    # finished_left=55; unfolded seam x = left_fold(15)+(400-55)=360.
    # 20 mm local relief => 350..370; 0.5T meat at T=2 => y=14.
    assert (350.0, 14.0) in coords
    assert (370.0, 14.0) in coords
    assert (350.0, 0.0) in coords
    assert (370.0, 0.0) in coords


def test_r02_seam_outside_55_finished_face_does_not_create_relief():
    base = BasePlatePartSpec(
        width=800.0, height=1600.0, thickness=2.0,
        shrink_top=55.0, shrink_bottom=55.0,
        shrink_left=55.0, shrink_right=55.0,
        bend=15.0, model_name="受電箱",
    )
    outside = BasePlatePartSpec(
        width=800.0, height=1600.0, thickness=2.0,
        shrink_top=55.0, shrink_bottom=55.0,
        shrink_left=55.0, shrink_right=55.0,
        bend=15.0, model_name="受電箱",
        seam_positions=(50.0,),
    )
    plain = build_part_render_data(base)
    relieved = build_part_render_data(outside)
    assert relieved.material.equals_exact(plain.material, 1e-9)


def test_vault_base_plate_policy_remains_normal_shrink_semantics():
    spec = BasePlatePartSpec(
        width=800.0, height=1600.0, thickness=2.0,
        shrink_top=55.0, shrink_bottom=55.0,
        shrink_left=55.0, shrink_right=55.0,
        bend=15.0, model_name="金庫型",
    )
    assert _bounds_size(build_part_render_data(spec)) == pytest.approx((720.0, 1520.0))


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="需要 Tk 顯示環境")
def test_receiving_2d_snapshot_and_3d_recalculation_keep_55_finished_dimensions():
    import tkinter as tk
    import gui
    import fold_designer_bridge

    root = tk.Tk()
    root.withdraw()
    app = gui.BoxCalculatorGUI(root)
    try:
        app.baseline_var.set("受電箱")
        root.update_idletasks()
        root.update()

        assert tuple(float(var.get()) for var in (
            app.base_plate_shrink_top_var,
            app.base_plate_shrink_bottom_var,
            app.base_plate_shrink_left_var,
            app.base_plate_shrink_right_var,
        )) == (55.0, 55.0, 55.0, 55.0)

        snapshot = app._compose_phase6_project_snapshot_from_main_gui()
        assert snapshot["part_dimensions"]["base_plate"] == {"width": 690.0, "height": 1490.0}

        designer = app.open_original_fold_designer()
        root.update_idletasks()
        root.update()
        dims = fold_designer_bridge._phase6_recalculate_part_dimensions(designer)
        assert dims["base_plate"] == {"width": 690.0, "height": 1490.0}
    finally:
        try:
            if app.fold_designer_window is not None:
                app.fold_designer_window.destroy()
        except Exception:
            pass
        try:
            root.destroy()
        except tk.TclError:
            pass
