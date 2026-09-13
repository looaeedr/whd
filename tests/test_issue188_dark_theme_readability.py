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
EXPECTED = {
    "background": "#121214",
    "panel": "#1e1e24",
    "input": "#151518",
    "text": "#e0e0e6",
    "muted_text": "#8e8e93",
    "action": "#0a84ff",
    "canvas": "#0d0d0f",
    "corner_data_canvas": "#000000",
}


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_shared_theme_provider_is_single_token_authority():
    theme = importlib.import_module("whd_theme")
    assert dict(theme.WHD_THEME) == EXPECTED
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
    assert 'self.COLOR_BG = "#121214"' not in source
    assert 'self.COLOR_PANEL = "#1e1e24"' not in source
    assert 'self.COLOR_INPUT_BG = "#151518"' not in source
    assert 'self.COLOR_CANVAS_BG = "#0d0d0f"' not in source
    assert "WHD_THEME" in source


def test_3d_shell_settings_and_final_scene_consume_shared_theme_contract():
    bridge = _text("fold_designer_bridge.py")
    panel = _text("phase6_settings_panel.py")
    scene = _text("phase6_final_scene_view.py")
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

        assert root.cget("background").lower() == EXPECTED["background"]
        assert style.lookup("TFrame", "background").lower() == EXPECTED["panel"]
        assert style.lookup("TLabel", "foreground").lower() == EXPECTED["text"]
        assert style.lookup("TEntry", "fieldbackground").lower() == EXPECTED["input"]
        assert style.lookup("TEntry", "foreground").lower() == EXPECTED["text"]
        assert style.lookup("Treeview", "background").lower() == EXPECTED["input"]
        assert style.lookup("Treeview", "foreground").lower() == EXPECTED["text"]

        tree_map = style.map("Treeview", "background")
        assert any(EXPECTED["action"] in str(value).lower() for _state, value in tree_map)

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


def test_corner_data_viewport_keeps_exact_black_exception():
    bridge = _text("fold_designer_bridge.py")
    assert 'bg="#000000"' in bridge
    # Generic 3D/canvas dark is deliberately not the Corner Data viewport color.
    theme = importlib.import_module("whd_theme")
    assert theme.WHD_THEME["canvas"] == "#0d0d0f"
    assert theme.WHD_THEME["corner_data_canvas"] == "#000000"
