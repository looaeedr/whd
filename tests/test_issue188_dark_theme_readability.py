# -*- coding: utf-8 -*-
"""#188 T3 — shared WHD dark engineering theme contract.

These tests validate presentation only.  They must never become geometry,
manufacturing, DXF, topology, or persistence authority.
"""
from __future__ import annotations

import importlib
from pathlib import Path
import tkinter as tk
from tkinter import ttk


ROOT = Path(__file__).resolve().parents[1]
def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_shared_theme_provider_is_single_token_authority():
    theme = importlib.import_module("whd_theme")
    required = {
        "background", "panel", "input", "text", "muted_text",
        "action", "action_hover", "action_pressed", "canvas", "corner_data_canvas",
    }
    assert required <= set(theme.WHD_THEME)
    assert callable(theme.apply_ttk_dark_theme)
    assert callable(theme.apply_mpl_dark_theme)

    # Theme code is presentation-only; it may not pull manufacturing authority in.
    source = _text("whd_theme.py")
    assert "ae_engine" not in source
    assert "manufacturing" not in source.lower()
    assert "PartSpec" not in source


def test_legacy_main_gui_consumes_shared_tokens_instead_of_owning_a_second_palette():
    source = _text("gui.py")
    assert "from whd_theme import" in source
    theme = importlib.import_module("whd_theme")
    for key in ("background", "panel", "input", "canvas"):
        token = str(theme.WHD_THEME[key])
        assert f'= "{token}"' not in source
    assert "WHD_THEME" in source


def test_3d_shell_settings_and_final_scene_consume_shared_theme_contract():
    bridge = _text("fold_designer_bridge.py")
    panel = _text("phase6_settings_panel.py")
    scene = _text("phase6_final_scene_renderer.py")
    original = _text("fold_designer_original.py")

    assert "whd_theme" in bridge
    assert "whd_theme" in panel
    assert "whd_theme" in original
    assert "apply_mpl_dark_theme" in scene
    assert "ax.clear()" in scene
    assert scene.index("ax.clear()") < scene.index("apply_mpl_dark_theme", scene.index("ax.clear()"))


def test_ttk_effective_dark_states_are_readable_under_real_tk():
    theme = importlib.import_module("whd_theme")
    root = tk.Tk()
    root.withdraw()
    try:
        style = theme.apply_ttk_dark_theme(root, text_scale=1.0)
        root.update_idletasks()

        colors = theme.WHD_THEME
        assert root.cget("background").lower() == colors["background"]
        assert style.lookup("TFrame", "background").lower() == colors["panel"]
        assert style.lookup("TLabel", "foreground").lower() == colors["text"]
        assert style.lookup("TEntry", "fieldbackground").lower() == colors["input"]
        assert style.lookup("TEntry", "foreground").lower() == colors["text"]
        assert style.lookup("Treeview", "background").lower() == colors["input"]
        assert style.lookup("Treeview", "foreground").lower() == colors["text"]
        assert style.lookup("Treeview", "background", ("selected",)).lower() == colors["action"]

        # Critical controls must be genuinely mapped/reachable, not merely created.
        host = ttk.Frame(root)
        host.pack(fill="both", expand=True)
        entry = ttk.Entry(host)
        check = ttk.Checkbutton(host, text="輸出")
        button = ttk.Button(host, text="套用")
        tree = ttk.Treeview(host, columns=("v",), show="tree")
        for widget in (entry, check, button, tree):
            widget.pack(fill="x")
        root.deiconify()
        root.update_idletasks()
        assert all(widget.winfo_ismapped() for widget in (entry, check, button, tree))
    finally:
        root.destroy()


def test_corner_data_viewport_uses_shared_exception_token():
    bridge = _text("fold_designer_bridge.py")
    theme = importlib.import_module("whd_theme")
    assert 'bg=WHD_THEME["corner_data_canvas"]' in bridge
    # The special Corner Data surface remains distinct, but its literal color is
    # owned only by the current shared theme provider.
    assert theme.WHD_THEME["canvas"] != theme.WHD_THEME["corner_data_canvas"]
