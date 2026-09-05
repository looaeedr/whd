# -*- coding: utf-8 -*-
from __future__ import annotations

import tkinter as tk

import pytest

import fold_designer_bridge as bridge


def _snapshot():
    return {
        "w": 500,
        "h": 600,
        "d": 200,
        "model": "金庫型",
        "existing_parts": ["box_body", "head", "tail"],
        "active_part": "box_body",
        "settings": {"t": 2.0, "fw": 24.0, "ui_text_size": "small"},
    }


def _make_app(monkeypatch):
    monkeypatch.setattr(bridge, "project_features_to_original_holes", lambda *a, **k: [])
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - headless fallback
        pytest.skip(f"Tk unavailable: {exc}")
    root.withdraw()
    win = tk.Toplevel(root)
    app = bridge.Phase6FoldDesignerApp(win, _snapshot())
    root.update_idletasks()
    return root, win, app


def test_first_3d_view_is_assembly_and_assembly_is_first_part_choice(monkeypatch):
    root, win, app = _make_app(monkeypatch)
    try:
        assert app.part_choice_menu.entrycget(0, "label") == "組合體"
        assert app.part_var.get() == "組合體"
        assert app._phase6_3d_display_mode == "assembly"
        assert app.fold_editor_host.winfo_manager() == ""
        assert app.settings_center.winfo_manager() == ""
    finally:
        root.destroy()


def test_selecting_real_sheet_part_switches_to_single_part_editor(monkeypatch):
    root, win, app = _make_app(monkeypatch)
    try:
        app.activate_part("box_body")
        root.update_idletasks()
        assert app.part_var.get() == "箱身"
        assert app._phase6_3d_display_mode == "single"
        assert app.fold_editor_host.winfo_manager() == "pack"
    finally:
        root.destroy()


def test_latest_top_and_global_layout_contract(monkeypatch):
    root, win, app = _make_app(monkeypatch)
    try:
        # Top row: file -> 3D display -> fullscreen -> transaction buttons.
        assert app.project_toolbar.master is app.top_command_row
        assert app.visual_controls.master is app.top_command_row
        assert app.fullscreen_button.master is app.top_command_row
        assert app.return_2d_button.master is app.top_command_row
        assert app.transaction_buttons.master is app.top_command_row
        assert app.fullscreen_button.cget("text") == "全螢幕"
        assert app.return_2d_button.cget("text") == "回2D截角"
        assert app.ui_text_size_combo.master is app.visual_controls

        # Global row 1: baseline + lock + save defaults.
        assert app.left_global_controls.master is app.top_global_host
        assert int(app.baseline_model_combo.grid_info()["row"]) == 0
        assert app.parameter_lock_button.master is app.left_global_controls
        assert int(app.parameter_lock_button.grid_info()["row"]) == 0
        assert int(app.save_global_settings_button.grid_info()["row"]) == 0
        assert app.save_global_settings_button.cget("text") == "儲存預設值"

        # Global row 2: W/H/D/T + structure + assembly type.
        for key in ("w", "h", "d", "t"):
            cell = app.left_global_cells[key]
            assert int(cell.grid_info()["row"]) == 1
        assert int(app.left_global_cells["structure"].grid_info()["row"]) == 1
        assert app.structure_choice_button.master is app.left_global_cells["structure"]
        assert int(app.left_global_cells["assembly"].grid_info()["row"]) == 1
        assert app.assembly_choice_button.master is app.left_global_cells["assembly"]

        # No duplicate right-side control bar remains above the canvas.
        assert getattr(app, "right_control_bar", None) is None
    finally:
        root.destroy()


def test_parameter_unlock_routes_to_assembly_diagnostics_then_part_settings(monkeypatch):
    root, win, app = _make_app(monkeypatch)
    try:
        assert app.part_var.get() == "組合體"
        assert bridge._phase6_toggle_parameter_panel(app) is True
        root.update_idletasks()
        assert app.assembly_diagnostics_frame.winfo_manager() == "pack"
        assert app.settings_center.winfo_manager() == ""

        app.activate_part("box_body")
        root.update_idletasks()
        assert app.assembly_diagnostics_frame.winfo_manager() == ""
        assert app.settings_center.winfo_manager() == "pack"
    finally:
        root.destroy()



def test_assembly_left_panel_lists_all_sheet_parts_with_view_only_checkboxes(monkeypatch):
    root, win, app = _make_app(monkeypatch)
    try:
        root.update_idletasks()
        assert app.assembly_parts_panel.master is app.left
        assert app.assembly_parts_panel.winfo_manager() == "pack"
        assert set(app.assembly_part_visible_vars) == set(app.available_parts)
        assert set(app.assembly_part_corner_vars) == set(app.available_parts)
        assert set(app.assembly_part_blank_vars) == set(app.available_parts)
        assert all(str(var.get()).startswith("展開料：") for var in app.assembly_part_blank_vars.values())
        assert all(var.get() is True for var in app.assembly_part_visible_vars.values())

        app.activate_part("head")
        root.update_idletasks()
        assert app.assembly_parts_panel.winfo_manager() == ""
    finally:
        root.destroy()

