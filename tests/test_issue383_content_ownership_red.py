# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tkinter as tk

import pytest

import fold_designer_bridge as bridge


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="#383 requires real Tk/Xvfb"
)


def _open(parts=None):
    root = tk.Tk()
    root.geometry("1200x850+0+0")
    app = bridge.Phase6FoldDesignerApp(root, {
        "model": "金庫型",
        "w": 500,
        "h": 600,
        "d": 200,
        "existing_parts": list(parts or ("box_body", "head", "tail", "door", "base_plate")),
        "active_part": "box_body",
        "settings": {"t": 2.0, "fw": 24.0},
    })
    for _ in range(3):
        root.update_idletasks()
        root.update()
    return root, app


def test_target_normal_part_does_not_reserve_or_show_structure_tree():
    root, app = _open()
    try:
        app.activate_part("head")
        root.update_idletasks(); root.update()

        assert app._phase6_3d_display_mode == "single"
        assert app.fold_editor_host.winfo_manager() != ""
        assert app.structure_tree_host.winfo_manager() == "", (
            "RED: 板件/功能 is still a separately reserved sticky region in normal part mode"
        )
        assert app.structure_tree_spacer.winfo_manager() == "", (
            "RED: old 板件/功能 spacer still consumes shared input/display layout space"
        )
    finally:
        root.destroy()


def test_target_assembly_uses_assembly_content_without_second_visible_structure_tree():
    root, app = _open()
    try:
        bridge._phase6_show_assembly(app)
        root.update_idletasks(); root.update()

        assert app._phase6_3d_display_mode == "assembly"
        assert app.assembly_parts_panel.winfo_manager() != ""
        assert app.structure_tree_host.winfo_manager() == "", (
            "RED: 組合體 still shows a second Structure Tree instead of one merged part/data list"
        )
    finally:
        root.destroy()


def test_target_fresh_assembly_rows_default_collapsed_but_keep_visibility_controls():
    root, app = _open()
    try:
        bridge._phase6_show_assembly(app)
        root.update_idletasks(); root.update()

        assert app.assembly_part_visible_vars
        for key in app.assembly_part_visible_vars:
            assert app.assembly_part_checkbuttons[key].winfo_manager() != ""
            assert app.assembly_part_detail_frames[key].winfo_manager() == "", (
                f"RED: {key} detail body still defaults expanded"
            )
            assert str(app.assembly_part_detail_buttons[key].cget("text")) == "▸"
    finally:
        root.destroy()


def test_target_dynamic_door_and_base_plate_children_have_presentation_only_parent_groups():
    helper = getattr(bridge, "_phase6_assembly_presentation_groups", None)
    assert callable(helper), (
        "RED: no assembly-only presentation grouping exists for Door/Base Plate physical children"
    )

    groups = helper((
        "box_body",
        "head",
        "tail",
        "door_c1_r1",
        "door_c1_r2",
        "base_plate_c1_r1",
        "base_plate_c1_r2",
    ))
    by_key = {group[0]: tuple(group[1]) for group in groups}
    assert by_key["door"] == ("door_c1_r1", "door_c1_r2")
    assert by_key["base_plate"] == ("base_plate_c1_r1", "base_plate_c1_r2")
    assert "door" not in (
        "box_body", "head", "tail", "door_c1_r1", "door_c1_r2",
        "base_plate_c1_r1", "base_plate_c1_r2",
    ), "presentation grouping must not require a fake workspace aggregate"
