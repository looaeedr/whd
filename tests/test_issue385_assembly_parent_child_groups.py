# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
import tkinter as tk

import pytest

import fold_designer_bridge as bridge


def test_presentation_groups_nest_dynamic_doors_and_baseplates_without_fake_domain_parts():
    helper = getattr(bridge, "_phase6_assembly_presentation_groups", None)
    assert callable(helper), "RED: assembly presentation grouping helper is missing"

    parts = (
        "box_body",
        "head",
        "tail",
        "door_c1_r1",
        "door_c1_r2",
        "base_plate_c1_r1",
        "base_plate_c1_r2",
        "indicator_box",
    )
    groups = helper(parts)
    assert groups == (
        ("box_body", ()),
        ("head", ()),
        ("tail", ()),
        ("door", ("door_c1_r1", "door_c1_r2")),
        ("base_plate", ("base_plate_c1_r1", "base_plate_c1_r2")),
        ("indicator_box", ()),
    )
    assert "door" not in parts
    assert "base_plate" not in parts


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="#385 requires real Tk/Xvfb")
def test_receiving_assembly_renders_dynamic_children_under_presentation_parents():
    import gui

    root = tk.Tk()
    root.withdraw()
    designer = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()

        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        bridge._phase6_show_assembly(designer)
        bridge._phase6_query_assembly_render_data(designer)
        root.update_idletasks(); root.update()

        available = tuple(str(k) for k in designer.designer_workspace.available_parts)
        doors = tuple(k for k in available if re.fullmatch(r"door_c\d+_r\d+", k))
        bases = tuple(k for k in available if re.fullmatch(r"base_plate_c\d+_r\d+", k))
        assert doors and bases
        assert "door" not in available
        assert "base_plate" not in available

        group_frames = designer.assembly_presentation_group_detail_frames
        sections = designer.assembly_part_sections
        assert "door" in group_frames
        assert "base_plate" in group_frames

        for key in doors:
            assert key in designer.assembly_part_visible_vars
            assert key in designer.assembly_part_detail_frames
            assert sections[key].master is group_frames["door"]
        for key in bases:
            assert key in designer.assembly_part_visible_vars
            assert key in designer.assembly_part_detail_frames
            assert sections[key].master is group_frames["base_plate"]

        # Synthetic presentation parents must not become visibility/domain owners.
        assert "door" not in designer.assembly_part_visible_vars
        assert "base_plate" not in designer.assembly_part_visible_vars
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        root.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="#385 requires real Tk/Xvfb")
def test_group_parent_toggle_is_presentation_only_and_child_visibility_survives():
    import gui

    root = tk.Tk()
    root.withdraw()
    designer = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("受電箱")
        root.update_idletasks(); root.update()
        designer = app.open_original_fold_designer()
        root.update_idletasks(); root.update()
        bridge._phase6_show_assembly(designer)
        root.update_idletasks(); root.update()

        door_keys = tuple(
            key for key in designer.assembly_part_visible_vars
            if re.fullmatch(r"door_c\d+_r\d+", key)
        )
        assert door_keys
        before = {key: bool(designer.assembly_part_visible_vars[key].get()) for key in door_keys}

        button = designer.assembly_presentation_group_detail_buttons["door"]
        details = designer.assembly_presentation_group_detail_frames["door"]
        assert details.winfo_manager() == ""
        button.invoke()
        root.update_idletasks(); root.update()
        assert details.winfo_manager() != ""

        after = {key: bool(designer.assembly_part_visible_vars[key].get()) for key in door_keys}
        assert after == before
        assert "door" not in designer.designer_workspace.available_parts
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        root.destroy()
