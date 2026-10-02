# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tkinter as tk

import pytest

import fold_designer_bridge as bridge


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="#384 requires real Tk/Xvfb"
)


def _open():
    root = tk.Tk()
    root.geometry("1200x850+0+0")
    app = bridge.Phase6FoldDesignerApp(root, {
        "model": "金庫型",
        "w": 500, "h": 600, "d": 200,
        "existing_parts": ["box_body", "head", "tail", "door", "base_plate"],
        "active_part": "box_body",
        "settings": {"t": 2.0, "fw": 24.0},
    })
    for _ in range(3):
        root.update_idletasks(); root.update()
    return root, app


def test_normal_part_has_no_reserved_structure_tree_region():
    root, app = _open()
    try:
        app.activate_part("head")
        root.update_idletasks(); root.update()

        assert app._phase6_3d_display_mode == "single"
        assert app.fold_editor_host.winfo_manager() != ""
        assert app.assembly_parts_panel.winfo_manager() == ""
        assert app.structure_tree_host.winfo_manager() == "", (
            "RED: old 板件/功能 host is still mapped during normal part input"
        )
        assert app.structure_tree_spacer.winfo_manager() == "", (
            "RED: old 板件/功能 spacer still reserves layout height"
        )
    finally:
        root.destroy()


def test_assembly_uses_single_assembly_content_without_structure_tree_overlay():
    root, app = _open()
    try:
        bridge._phase6_show_assembly(app)
        root.update_idletasks(); root.update()

        assert app._phase6_3d_display_mode == "assembly"
        assert app.assembly_parts_panel.winfo_manager() != ""
        assert app.fold_editor_host.winfo_manager() == ""
        assert app.structure_tree_host.winfo_manager() == "", (
            "RED: second 板件/功能 Structure Tree is still visible above assembly content"
        )
        assert app.structure_tree_spacer.winfo_manager() == ""
    finally:
        root.destroy()


def test_normal_and_assembly_content_share_same_left_content_owner():
    root, app = _open()
    try:
        # #440 superseded the old wrapper-host model: the shared mount owner is
        # self.left itself, and all mode surfaces are direct siblings. Keeping an
        # extra Frame here would reintroduce the rejected "大框包小框" layout.
        shared = app.shared_content_host
        assert shared is app.left
        assert app.fold_editor_host is app.input_content_host
        assert app.fold_editor_host.master is shared
        assert app.assembly_parts_panel.master is shared
    finally:
        root.destroy()
