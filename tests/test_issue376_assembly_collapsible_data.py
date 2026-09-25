# -*- coding: utf-8 -*-
import os
import tkinter as tk

import pytest

import fold_designer_bridge as bridge


pytestmark = pytest.mark.skipif(
    not os.environ.get("DISPLAY"), reason="#376 requires real Tk/Xvfb"
)


def _open():
    root = tk.Tk()
    root.geometry("1200x850+0+0")
    app = bridge.Phase6FoldDesignerApp(root, {
        "w": 500,
        "h": 600,
        "d": 200,
        "existing_parts": ["box_body", "head", "tail"],
        "active_part": "box_body",
        "settings": {"t": 2.0, "fw": 24.0},
    })
    root.update_idletasks()
    root.update()
    return root, app


def _pump(root, cycles=2):
    for _ in range(cycles):
        root.update_idletasks()
        root.update()


def _assert_read_only_tree(widget):
    stack = [widget]
    while stack:
        current = stack.pop()
        klass = str(current.winfo_class())
        assert klass not in {"TEntry", "Entry", "TCombobox", "Spinbox", "TSpinbox"}, (
            f"assembly details gained an editable widget: {klass}"
        )
        stack.extend(current.winfo_children())


def test_each_assembly_part_keeps_existing_visibility_and_data_in_collapsible_details():
    root, app = _open()
    try:
        keys = tuple(app.assembly_part_visible_vars)
        assert keys
        assert set(app.assembly_part_detail_frames) == set(keys)
        assert set(app.assembly_part_detail_buttons) == set(keys)

        for key in keys:
            details = app.assembly_part_detail_frames[key]
            button = app.assembly_part_detail_buttons[key]
            assert details.winfo_manager() == ""
            assert str(button.cget("text")) == "▸"
            _assert_read_only_tree(details)

        target = "head" if "head" in keys else keys[0]
        visible = app.assembly_part_visible_vars[target]
        formed = app.assembly_part_formed_vars[target]
        blank = app.assembly_part_blank_vars[target]
        corner = app.assembly_part_corner_vars[target]

        visible_before = bool(visible.get())
        text_before = (formed.get(), blank.get(), corner.get())

        app.assembly_part_detail_buttons[target].invoke()
        _pump(root)
        assert app.assembly_part_detail_frames[target].winfo_manager() == "pack"
        assert bool(visible.get()) is visible_before
        assert (formed.get(), blank.get(), corner.get()) == text_before

        # Visibility and details-open are independent presentation states.
        visible.set(False)
        app.assembly_part_detail_buttons[target].invoke()
        _pump(root)
        assert app.assembly_part_detail_frames[target].winfo_manager() == ""
        assert bool(visible.get()) is False
        assert (formed.get(), blank.get(), corner.get()) == text_before
    finally:
        root.destroy()


def test_collapsed_state_survives_topology_panel_rebuild_without_hiding_or_deleting_data():
    root, app = _open()
    try:
        target = "head" if "head" in app.assembly_part_visible_vars else next(iter(app.assembly_part_visible_vars))
        original_text = (
            app.assembly_part_formed_vars[target].get(),
            app.assembly_part_blank_vars[target].get(),
            app.assembly_part_corner_vars[target].get(),
        )
        app._phase6_assembly_panel_owner.set_part_details_open(target, False)
        _pump(root)
        assert app.assembly_part_detail_frames[target].winfo_manager() == ""

        bridge._phase6_refresh_assembly_parts_panel(app)
        _pump(root)

        assert target in app.assembly_part_visible_vars
        assert target in app.assembly_part_detail_frames
        assert app.assembly_part_detail_frames[target].winfo_manager() == ""
        assert str(app.assembly_part_detail_buttons[target].cget("text")) == "▸"
        assert (
            app.assembly_part_formed_vars[target].get(),
            app.assembly_part_blank_vars[target].get(),
            app.assembly_part_corner_vars[target].get(),
        ) == original_text
    finally:
        root.destroy()


def test_box_body_physical_piece_rows_are_also_collapsible_when_present():
    root, app = _open()
    try:
        app.do_update()
        _pump(root, 3)
        keys = tuple(app.assembly_box_body_piece_visible_vars)
        if not keys:
            pytest.skip("current family has no resolved BoxBody physical child rows")

        assert set(app.assembly_box_body_piece_detail_frames) == set(keys)
        assert set(app.assembly_box_body_piece_detail_buttons) == set(keys)

        key = keys[0]
        visible = app.assembly_box_body_piece_visible_vars[key]
        text_before = (
            app.assembly_box_body_piece_formed_vars[key].get(),
            app.assembly_box_body_piece_blank_vars[key].get(),
            app.assembly_box_body_piece_corner_vars[key].get(),
        )
        visible_before = bool(visible.get())

        assert app.assembly_box_body_piece_detail_frames[key].winfo_manager() == ""
        app.assembly_box_body_piece_detail_buttons[key].invoke()
        _pump(root)
        assert app.assembly_box_body_piece_detail_frames[key].winfo_manager() == "pack"
        assert bool(visible.get()) is visible_before
        assert (
            app.assembly_box_body_piece_formed_vars[key].get(),
            app.assembly_box_body_piece_blank_vars[key].get(),
            app.assembly_box_body_piece_corner_vars[key].get(),
        ) == text_before
    finally:
        root.destroy()
