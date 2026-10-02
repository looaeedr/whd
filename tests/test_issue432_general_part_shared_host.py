# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tkinter as tk

import pytest

import fold_designer_bridge as bridge


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="#432 T2 requires real Tk/Xvfb"
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


def _open(**kwargs):
    root = tk.Tk()
    root.geometry("1200x850+0+0")
    app = bridge.Phase6FoldDesignerApp(root, _snapshot(), **kwargs)
    _pump(root, 3)
    return root, app


def _assert_part_mode_only(app):
    assert app._phase6_3d_display_mode == "single"
    assert app.shared_content_host is app.left
    assert app.fold_editor_host is app.input_content_host
    assert app.input_content_host.master is app.left
    assert app.input_content_host.winfo_manager() != ""
    assert app.assembly_parts_panel.master is app.left
    assert app.assembly_parts_panel.winfo_manager() == ""
    panel = getattr(app, "corner_data_panel", None)
    if panel is not None:
        assert panel.master is app.left
        assert panel.winfo_manager() == ""


def test_t2_part_mode_uses_shared_host_and_unmounts_other_mode_trees():
    root, app = _open()
    try:
        bridge._phase6_show_corner_data(app)
        _pump(root)
        bridge._phase6_show_assembly(app)
        _pump(root)
        app.activate_part("head")
        _pump(root)

        assert app.designer_workspace.active_part == "head"
        _assert_part_mode_only(app)
    finally:
        root.destroy()


def test_t2_part_display_roundtrip_preserves_active_part_and_editor_identity():
    root, app = _open()
    try:
        app.activate_part("head")
        _pump(root)
        before_active = app.designer_workspace.active_part
        before_label = app.part_var.get()
        before_editor = app.fold_editor_host
        before_bend_ui = app.bend_ui

        bridge._phase6_show_assembly(app)
        _pump(root)
        bridge._phase6_show_corner_data(app)
        _pump(root)
        app.activate_part(app.designer_workspace.active_part)
        _pump(root)

        assert app.designer_workspace.active_part == before_active
        assert app.part_var.get() == before_label
        assert app.fold_editor_host is before_editor
        assert app.bend_ui is before_bend_ui
        _assert_part_mode_only(app)
    finally:
        root.destroy()


def test_t2_part_input_callback_bindings_survive_mode_roundtrip():
    callbacks = {
        "on_settings_change": lambda *_args, **_kwargs: None,
        "on_live_sync": lambda *_args, **_kwargs: None,
        "on_part_spec_query": lambda *_args, **_kwargs: None,
        "on_project_load": lambda *_args, **_kwargs: None,
        "on_project_save": lambda *_args, **_kwargs: None,
    }
    root, app = _open(**callbacks)
    try:
        before = {
            "_settings_change_callback": app._settings_change_callback,
            "_live_sync_callback": app._live_sync_callback,
            "_part_spec_query_callback": app._part_spec_query_callback,
            "_project_load_callback": app._project_load_callback,
            "_project_save_callback": app._project_save_callback,
        }

        app.activate_part("head")
        _pump(root)
        bridge._phase6_show_assembly(app)
        _pump(root)
        bridge._phase6_show_corner_data(app)
        _pump(root)
        app.activate_part(app.designer_workspace.active_part)
        _pump(root)

        after = {name: getattr(app, name) for name in before}
        assert after == before
        _assert_part_mode_only(app)
    finally:
        root.destroy()


def test_t2_add_delete_part_keeps_normal_part_on_shared_host():
    root, app = _open()
    try:
        bridge._phase6_show_corner_data(app)
        _pump(root)
        app.activate_part(app.designer_workspace.active_part)
        _pump(root)

        assert "door" not in app.designer_workspace.available_parts
        bridge._fix11_add_part(app, "door")
        _pump(root)

        assert "door" in app.designer_workspace.available_parts
        assert app.designer_workspace.active_part in app.designer_workspace.available_parts
        _assert_part_mode_only(app)

        assert bridge._fix11_remove_part(app, "door") is True
        _pump(root)

        assert "door" not in app.designer_workspace.available_parts
        assert app.designer_workspace.active_part in app.designer_workspace.available_parts
        _assert_part_mode_only(app)
    finally:
        root.destroy()