def test_fullscreen_toggle_maximizes_and_restores_without_touching_geometry_state():
    from types import SimpleNamespace

    class Root:
        def __init__(self):
            self.current_state = "normal"
            self.geom = "1200x800+10+10"
            self.attr_calls = []

        def geometry(self, value=None):
            if value is not None:
                self.geom = value
            return self.geom

        def state(self, value=None):
            if value is not None:
                self.current_state = value
            return self.current_state

        def attributes(self, *args):
            self.attr_calls.append(args)

    class Button:
        def __init__(self):
            self.text = "全螢幕"

        def configure(self, **kwargs):
            self.text = kwargs.get("text", self.text)

    root = Root()
    button = Button()
    app = SimpleNamespace(root=root, fullscreen_button=button, _phase6_fullscreen=False)

    assert bridge._phase6_toggle_fullscreen(app) is True
    assert root.current_state == "zoomed"
    assert button.text == "還原視窗"

    assert bridge._phase6_toggle_fullscreen(app) is False
    assert root.current_state == "normal"
    assert root.geom == "1200x800+10+10"
    assert button.text == "全螢幕"


def test_parameter_unlock_shows_assembly_diagnostics_while_assembly_is_selected(monkeypatch):
    root, win, app = _make_app(monkeypatch)
    try:
        assert app.part_var.get() == "組合體"
        assert bridge._phase6_toggle_parameter_panel(app) is True
        root.update_idletasks()
        assert app.assembly_diagnostics_frame.winfo_manager() == "pack"
        assert app.settings_center.winfo_manager() == ""
        assert app.assembly_ignore_fixed_corner_var.get() is True
        assert app.assembly_show_interference_var.get() is True
    finally:
        root.destroy()


def test_assembly_diagnostics_exposes_clearance_a_and_actual_relief_size(monkeypatch):
    root, win, app = _make_app(monkeypatch)
    try:
        assert bridge._phase6_toggle_parameter_panel(app) is True
        root.update_idletasks()
        assert app.assembly_relief_clearance_var.get() == "0"
        assert app.assembly_relief_size_var.get().startswith("實際截角尺寸：")
        assert app.assembly_relief_clearance_entry.winfo_manager() == "pack"
    finally:
        root.destroy()


def test_parameter_lock_button_invoke_makes_assembly_panel_actually_visible(monkeypatch):
    monkeypatch.setattr(bridge, "project_features_to_original_holes", lambda *a, **k: [])
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover
        pytest.skip(f"Tk unavailable: {exc}")
    root.geometry("1200x800+0+0")
    win = tk.Toplevel(root)
    win.geometry("1100x700+20+20")
    app = bridge.Phase6FoldDesignerApp(win, _snapshot())
    try:
        root.update_idletasks(); root.update()
        assert app.part_var.get() == "組合體"
        assert app.assembly_diagnostics_frame.winfo_viewable() == 0

        app.parameter_lock_button.invoke()
        root.update_idletasks(); root.update()

        assert app._phase6_parameters_unlocked is True
        assert app.assembly_diagnostics_frame.winfo_manager() == "pack"
        assert app.assembly_diagnostics_frame.winfo_viewable() == 1
        assert app.assembly_diagnostics_frame.winfo_height() > 1
        assert app.renderer.canvas.get_tk_widget().winfo_viewable() == 1
    finally:
        root.destroy()


def test_parameter_unlock_then_select_box_body_shows_real_part_settings(monkeypatch):
    monkeypatch.setattr(bridge, "project_features_to_original_holes", lambda *a, **k: [])
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover
        pytest.skip(f"Tk unavailable: {exc}")
    root.geometry("1200x800+0+0")
    win = tk.Toplevel(root)
    win.geometry("1100x700+20+20")
    app = bridge.Phase6FoldDesignerApp(win, _snapshot())
    try:
        root.update_idletasks(); root.update()
        app.parameter_lock_button.invoke()
        root.update_idletasks(); root.update()
        assert app.assembly_diagnostics_frame.winfo_viewable() == 1

        app.activate_part("box_body")
        root.update_idletasks(); root.update()

        assert app._phase6_3d_display_mode == "single"
        assert app.assembly_diagnostics_frame.winfo_viewable() == 0
        assert app.settings_center.winfo_manager() == "pack"
        assert app.settings_center.winfo_viewable() == 1
        assert app.settings_center.winfo_height() > 1
    finally:
        root.destroy()


def test_operator_assembly_diagnostics_does_not_expose_joint_debug_selector(monkeypatch):
    root, win, app = _make_app(monkeypatch)
    try:
        children = app.assembly_diagnostics_frame.winfo_children()
        texts = []
        for child in children:
            try:
                texts.append(str(child.cget("text")))
            except tk.TclError:
                pass
        assert "Joint" not in texts
        assert not hasattr(app, "assembly_joint_diag_button")
    finally:
        root.destroy()
