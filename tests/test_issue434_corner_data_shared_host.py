# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tkinter as tk

import pytest

import fold_designer_bridge as bridge


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="#434 T4 requires real Tk/Xvfb"
)


def _snapshot():
    return {
        "model": "金庫型",
        "w": 500,
        "h": 600,
        "d": 200,
        "existing_parts": ["box_body", "head", "tail", "door", "base_plate"],
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


def _corner_mounted_count(app):
    panel = getattr(app, "corner_data_panel", None)
    return sum(
        1
        for child in app.shared_content_host.winfo_children()
        if child is panel and child.winfo_manager()
    )


def test_t4_corner_data_panel_is_the_shared_host_corner_content():
    root, app = _open()
    try:
        bridge._phase6_show_corner_data(app)
        _pump(root)

        panel = app.corner_data_panel
        assert panel.master is app.shared_content_host
        assert panel.winfo_manager() != ""
        assert _corner_mounted_count(app) == 1
        assert app.fold_editor_host is app.input_content_host
        assert app.input_content_host.winfo_manager() == ""
        assert app.assembly_parts_panel.winfo_manager() == ""
        assert app._phase6_3d_display_mode == "corner_data"
    finally:
        root.destroy()


def test_t4_corner_data_tree_is_mounted_once_when_active_and_zero_when_inactive():
    root, app = _open()
    try:
        bridge._phase6_show_corner_data(app)
        _pump(root)
        panel = app.corner_data_panel

        assert _corner_mounted_count(app) == 1

        app.activate_part("head")
        _pump(root)
        assert app.corner_data_panel is panel
        assert _corner_mounted_count(app) == 0
        assert panel.winfo_manager() == ""

        bridge._phase6_show_assembly(app)
        _pump(root)
        assert app.corner_data_panel is panel
        assert _corner_mounted_count(app) == 0

        bridge._phase6_show_corner_data(app)
        _pump(root)
        assert app.corner_data_panel is panel
        assert _corner_mounted_count(app) == 1
    finally:
        root.destroy()


def test_t4_corner_data_adapter_is_single_state_owner_and_selection_is_view_only():
    root, app = _open()
    try:
        bridge._phase6_show_corner_data(app)
        _pump(root)
        adapter = bridge._phase6_corner_data_view(app)
        before_workspace = (
            app.designer_workspace.active_part,
            app.designer_workspace.selected_part,
            tuple(app.designer_workspace.available_parts),
        )

        # This test validates navigation/state ownership only. A directly
        # constructed Fold Designer intentionally has no main-GUI final-scene
        # provider, so do not ask the selection helper to render an unfold.
        resolved = bridge._phase6_select_corner_data_part(
            app, "head", refresh_view=False
        )
        _pump(root)

        assert resolved == "head"
        assert bridge._phase6_corner_data_view(app) is adapter
        assert adapter.selected_part_key == "head"
        assert app._phase6_corner_data_selected_part_key == "head"
        assert (
            app.designer_workspace.active_part,
            app.designer_workspace.selected_part,
            tuple(app.designer_workspace.available_parts),
        ) == before_workspace

        # Presentation mount roundtrip must not create or replace selection
        # authority. Use the mount seam directly so this ownership test remains
        # independent of the final-scene provider.
        app._phase6_3d_display_mode = "assembly"
        bridge._phase6_mount_shared_content(app, "assembly")
        _pump(root)
        assert _corner_mounted_count(app) == 0

        app._phase6_3d_display_mode = "corner_data"
        bridge._phase6_mount_shared_content(app, "corner_data")
        _pump(root)

        assert _corner_mounted_count(app) == 1
        assert bridge._phase6_corner_data_view(app) is adapter
        assert adapter.selected_part_key == "head"
        assert app._phase6_corner_data_selected_part_key == "head"
    finally:
        root.destroy()


def test_t4_corner_data_refresh_reuses_panel_and_adapter_without_second_authority():
    root, app = _open()
    try:
        bridge._phase6_show_corner_data(app)
        _pump(root)
        panel = app.corner_data_panel
        adapter = bridge._phase6_corner_data_view(app)

        bridge._phase6_select_corner_data_part(app, "tail", refresh_view=False)

        # Panel-list refresh is a view projection and is legal while the
        # Corner Data surface is unmounted. This avoids coupling the ownership
        # test to a final-scene provider while still exercising repeated rebuild.
        app._phase6_3d_display_mode = "assembly"
        bridge._phase6_mount_shared_content(app, "assembly")
        _pump(root)

        first_keys = tuple(bridge._phase6_refresh_corner_data_parts_panel(app))
        _pump(root)
        second_keys = tuple(bridge._phase6_refresh_corner_data_parts_panel(app))
        _pump(root)

        assert app.corner_data_panel is panel
        assert panel.master is app.shared_content_host
        assert bridge._phase6_corner_data_view(app) is adapter
        assert first_keys == second_keys == tuple(app.designer_workspace.available_parts)
        assert adapter.selected_part_key == "tail"
        assert app._phase6_corner_data_selected_part_key == "tail"
        assert _corner_mounted_count(app) == 0

        app._phase6_3d_display_mode = "corner_data"
        bridge._phase6_mount_shared_content(app, "corner_data")
        _pump(root)
        assert _corner_mounted_count(app) == 1
        assert bridge._phase6_corner_data_view(app) is adapter
        assert adapter.selected_part_key == "tail"
    finally:
        root.destroy()
