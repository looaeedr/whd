# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tkinter as tk

import pytest

import fold_designer_bridge as bridge


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="#433 T3 requires real Tk/Xvfb"
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


def _assembly_mounted_count(app):
    return sum(
        1
        for child in app.shared_content_host.winfo_children()
        if child is app.assembly_parts_panel and child.winfo_manager()
    )


def test_t3_existing_phase5_panel_owner_is_the_shared_host_assembly_content():
    root, app = _open()
    try:
        owner = app._phase6_assembly_panel_owner
        assert owner.host is app.assembly_parts_panel
        assert owner.host.master is app.shared_content_host
        assert app.assembly_parts_panel.master is app.shared_content_host
        assert app.assembly_part_visible_vars is owner.visible_vars
        assert app.assembly_part_detail_frames is owner.detail_frames
        assert app.assembly_part_detail_buttons is owner.detail_buttons
        assert app.assembly_box_body_piece_visible_vars is owner.box_piece_visible_vars
    finally:
        root.destroy()


def test_t3_assembly_tree_is_mounted_once_when_active_and_zero_when_inactive():
    root, app = _open()
    try:
        assert _assembly_mounted_count(app) == 1
        assert app._phase6_3d_display_mode == "assembly"

        app.activate_part("head")
        _pump(root)
        assert _assembly_mounted_count(app) == 0
        assert app.assembly_parts_panel.winfo_manager() == ""

        bridge._phase6_show_corner_data(app)
        _pump(root)
        assert _assembly_mounted_count(app) == 0
        assert app.assembly_parts_panel.winfo_manager() == ""

        bridge._phase6_show_assembly(app)
        _pump(root)
        assert _assembly_mounted_count(app) == 1
        assert app.assembly_parts_panel.winfo_manager() != ""
    finally:
        root.destroy()


def test_t3_visibility_var_identity_and_value_survive_mode_roundtrip():
    root, app = _open()
    try:
        owner = app._phase6_assembly_panel_owner
        keys = tuple(owner.visible_vars)
        assert keys
        target = "head" if "head" in owner.visible_vars else keys[0]

        var = owner.visible_vars[target]
        assert bridge._phase6_structure_tree_visibility_var(app, target) is var
        before = bool(var.get())
        var.set(not before)

        app.activate_part("head")
        _pump(root)
        bridge._phase6_show_corner_data(app)
        _pump(root)
        bridge._phase6_show_assembly(app)
        _pump(root)

        assert owner.visible_vars[target] is var
        assert bridge._phase6_structure_tree_visibility_var(app, target) is var
        assert bool(var.get()) is (not before)
    finally:
        root.destroy()


def test_t3_collapse_state_and_details_data_survive_mode_roundtrip():
    root, app = _open()
    try:
        owner = app._phase6_assembly_panel_owner
        keys = tuple(owner.detail_frames)
        assert keys
        target = "head" if "head" in owner.detail_frames else keys[0]

        details = owner.detail_frames[target]
        formed = owner.formed_vars[target]
        blank = owner.blank_vars[target]
        corner = owner.corner_vars[target]
        text_before = (formed.get(), blank.get(), corner.get())

        assert details.winfo_manager() == ""
        assert owner.set_part_details_open(target, True) is True
        _pump(root)
        assert details.winfo_manager() == "pack"

        app.activate_part("head")
        _pump(root)
        bridge._phase6_show_assembly(app)
        _pump(root)

        assert owner.detail_frames[target] is details
        assert details.winfo_manager() == "pack"
        assert (formed.get(), blank.get(), corner.get()) == text_before

        assert owner.set_part_details_open(target, False) is False
        _pump(root)
        assert details.winfo_manager() == ""
        assert (formed.get(), blank.get(), corner.get()) == text_before
    finally:
        root.destroy()
