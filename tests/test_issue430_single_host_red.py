# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tkinter as tk

import pytest

import fold_designer_bridge as bridge


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="#430 T0 requires real Tk/Xvfb"
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


def _direct_content_host(widget, left):
    current = widget
    seen = set()
    while current is not None and getattr(current, "master", None) is not left:
        marker = str(current)
        assert marker not in seen, "widget master chain looped"
        seen.add(marker)
        current = getattr(current, "master", None)
    assert current is not None, "content surface is not owned by the left workspace"
    return current


def _show_mode(app, root, mode):
    if mode == "single":
        target = "head" if "head" in app.designer_workspace.available_parts else "box_body"
        app.activate_part(target)
        surface = app.input_content_host
    elif mode == "assembly":
        bridge._phase6_show_assembly(app)
        surface = app.assembly_parts_panel
    elif mode == "corner_data":
        bridge._phase6_show_corner_data(app)
        surface = app.corner_data_panel
    else:
        raise AssertionError(mode)
    _pump(root)
    assert surface is not None
    assert surface.winfo_manager() != ""
    return surface


def _mode_surfaces(app, root):
    return tuple(_show_mode(app, root, mode) for mode in ("single", "assembly", "corner_data"))


def _surface_identity(app):
    return (
        id(app.input_content_host),
        id(app.assembly_parts_panel),
        id(app.corner_data_panel),
    )


def _mapped_mode_surface_count(app):
    widgets = (
        getattr(app, "input_content_host", None),
        getattr(app, "assembly_parts_panel", None),
        getattr(app, "corner_data_panel", None),
    )
    return sum(1 for widget in widgets if widget is not None and widget.winfo_manager())


def test_t0_mode_authority_stays_workspace_plus_existing_display_mode():
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

        bridge._phase6_show_corner_data(app)
        _pump(root)
        assert app._phase6_3d_display_mode == "corner_data"
        assert app.designer_workspace.active_part == active

        app.activate_part(app.designer_workspace.active_part)
        _pump(root)
        assert app._phase6_3d_display_mode == "single"
        assert app.designer_workspace.active_part == active
        assert not hasattr(app, "shared_content_active_part")
    finally:
        root.destroy()


def test_t0_repeated_switch_reuses_existing_mode_surface_objects():
    root, app = _open()
    try:
        _mode_surfaces(app, root)
        first = _surface_identity(app)
        assert _mapped_mode_surface_count(app) == 1

        for _ in range(4):
            _mode_surfaces(app, root)
            assert _surface_identity(app) == first
            assert _mapped_mode_surface_count(app) == 1
    finally:
        root.destroy()


def test_t0_refresh_add_delete_does_not_accumulate_mode_surfaces():
    root, app = _open()
    try:
        _mode_surfaces(app, root)
        first = _surface_identity(app)

        app._refresh_part_buttons()
        bridge._phase6_refresh_assembly_parts_panel_if_topology_changed(app)
        _pump(root)

        if "door" not in app.designer_workspace.available_parts:
            bridge._fix11_add_part(app, "door")
            _pump(root)
            assert "door" in app.designer_workspace.available_parts
            assert bridge._fix11_remove_part(app, "door") is True
            _pump(root)

        _mode_surfaces(app, root)
        assert _surface_identity(app) == first
        assert _mapped_mode_surface_count(app) == 1
    finally:
        root.destroy()


def test_t0_fresh_workspace_reopen_has_no_cross_instance_widget_reuse():
    roots = []
    apps = []
    try:
        for _ in range(2):
            root, app = _open()
            roots.append(root)
            apps.append(app)
            _mode_surfaces(app, root)
            assert _mapped_mode_surface_count(app) == 1

        first_ids = set(_surface_identity(apps[0]))
        second_ids = set(_surface_identity(apps[1]))
        assert first_ids.isdisjoint(second_ids)
    finally:
        for root in roots:
            try:
                root.destroy()
            except Exception:
                pass


def test_t0_intended_red_all_three_modes_require_one_direct_shared_content_host():
    root, app = _open()
    try:
        surfaces = _mode_surfaces(app, root)
        hosts = tuple(_direct_content_host(surface, app.left) for surface in surfaces)
        host_paths = tuple(str(host) for host in hosts)
        assert len(set(host_paths)) == 1, (
            "INTENDED_RED_DUPLICATE_REGION: normal/assembly/corner-data currently "
            f"resolve to {len(set(host_paths))} direct left-content hosts: {host_paths}"
        )
    finally:
        root.destroy()
