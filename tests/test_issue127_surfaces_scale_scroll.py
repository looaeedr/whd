# -*- coding: utf-8 -*-
import tkinter as tk
from types import SimpleNamespace

import fold_designer_bridge as bridge
import phase6_settings_panel as settings_panel
from phase6_settings_center import SettingSpec, UI_TEXT_SIZE_FACTORS


class _Value:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value


def _spec(index: int) -> SettingSpec:
    return SettingSpec(
        key=f"demo_{index}",
        label=f"欄位 {index}",
        contexts=("demo",),
        section="DEMO",
        option=f"demo_{index}",
        default=float(index),
        group="測試群組",
    )


def _panel(specs):
    values = {spec.key: spec.default for spec in specs}
    return settings_panel.Phase6SettingsPanel(
        values_snapshot=lambda: dict(values),
        stage_setting_update=lambda _key, _value: None,
        flush_settings=lambda: None,
        save_defaults=lambda _context: None,
        specs_provider=lambda _context: tuple(specs),
        part_labels={"demo": "測試板件"},
    )


def test_text_scale_contract_is_exactly_1_0_1_2_1_4():
    assert UI_TEXT_SIZE_FACTORS == {
        "small": 1.0,
        "medium": 1.2,
        "large": 1.4,
    }


def test_status_projection_reads_existing_authoritative_family_part_and_view_only():
    owner = SimpleNamespace(
        _phase6_input_snapshot={"model": "受電箱"},
        baseline_model_var=_Value("受電箱"),
        _phase6_3d_display_mode="single",
        active_part_key="head",
        _phase6_corner_data_selected_part_key=None,
    )
    projection = getattr(bridge, "_phase6_status_projection", None)
    assert callable(projection), "#127 requires one read-only Status Bar projection helper"

    before = dict(owner._phase6_input_snapshot)
    text = projection(owner)
    assert "箱型：受電箱" in text
    assert "板件：封頭" in text
    assert "視圖：單件 3D" in text
    assert owner._phase6_input_snapshot == before

    owner._phase6_3d_display_mode = "assembly"
    assert "視圖：組合體" in projection(owner)
    owner._phase6_3d_display_mode = "corner_data"
    owner._phase6_corner_data_selected_part_key = "tail"
    corner_text = projection(owner)
    assert "板件：封尾" in corner_text
    assert "視圖：截角資料" in corner_text


def test_settings_scroll_supports_keyboard_home_end_page_navigation():
    root = tk.Tk()
    try:
        specs = tuple(_spec(i) for i in range(24))
        panel = _panel(specs)
        panel.build_settings_center(root)
        panel.settings_scroll_canvas.configure(height=90)
        panel.render_context("demo")
        root.geometry("520x220+0+0")
        root.update_idletasks(); root.update()

        canvas = panel.settings_scroll_canvas
        assert canvas.bind("<Home>"), "#127 requires keyboard scroll reachability"
        assert canvas.bind("<End>")
        assert canvas.bind("<Prior>")
        assert canvas.bind("<Next>")

        canvas.yview_moveto(0.0)
        canvas.focus_force(); root.update()
        canvas.event_generate("<End>", when="tail"); root.update()
        assert canvas.yview()[1] >= 0.99
        canvas.event_generate("<Home>", when="tail"); root.update()
        assert canvas.yview()[0] <= 0.01
    finally:
        root.destroy()


def test_dropdown_has_explicit_foreground_role_and_keyboard_focus():
    root = tk.Tk()
    try:
        var = tk.StringVar(master=root, value="A")
        button = settings_panel.build_choice_menubutton(
            root, variable=var, values=("A", "B", "C"), width=8
        )
        button.pack()
        root.update_idletasks()
        menu = button._phase6_menu

        assert getattr(button, "_phase6_foreground_role", None) == "dropdown"
        assert getattr(menu, "_phase6_foreground_role", None) == "floating_menu"
        assert str(button.cget("takefocus")) not in {"", "0", "false", "False"}
        assert str(menu.cget("relief")) in {"raised", "ridge", "solid"}
        assert int(menu.cget("borderwidth")) >= 1
        assert int(menu.cget("activeborderwidth")) >= 1
    finally:
        root.destroy()


def test_floating_surface_is_transient_focusable_and_escape_reachable_without_forcing_modal():
    root = tk.Tk()
    try:
        win = tk.Toplevel(root)
        configure = getattr(bridge, "_phase6_configure_floating_surface", None)
        assert callable(configure), "#127 requires one shared floating-surface foreground contract"
        configure(win, root, modal=False)
        root.update_idletasks(); root.update()

        assert str(win.transient()) == str(root)
        assert getattr(win, "_phase6_foreground_role", None) == "floating_surface"
        assert win.bind("<Escape>")
        assert win.grab_current() is None
    finally:
        for widget in tuple(root.winfo_children()):
            try:
                widget.destroy()
            except tk.TclError:
                pass
        root.destroy()


def test_status_bar_widget_is_projection_only_and_does_not_create_state_owner():
    import gui

    root = tk.Tk()
    designer = None
    try:
        root.geometry("1100x760+0+0")
        root.update()
        app = gui.BoxCalculatorGUI(root)
        designer = app.open_original_fold_designer()
        designer.root.update_idletasks(); designer.root.update()

        assert getattr(designer, "status_bar", None) is not None
        assert getattr(designer, "status_projection_var", None) is not None
        assert designer.status_bar.winfo_manager()
        text = designer.status_projection_var.get()
        assert "箱型：" in text and "板件：" in text and "視圖：" in text

        before = designer.designer_workspace.snapshot()
        bridge._phase6_refresh_status_bar(designer)
        after = designer.designer_workspace.snapshot()
        assert after == before
    finally:
        if designer is not None:
            try:
                designer.root.destroy()
            except Exception:
                pass
        root.destroy()
