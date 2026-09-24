# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tkinter as tk

import pytest

import fold_designer_bridge as bridge


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="#439/#440 shared-slot contract requires real Tk/Xvfb"
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


def _pump(root, cycles=4):
    for _ in range(cycles):
        root.update_idletasks()
        root.update()


def _open():
    root = tk.Tk()
    root.geometry("1200x850+0+0")
    app = bridge.Phase6FoldDesignerApp(root, _snapshot())
    _pump(root)
    return root, app


def _mapped(app):
    return tuple(
        w for w in (
            app.input_content_host,
            app.assembly_parts_panel,
            getattr(app, "corner_data_panel", None),
        )
        if w is not None and w.winfo_manager()
    )


def test_issue439_440_no_extra_physical_wrapper_frame():
    root, app = _open()
    try:
        assert app.shared_content_host is app.left
        assert app.fold_editor_host is app.input_content_host
        assert app.input_content_host.master is app.left
        assert app.assembly_parts_panel.master is app.left
        assert not hasattr(app, "_phase6_physical_content_height")

        bridge._phase6_show_corner_data(app)
        _pump(root)
        assert app.corner_data_panel.master is app.left
    finally:
        root.destroy()


def test_issue439_440_same_slot_switches_one_direct_surface_without_fixed_shell():
    root, app = _open()
    try:
        app.activate_part("head")
        _pump(root)
        assert _mapped(app) == (app.input_content_host,)

        bridge._phase6_show_assembly(app)
        _pump(root)
        assert _mapped(app) == (app.assembly_parts_panel,)

        bridge._phase6_show_corner_data(app)
        _pump(root)
        assert _mapped(app) == (app.corner_data_panel,)

        app.activate_part(app.designer_workspace.active_part)
        _pump(root)
        assert _mapped(app) == (app.input_content_host,)
    finally:
        root.destroy()
