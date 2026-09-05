import tkinter as tk

import fold_designer_bridge as bridge
import fold_designer_original as original


def _snapshot():
    settings = {
        "w": 500.0, "h": 600.0, "d": 200.0, "t": 2.0, "fw": 25.0,
        "draw_stock": False,
        "relief_top_secondary_x_factor": 0.5,
        "relief_top_secondary_depth_factor": 2.0,
        "relief_bottom_x_factor": 0.5,
        "relief_bottom_y_factor": 0.5,
        "notch_bottom_gap": 0.5, "notch_sub_x_half": 0.5, "notch_sub_y_factor": 2.0,
        "zl1": 15.0, "zl2": 20.0, "zr1": 15.0, "zr2": 20.0, "z_comp": 3.0,
        "yl1": 15.0, "yr1": 15.0, "ytop1": 16.0, "ybottom1": 15.0,
        "hang_hole_r": 3.2, "hang_hole_x": 35.5, "hang_hole_y_up": 6.0,
        "sq_x_left": 3.0, "sq_width": 4.0, "sq_y_bottom": 18.0, "sq_height": 4.0,
        "bottom_hole_r": 2.5, "bottom_hole_y": 5.0,
        "door_gap_w": 3.5, "door_gap_h": 3.5,
        "door_fold_l": 19.0, "door_fold_r": 15.0, "door_fold_t": 15.0, "door_fold_b": 15.0,
        "base_plate_shrink_top": 55.0, "base_plate_shrink_bottom": 55.0,
        "base_plate_shrink_left": 55.0, "base_plate_shrink_right": 55.0, "base_plate_bend": 15.0,
        "indicator_box_fold": 49.0, "indicator_door_fold": 19.0,
    }
    return dict(
        model="金庫型", w=500, h=600, d=200, t=2, fw=25,
        zl1=15, zl2=20, zr1=15, zr2=20, z_comp=3,
        yl1=15, yr1=15, ytop1=16, ybottom1=15,
        door_gap_w=3.5, door_gap_h=3.5,
        door_fold_l=19, door_fold_r=15, door_fold_t=15, door_fold_b=15,
        base_plate_shrink_top=55, base_plate_shrink_bottom=55,
        base_plate_shrink_left=55, base_plate_shrink_right=55, base_plate_bend=15,
        indicator_box_fold=49, indicator_door_fold=19,
        existing_parts=["box_body", "door", "base_plate"], active_part="box_body",
        part_dimensions={
            "box_body": {"width": 500, "height": 600},
            "door": {"width": 435, "height": 535},
            "base_plate": {"width": 390, "height": 490},
        },
        part_features={}, part_face_features={}, settings=settings,
    )


def _make_app(monkeypatch, **kwargs):
    monkeypatch.setattr(bridge, "project_features_to_original_holes", lambda *a, **k: [])
    root = tk.Tk(); root.withdraw(); win = tk.Toplevel(root)
    app = bridge.Phase6FoldDesignerApp(win, _snapshot(), **kwargs)
    win.update_idletasks()
    return root, win, app


def test_settings_center_is_above_original_renderer_and_global_controls_are_left(monkeypatch):
    root, win, app = _make_app(monkeypatch)
    try:
        assert type(app.renderer) is original.Renderer
        assert app.settings_center.winfo_exists()
        # Assembly startup may initialize the settings-controller context.
        assert "w" in app.left_global_vars
        assert "fw" not in app.left_global_vars
        renderer_widget = app.renderer.canvas.get_tk_widget()
        assert app.settings_center.winfo_manager() == ""
        assert renderer_widget.winfo_manager() == "pack"
        app._phase6_parameters_unlocked = True
        app.activate_part("box_body")
        win.update_idletasks()
        assert app.settings_context == "box_body"
        assert app.settings_title_var.get() == "箱身設定"
        assert "w" not in app.setting_vars
        assert "zl1" not in app.setting_vars
        assert app.settings_center.winfo_manager() == "pack"
        assert renderer_widget.winfo_manager() == "pack"
    finally:
        root.destroy()


def test_part_activation_switches_settings_context_without_combobox(monkeypatch):
    root, win, app = _make_app(monkeypatch)
    try:
        app.activate_part("door")
        win.update_idletasks()
        assert app.settings_context == "door"
        assert {"door_gap_w", "door_gap_h"} <= set(app.setting_vars)
        assert not {"door_fold_l", "door_fold_r", "door_fold_t", "door_fold_b"} & set(app.setting_vars)
        assert "w" not in app.setting_vars
        assert app.settings_context == "door"
    finally:
        root.destroy()


def test_setting_edit_calls_live_callback_and_external_global_update_refreshes_designer(monkeypatch):
    calls = []
    root, win, app = _make_app(monkeypatch, on_settings_change=lambda payload: calls.append(dict(payload)))
    try:
        var = app.left_global_vars["w"]
        var.set("640")
        app.flush_pending_settings()
        win.update()
        assert calls and calls[-1]["w"] == 640.0
        assert app.v_w.get() == "640"

        app.apply_external_settings({"d": 275.0, "t": 2.3})
        win.update()
        assert app.v_d.get() == "275"
        assert app._phase6_input_snapshot["t"] == 2.3
    finally:
        root.destroy()


def test_save_button_delegates_only_current_context(monkeypatch):
    saved = []
    root, win, app = _make_app(monkeypatch, on_save_defaults=lambda context, values, corner_state, pair_same: saved.append((context, dict(values))))
    try:
        app.activate_part("base_plate")
        app.save_current_settings_as_defaults()
        assert saved and saved[-1][0] == "base_plate"
        assert saved[-1][1]["base_plate_bend"] == 15.0
    finally:
        root.destroy()


def test_part_settings_center_corner_pair_edit_uses_live_canonical_callback(monkeypatch):
    monkeypatch.setattr(bridge, "project_features_to_original_holes", lambda *a, **k: [])
    root = tk.Tk(); root.withdraw()
    published = []
    try:
        snapshot = _snapshot()
        snapshot["model"] = "未知類型"
        snapshot["baseline_models"] = ["金庫型", "未知類型"]
        snapshot["baseline_unknown_value"] = "未知類型"
        snapshot["corner_editable"] = True
        snapshot["corner_state"] = {
            "door": {
                "top_left": {"type_id": "C01", "rotation_quadrants": 0},
                "top_right": {"type_id": "C01", "rotation_quadrants": 0},
                "bottom_left": {"type_id": "C01", "rotation_quadrants": 0},
                "bottom_right": {"type_id": "C01", "rotation_quadrants": 0},
            }
        }
        snapshot["corner_pair_same"] = {"door": {"top": True, "bottom": True}}
        app = bridge.Phase6FoldDesignerApp(root, snapshot, on_live_sync=lambda payload: published.append(payload))
        app._phase6_parameters_unlocked = True
        app.activate_part("door")
        root.update_idletasks()
        published.clear()
        app.corner_pair_checkbuttons["top"].invoke()
        root.update_idletasks()
        assert app._phase6_corner_pair_same["door"]["top"] is False
        assert published
        assert published[-1]["corner_pair_same"]["door"]["top"] is False
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass

