# -*- coding: utf-8 -*-
"""#334 T1 — every user-visible Menu/Popup must use the shared dark adapter."""
from __future__ import annotations

import os
from pathlib import Path
import re
import tkinter as tk

import pytest

import whd_theme


ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    "fold_designer_bridge.py",
    "phase6_settings_panel.py",
    "gui_modules/parts/panels/door.py",
    "gui_modules/editors/hole_editor_composition.py",
)
MENU_CALL = re.compile(r"(?:(?:[A-Za-z_]\w*)\.)*tk\.Menu\s*\(")


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _menu_counts(path: str) -> tuple[int, int]:
    source = _text(path)
    constructors = len(MENU_CALL.findall(source))
    themed = source.count("configure_tk_menu(")
    return constructors, themed


def test_all_visible_menu_constructors_route_through_shared_adapter():
    offenders = {}
    for path in TARGETS:
        constructors, themed = _menu_counts(path)
        if constructors != themed:
            offenders[path] = {"constructors": constructors, "themed": themed}
    assert not offenders, (
        "#334 EXPECTED RED: user-visible tk.Menu constructors must route through "
        f"whd_theme.configure_tk_menu; offenders={offenders!r}"
    )


def test_menu_theme_provider_is_presentation_only():
    source = _text("whd_theme.py")
    assert "def configure_tk_menu" in source
    assert "ae_engine" not in source
    assert "manufacturing" not in source.lower()



def test_menu_callback_authority_names_remain_existing_routes():
    bridge = _text("fold_designer_bridge.py")
    door = _text("gui_modules/parts/panels/door.py")
    editor = _text("gui_modules/editors/hole_editor_composition.py")

    for token in (
        '"load_project_file": _phase6_load_project_file',
        '"save_project_file": _phase6_save_project_file',
        '"save_project_file_as": _phase6_save_project_file_as',
        "_phase6_activate_operator_part",
        "self.add_part",
        "self.remove_selected_part",
    ):
        assert token in bridge
    assert "command=lambda:" in door or "add_command" in door
    assert "menu_factory=" in editor

def test_shared_menu_adapter_effective_palette_under_real_tk():
    if not os.environ.get("DISPLAY"):
        pytest.skip("requires real Tk/Xvfb")
    root = tk.Tk()
    root.withdraw()
    try:
        menu = tk.Menu(root, tearoff=False)
        whd_theme.configure_tk_menu(menu)
        assert str(menu.cget("background")).lower() == whd_theme.WHD_THEME["panel"]
        assert str(menu.cget("foreground")).lower() == whd_theme.WHD_THEME["text"]
        assert str(menu.cget("activebackground")).lower() == whd_theme.WHD_THEME["action"]
        assert str(menu.cget("activeforeground")).lower() == "#ffffff"
        assert str(menu.cget("disabledforeground")).lower() == whd_theme.WHD_THEME["muted_text"]
    finally:
        root.destroy()


def test_fold_designer_operator_menus_are_themed_and_postable():
    if not os.environ.get("DISPLAY"):
        pytest.skip("requires real Tk/Xvfb")

    import gui

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    root.update_idletasks()
    root.update()
    try:
        menus = (
            designer.project_file_menu,
            designer.part_choice_menu,
            designer.add_part_menu,
        )
        for menu in menus:
            assert str(menu.cget("background")).lower() == whd_theme.WHD_THEME["panel"]
            assert str(menu.cget("foreground")).lower() == whd_theme.WHD_THEME["text"]
            assert str(menu.cget("activebackground")).lower() == whd_theme.WHD_THEME["action"]
            assert str(menu.cget("activeforeground")).lower() == "#ffffff"
            assert str(menu.cget("disabledforeground")).lower() == whd_theme.WHD_THEME["muted_text"]

        button = designer.part_choice_button
        x = button.winfo_rootx()
        y = button.winfo_rooty() + button.winfo_height()
        designer.part_choice_menu.post(x, y)
        root.update_idletasks()
        root.update()
        assert designer.part_choice_menu.winfo_ismapped() == 1
        assert designer.part_choice_menu.winfo_width() > 1
        assert designer.part_choice_menu.winfo_height() > 1
        designer.part_choice_menu.unpost()
    finally:
        root.destroy()
