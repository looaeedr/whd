# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tkinter as tk

import pytest

import fold_designer_bridge as bridge
from whd_theme import WHD_THEME

pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="#440 requires real Tk/Xvfb"
)


def _snapshot():
    return {
        "model": "金庫型",
        "w": 500,
        "h": 600,
        "d": 200,
        "existing_parts": ["box_body", "head", "tail"],
        "active_part": "box_body",
        "settings": {"t": 2.0, "fw": 24.0},
    }


def _pump(root, cycles=3):
    for _ in range(cycles):
        root.update_idletasks()
        root.update()


def _open():
    root = tk.Tk()
    root.geometry("1200x850+0+0")
    app = bridge.Phase6FoldDesignerApp(root, _snapshot())
    _pump(root)
    return root, app


def _mapped_mode_surfaces(app):
    surfaces = (
        app.input_content_host,
        app.assembly_parts_panel,
        getattr(app, "corner_data_panel", None),
    )
    return tuple(w for w in surfaces if w is not None and w.winfo_manager())


def test_440_no_fixed_outer_wrapper_shell():
    root, app = _open()
    try:
        assert app.fold_editor_host is app.input_content_host, (
            "INTENDED_RED_FIXED_OUTER_WRAPPER_EXISTS"
        )
        assert app.shared_content_host is app.left
        assert not hasattr(app, "_phase6_physical_content_height")
    finally:
        root.destroy()


def test_440_all_mode_surfaces_are_direct_left_siblings():
    root, app = _open()
    try:
        bridge._phase6_show_corner_data(app)
        _pump(root)
        assert app.input_content_host.master is app.left, "INTENDED_RED_INPUT_NESTED_IN_WRAPPER"
        assert app.assembly_parts_panel.master is app.left, "INTENDED_RED_ASSEMBLY_NESTED_IN_WRAPPER"
        assert app.corner_data_panel.master is app.left, "INTENDED_RED_CORNER_NESTED_IN_WRAPPER"
    finally:
        root.destroy()


def test_440_same_slot_mutual_exclusion_without_fixed_height_shell():
    root, app = _open()
    try:
        app.activate_part("head")
        _pump(root)
        assert _mapped_mode_surfaces(app) == (app.input_content_host,)

        bridge._phase6_show_assembly(app)
        _pump(root)
        assert _mapped_mode_surfaces(app) == (app.assembly_parts_panel,)

        bridge._phase6_show_corner_data(app)
        _pump(root)
        assert _mapped_mode_surfaces(app) == (app.corner_data_panel,)

        app.activate_part(app.designer_workspace.active_part)
        _pump(root)
        assert _mapped_mode_surfaces(app) == (app.input_content_host,)
    finally:
        root.destroy()


def test_440_native_canvases_do_not_leak_system_default_background():
    root, app = _open()
    try:
        assert app.left_scroll_canvas.cget("background").lower() == WHD_THEME["background"].lower(), (
            "INTENDED_RED_LEFT_SCROLL_CANVAS_SHELL_BG"
        )
        assert app._phase6_assembly_panel_owner.canvas.cget("background").lower() == WHD_THEME["panel"].lower(), (
            "INTENDED_RED_ASSEMBLY_CANVAS_DEFAULT_BG"
        )
    finally:
        root.destroy()
