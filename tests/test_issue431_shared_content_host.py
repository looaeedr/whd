# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tkinter as tk

import pytest

import fold_designer_bridge as bridge


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="#431 T1 requires real Tk/Xvfb"
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


def _pump(root, cycles=2):
    for _ in range(cycles):
        root.update_idletasks()
        root.update()


def _open():
    root = tk.Tk()
    root.geometry("1200x850+0+0")
    app = bridge.Phase6FoldDesignerApp(root, _snapshot())
    _pump(root, 3)
    return root, app


def _first_direct_child_under(widget, ancestor):
    current = widget
    seen = set()
    while current is not None and getattr(current, "master", None) is not ancestor:
        marker = id(current)
        assert marker not in seen, "widget master chain looped"
        seen.add(marker)
        current = getattr(current, "master", None)
    assert current is not None, "content surface is outside the left workspace"
    return current


def _ensure_all_surfaces(app, root):
    app.activate_part("head")
    _pump(root)
    bridge._phase6_show_assembly(app)
    _pump(root)
    bridge._phase6_show_corner_data(app)
    _pump(root)
    return (
        app.input_content_host,
        app.assembly_parts_panel,
        app.corner_data_panel,
    )


def test_t1_existing_workspace_and_display_mode_authorities_are_preserved():
    root, app = _open()
    try:
        app.activate_part("head")
        _pump(root)
        active = app.designer_workspace.active_part
        assert active == "head"
        assert app._phase6_3d_display_mode == "single"

        bridge._phase6_show_assembly(app)
        _pump(root)
        assert app._phase6_3d_display_mode == "assembly"
        assert app.designer_workspace.active_part == active
        assert app.part_var.get() == "組合體"

        bridge._phase6_show_corner_data(app)
        _pump(root)
        assert app._phase6_3d_display_mode == "corner_data"
        assert app.designer_workspace.active_part == active
        assert app.part_var.get() == "截角資料"

        app.activate_part(app.designer_workspace.active_part)
        _pump(root)
        assert app._phase6_3d_display_mode == "single"
        assert app.designer_workspace.active_part == active
        assert not hasattr(app, "shared_content_active_part")
        assert not hasattr(app, "shared_content_mode_var")
    finally:
        root.destroy()


def test_t1_one_dedicated_shared_host_owns_all_three_existing_mode_surfaces():
    root, app = _open()
    try:
        surfaces = _ensure_all_surfaces(app, root)
        shared = getattr(app, "shared_content_host", None)
        assert shared is app.left, "shared mount parent must be the left workspace itself"
        assert all(surface.master is shared for surface in surfaces), (
            "all three mode surfaces must be direct siblings in one left-side slot"
        )
    finally:
        root.destroy()


def test_t1_mode_controller_mounts_exactly_one_existing_content_tree():
    root, app = _open()
    try:
        _ensure_all_surfaces(app, root)
        shared = getattr(app, "shared_content_host", None)
        assert shared is not None, "INTENDED_RED_SHARED_CONTENT_CONTROLLER_MISSING"

        sequence = (
            ("single", lambda: app.activate_part("head"), app.input_content_host),
            ("assembly", lambda: bridge._phase6_show_assembly(app), app.assembly_parts_panel),
            ("corner_data", lambda: bridge._phase6_show_corner_data(app), app.corner_data_panel),
            ("single", lambda: app.activate_part(app.designer_workspace.active_part), app.input_content_host),
        )
        surfaces = (
            app.input_content_host,
            app.assembly_parts_panel,
            app.corner_data_panel,
        )

        for mode, action, expected in sequence:
            action()
            _pump(root)
            assert app._phase6_3d_display_mode == mode
            assert shared.winfo_manager() != ""
            assert all(surface.master is shared for surface in surfaces)
            mapped = [surface for surface in surfaces if surface.winfo_manager()]
            assert mapped == [expected], (
                f"mode={mode} mounted {[str(widget) for widget in mapped]} "
                f"instead of only {expected}"
            )
    finally:
        root.destroy()
