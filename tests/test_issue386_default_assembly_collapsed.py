# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import re
import tkinter as tk

import pytest

import fold_designer_bridge as bridge


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="#386 requires real Tk/Xvfb"
)


def _pump(root, cycles=2):
    for _ in range(cycles):
        root.update_idletasks()
        root.update()


def _open_simple():
    root = tk.Tk()
    root.geometry("1200x850+0+0")
    app = bridge.Phase6FoldDesignerApp(root, {
        "model": "金庫型",
        "w": 500, "h": 600, "d": 200,
        "existing_parts": ["box_body", "head", "tail", "door", "base_plate"],
        "active_part": "box_body",
        "settings": {"t": 2.0, "fw": 24.0},
    })
    _pump(root, 3)
    return root, app


def test_fresh_logical_assembly_rows_default_collapsed():
    root, app = _open_simple()
    try:
        assert app.assembly_part_detail_frames
        for key, details in app.assembly_part_detail_frames.items():
            assert details.winfo_manager() == "", f"RED: {key} fresh detail is expanded"
            assert str(app.assembly_part_detail_buttons[key].cget("text")) == "▸"
            assert app.assembly_part_checkbuttons[key].winfo_manager() != ""
    finally:
        root.destroy()


def test_fresh_receiving_presentation_parents_and_children_default_collapsed():
    import gui

    root = tk.Tk()
    root.withdraw()
    designer = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("受電箱")
        _pump(root, 2)
        designer = app.open_original_fold_designer()
        _pump(root, 3)
        bridge._phase6_show_assembly(designer)
        _pump(root, 2)

        assert {"door", "base_plate"}.issubset(
            designer.assembly_presentation_group_detail_frames
        )
        for key in ("door", "base_plate"):
            details = designer.assembly_presentation_group_detail_frames[key]
            assert details.winfo_manager() == "", f"RED: {key} parent group is expanded"
            assert str(
                designer.assembly_presentation_group_detail_buttons[key].cget("text")
            ) == "▸"

        dynamic = tuple(
            key for key in designer.assembly_part_detail_frames
            if re.fullmatch(r"(?:door|base_plate)_c\d+_r\d+", key)
        )
        assert dynamic
        for key in dynamic:
            assert designer.assembly_part_detail_frames[key].winfo_manager() == ""
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        root.destroy()


def test_fresh_box_body_physical_piece_rows_default_collapsed_when_present():
    import gui

    root = tk.Tk()
    root.withdraw()
    designer = None
    try:
        app = gui.BoxCalculatorGUI(root)
        app.baseline_var.set("受電箱")
        _pump(root, 2)
        designer = app.open_original_fold_designer()
        _pump(root, 3)
        bridge._phase6_show_assembly(designer)
        bridge._phase6_query_assembly_render_data(designer)
        _pump(root, 3)

        keys = tuple(designer.assembly_box_body_piece_detail_frames)
        assert keys, "receiving precondition: resolved BoxBody physical children"
        for key in keys:
            assert designer.assembly_box_body_piece_detail_frames[key].winfo_manager() == "", (
                f"RED: {key} physical child detail is expanded"
            )
            assert str(
                designer.assembly_box_body_piece_detail_buttons[key].cget("text")
            ) == "▸"
    finally:
        try:
            if designer is not None:
                designer.root.destroy()
        except Exception:
            pass
        root.destroy()


def test_collapsing_and_visibility_are_independent_presentation_states():
    root, app = _open_simple()
    try:
        key = "head"
        visible = app.assembly_part_visible_vars[key]
        details = app.assembly_part_detail_frames[key]
        texts = (
            app.assembly_part_formed_vars[key].get(),
            app.assembly_part_blank_vars[key].get(),
            app.assembly_part_corner_vars[key].get(),
        )

        app._phase6_assembly_panel_owner.set_part_details_open(key, False)
        visible.set(False)
        bridge._phase6_on_assembly_part_visibility_changed(app)
        _pump(root, 2)

        assert details.winfo_manager() == ""
        assert bool(visible.get()) is False
        assert (
            app.assembly_part_formed_vars[key].get(),
            app.assembly_part_blank_vars[key].get(),
            app.assembly_part_corner_vars[key].get(),
        ) == texts

        app._phase6_assembly_panel_owner.set_part_details_open(key, True)
        _pump(root)
        assert details.winfo_manager() == "pack"
        assert bool(visible.get()) is False
    finally:
        root.destroy()


def test_explicit_collapse_state_survives_panel_rebuild_without_domain_mutation():
    root, app = _open_simple()
    try:
        key = "tail"
        app._phase6_assembly_panel_owner.set_part_details_open(key, False)
        app.assembly_part_visible_vars[key].set(False)
        text_before = (
            app.assembly_part_formed_vars[key].get(),
            app.assembly_part_blank_vars[key].get(),
            app.assembly_part_corner_vars[key].get(),
        )

        bridge._phase6_refresh_assembly_parts_panel(app)
        _pump(root, 2)

        assert app.assembly_part_detail_frames[key].winfo_manager() == ""
        assert bool(app.assembly_part_visible_vars[key].get()) is False
        assert (
            app.assembly_part_formed_vars[key].get(),
            app.assembly_part_blank_vars[key].get(),
            app.assembly_part_corner_vars[key].get(),
        ) == text_before
        assert key in app.designer_workspace.available_parts
    finally:
        root.destroy()
