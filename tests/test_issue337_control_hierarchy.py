# -*- coding: utf-8 -*-
"""#337 T4 — shared control identity and action hierarchy."""
from __future__ import annotations

import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk

import pytest

import whd_theme


ROOT = Path(__file__).resolve().parents[1]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")



def test_t4_shared_role_source_contract():
    theme = _text("whd_theme.py")
    panel = _text("phase6_settings_panel.py")
    bridge = _text("fold_designer_bridge.py")

    required = (
        "Primary.TButton",
        "Secondary.TButton",
        "Selector.TMenubutton",
        "Editable.TEntry",
        "Readonly.TEntry",
    )
    missing = [role for role in required if f'"{role}"' not in theme]
    assert not missing, (
        "#337 shared input/selector/primary/secondary style roles drifted: "
        f"{missing!r}"
    )

    assert "Selector.TMenubutton" in panel
    assert "Primary.TButton" in panel
    assert "Secondary.TButton" in panel
    assert "Selector.TMenubutton" in bridge
    assert "Secondary.TButton" in bridge
    assert "Secondary.TMenubutton" in bridge

def test_t4_theme_remains_presentation_only():
    source = _text("whd_theme.py")
    assert "ae_engine" not in source
    assert "manufacturing" not in source.lower()
    assert "PartSpec" not in source


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires real Tk/Xvfb")
def test_t4_effective_roles_are_visually_distinct_and_stateful():
    root = tk.Tk()
    root.withdraw()
    try:
        style = whd_theme.apply_ttk_dark_theme(root)

        assert style.lookup("Primary.TButton", "background").lower() == whd_theme.WHD_THEME["action"]
        assert style.lookup("Secondary.TButton", "background").lower() == whd_theme.WHD_THEME["panel"]
        assert style.lookup("Selector.TMenubutton", "background").lower() == whd_theme.WHD_THEME["input"]

        assert style.lookup("Editable.TEntry", "fieldbackground").lower() == whd_theme.WHD_THEME["input"]
        assert style.lookup("Readonly.TEntry", "fieldbackground").lower() == whd_theme.WHD_THEME["panel"]
        assert style.lookup("Editable.TEntry", "relief") != style.lookup("Secondary.TButton", "relief")
        assert style.lookup("Selector.TMenubutton", "arrowcolor").lower() == whd_theme.WHD_THEME["action"]

        primary_map = style.map("Primary.TButton", "background")
        secondary_map = style.map("Secondary.TButton", "background")
        selector_map = style.map("Selector.TMenubutton", "background")
        assert any("active" in state for state, _value in primary_map)
        assert any("pressed" in state for state, _value in primary_map)
        assert any("disabled" in state for state, _value in primary_map)
        assert any("active" in state for state, _value in secondary_map)
        assert any("pressed" in state for state, _value in secondary_map)
        assert any("active" in state for state, _value in selector_map)

        entry_map = style.map("TEntry", "fieldbackground")
        assert any("readonly" in state for state, _value in entry_map)
    finally:
        root.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires real Tk/Xvfb")
def test_t4_designer_assigns_semantic_roles_without_callback_changes():
    import gui

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    try:
        for _ in range(4):
            root.update_idletasks(); root.update()

        assert str(designer.output_export_button.cget("style")) == "Primary.TButton"
        assert str(designer.part_choice_button.cget("style")) == "Selector.TMenubutton"
        assert str(designer.add_part_button.cget("style")) == "Secondary.TMenubutton"
        assert str(designer.remove_part_button.cget("style")) == "Secondary.TButton"
        assert str(designer.project_file_button.cget("style")) == "Secondary.TMenubutton"
        assert str(designer.relief_registry_button.cget("style")) == "Secondary.TButton"
        assert str(designer.reset_initial_button.cget("style")) == "Secondary.TButton"
        assert str(designer.fullscreen_button.cget("style")) == "Secondary.TButton"

        # Callback/state authority remains the already-existing route.
        assert designer.output_export_button.cget("command")
        assert designer.part_choice_button.cget("menu")
        assert designer.add_part_button.cget("menu")
    finally:
        root.destroy()
