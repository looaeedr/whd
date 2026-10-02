# -*- coding: utf-8 -*-
"""#340 T7 — authoritative keyboard shortcuts and focus traversal."""
from __future__ import annotations

import os
from pathlib import Path
import tkinter as tk

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_t7_source_contract_installs_authoritative_shortcuts_and_focus_guards():
    bridge = _text("fold_designer_bridge.py")
    router = _text("gui_modules/application/command_router.py")
    bridge_required = (
        "def _phase6_install_keyboard_shortcuts",
        "self.save_project_file()",
        "self.load_project_file()",
        "_phase6_toggle_fullscreen(self)",
        "takefocus=False",
    )
    router_required = (
        '("<Control-s>", "<Control-S>")',
        '("<Control-o>", "<Control-O>")',
        '"<F11>"',
        "install_fold_designer_keyboard_shortcuts",
    )
    missing = [
        token for token in bridge_required if token not in bridge
    ] + [
        token for token in router_required if token not in router
    ]
    assert not missing, (
        "Fold Designer shortcut/focus ownership drifted from the accepted T7 route; "
        f"missing={missing!r}"
    )

    editor = _text("gui_modules/editors/hole_editor_composition.py")
    for token in ('"<F11>"', '"<Control-z>"', '"<Control-Z>"', '"<Escape>"'):
        assert token in editor


def test_t7_shortcut_helpers_call_existing_actions_only():
    import fold_designer_bridge as bridge

    calls = []
    host = type("Host", (), {})()
    host.save_project_file = lambda: calls.append("save")
    host.load_project_file = lambda: calls.append("open")

    assert bridge._phase6_keyboard_save(host) == "break"
    assert bridge._phase6_keyboard_open(host) == "break"
    assert calls == ["save", "open"]


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires real Tk/Xvfb")
def test_t7_real_tk_ctrl_s_ctrl_o_route_to_existing_callbacks():
    import gui

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    calls = []
    try:
        designer.save_project_file = lambda: calls.append("save")
        designer.load_project_file = lambda: calls.append("open")
        root.deiconify()
        root.focus_force()
        for sequence in ("<Control-s>", "<Control-o>"):
            root.event_generate(sequence)
            root.update_idletasks(); root.update()
        assert calls == ["save", "open"]
        assert root.bind("<F11>")
    finally:
        root.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires real Tk/Xvfb")
@pytest.mark.parametrize("ui_text_size", ("small", "medium", "large"))
def test_t7_focus_traversal_reaches_main_controls_and_skips_compat_canvas(ui_text_size):
    import gui

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    try:
        designer.apply_external_settings({"ui_text_size": ui_text_size})
        for _ in range(4):
            root.update_idletasks(); root.update()

        main = (
            designer.project_file_button,
            designer.output_export_button,
            designer.part_choice_button,
            designer.add_part_button,
            designer.remove_part_button,
        )
        assert all(str(widget.cget("takefocus")).lower() not in {"0", "false"} for widget in main)

        forbidden = {
            str(designer.box_body_piece_selector),
            str(designer.left_scroll_canvas),
            str(designer.assembly_parts_canvas),
            str(designer.renderer.canvas.get_tk_widget()),
        }
        for widget in (
            designer.box_body_piece_selector,
            designer.left_scroll_canvas,
            designer.assembly_parts_canvas,
            designer.renderer.canvas.get_tk_widget(),
        ):
            assert str(widget.cget("takefocus")).lower() in {"0", "false"}

        start = designer.part_choice_button
        seen = {str(start)}
        current = str(start)
        for _ in range(18):
            nxt = str(root.tk.call("tk_focusNext", current))
            if not nxt or nxt == current:
                break
            assert nxt not in forbidden
            seen.add(nxt)
            current = nxt
        assert str(designer.add_part_button) in seen or str(designer.remove_part_button) in seen
    finally:
        root.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires real Tk/Xvfb")
def test_t7_focus_style_is_visible_and_floating_surface_returns_focus():
    import gui
    import whd_theme

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    try:
        style = tk.ttk.Style(root) if hasattr(tk, "ttk") else None
    except Exception:
        style = None
    try:
        from tkinter import ttk
        style = ttk.Style(root)
        for role in ("Primary.TButton", "Secondary.TButton", "Selector.TMenubutton"):
            assert style.lookup(role, "bordercolor", ("focus",)).lower() == whd_theme.WHD_THEME["action"]

        designer.relief_registry_button.focus_set()
        root.update_idletasks(); root.update()
        designer.relief_registry_button.invoke()
        for _ in range(3):
            root.update_idletasks(); root.update()
        win = designer.relief_registry_window
        assert getattr(win, "_phase6_return_focus", None) is designer.relief_registry_button

        win.event_generate("<Escape>")
        for _ in range(3):
            root.update_idletasks(); root.update()
        assert not win.winfo_exists()
        assert root.focus_get() is designer.relief_registry_button
    finally:
        root.destroy()
