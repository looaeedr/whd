# -*- coding: utf-8 -*-
"""#336 T3 — sheet-metal selector and three-way content switch."""
from __future__ import annotations

import ast
import os
from pathlib import Path
import tkinter as tk

import pytest


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"


def _source() -> str:
    return BRIDGE.read_text(encoding="utf-8")


def _func(name: str) -> str:
    source = _source()
    tree = ast.parse(source)
    node = next(
        (
            n for n in tree.body
            if isinstance(n, ast.FunctionDef) and n.name == name
        ),
        None,
    )
    return (ast.get_source_segment(source, node) or "") if node is not None else ""


def test_t3_source_contract_uses_one_main_selector_without_duplicate_content_strip():
    refresh = _func("_fix11_refresh_part_buttons")
    builder = _func("_phase6_build_content_switch")
    input_switch = _func("_phase6_show_input_content")

    # Accepted operator layout: one main selector owns 組合體 / 鈑件 / 截角資料.
    # The old three-button content switch survives only as hidden compatibility
    # handles so there is no second navigation strip or second mode state.
    assert 'label="組合體"' in refresh
    assert 'label="截角資料"' in refresh
    assert "_phase6_show_assembly" in refresh
    assert "_phase6_show_corner_data" in refresh

    assert builder
    assert "input_content_button = None" in builder
    assert "assembly_content_button = None" in builder
    assert "corner_data_content_button = None" in builder
    assert 'text="輸入區"' not in builder
    assert 'text="組合體"' not in builder
    assert 'text="截角資料"' not in builder
    assert "StringVar" not in builder and "IntVar" not in builder, (
        "compatibility content-switch shell must not own a second navigation state"
    )
    assert "designer_workspace" in input_switch or "_designer_workspace" in input_switch


def test_t3_authority_guard_keeps_existing_workspace_navigation():
    source = _source()
    assert "_phase6_activate_operator_part" in source
    assert "_dm7_resolve_navigation" in source
    assert "designer_workspace.active_part" in source
    assert "_phase6_3d_display_mode" in source
    assert "content_mode_var" not in source


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires real Tk/Xvfb")
@pytest.mark.parametrize("ui_text_size", ("small", "medium", "large"))
def test_t3_controls_are_reachable_and_modes_are_exclusive(ui_text_size):
    import gui

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    try:
        designer.apply_external_settings({"ui_text_size": ui_text_size})
        for _ in range(4):
            root.update_idletasks(); root.update()

        for widget in (
            designer.part_choice_button,
            designer.add_part_button,
            designer.remove_part_button,
        ):
            assert widget.winfo_ismapped()
            assert widget.winfo_width() > 1 and widget.winfo_height() > 1
        assert designer.input_content_button is None
        assert designer.assembly_content_button is None
        assert designer.corner_data_content_button is None

        labels = []
        label_to_index = {}
        end = designer.part_choice_menu.index("end")
        if end is not None:
            for index in range(end + 1):
                try:
                    label = str(designer.part_choice_menu.entrycget(index, "label"))
                except tk.TclError:
                    continue
                labels.append(label)
                label_to_index[label] = index
        assert "組合體" in labels
        assert "截角資料" in labels
        real_labels = [label for label in labels if label not in {"組合體", "截角資料"}]
        assert real_labels, "main selector must still contain real sheet-metal choices"

        active_before = designer.designer_workspace.active_part

        designer.part_choice_menu.invoke(label_to_index["組合體"])
        root.update_idletasks(); root.update()
        assert designer._phase6_3d_display_mode == "assembly"
        assert designer.part_var.get() == "組合體"
        assert designer.assembly_parts_panel.winfo_manager() == "pack"
        assert designer.fold_editor_host.winfo_manager() == ""
        assert designer.designer_workspace.active_part == active_before

        designer.part_choice_menu.invoke(label_to_index["截角資料"])
        root.update_idletasks(); root.update()
        assert designer._phase6_3d_display_mode == "corner_data"
        assert designer.part_var.get() == "截角資料"
        assert designer.corner_data_panel.winfo_manager() == "pack"
        assert designer.assembly_parts_panel.winfo_manager() == ""
        assert designer.fold_editor_host.winfo_manager() == ""
        assert designer.designer_workspace.active_part == active_before

        designer.part_choice_menu.invoke(label_to_index[real_labels[0]])
        root.update_idletasks(); root.update()
        assert designer._phase6_3d_display_mode == "single"
        assert designer.fold_editor_host.winfo_manager() == "pack"
        assert designer.assembly_parts_panel.winfo_manager() == ""
        assert designer.corner_data_panel.winfo_manager() == ""
        assert designer.designer_workspace.active_part == active_before
    finally:
        root.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires real Tk/Xvfb")
def test_t3_switch_clears_posted_navigation_menu_residue():
    import gui

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    try:
        for _ in range(3):
            root.update_idletasks(); root.update()
        button = designer.part_choice_button
        designer.part_choice_menu.post(
            button.winfo_rootx(), button.winfo_rooty() + button.winfo_height()
        )
        root.update_idletasks(); root.update()
        assert designer.part_choice_menu.winfo_ismapped() == 1

        end = designer.part_choice_menu.index("end")
        assembly_index = next(
            i for i in range(end + 1)
            if str(designer.part_choice_menu.entrycget(i, "label")) == "組合體"
        )
        designer.part_choice_menu.invoke(assembly_index)
        root.update_idletasks(); root.update()
        assert designer.part_choice_menu.winfo_ismapped() == 0
        assert designer._phase6_3d_display_mode == "assembly"
    finally:
        root.destroy()
