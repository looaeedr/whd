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


def test_t3_source_contract_separates_part_selector_from_content_modes():
    refresh = _func("_fix11_refresh_part_buttons")
    builder = _func("_phase6_build_content_switch")
    assert 'label="組合體"' in refresh
    assert 'label="截角資料"' in refresh
    assert "command=lambda: _phase6_show_assembly(self)" in refresh
    assert "command=lambda: _phase6_show_corner_data(self)" in refresh
    assert "self.input_content_button = None" in builder
    assert "self.assembly_content_button = None" in builder
    assert "self.corner_data_content_button = None" in builder
    assert 'text="輸入區"' not in builder
    assert 'text="顯示區"' not in builder
    assert "_phase6_show_input_content" not in _source()


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
    import fold_designer_bridge as bridge

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
        end = designer.part_choice_menu.index("end")
        if end is not None:
            for index in range(end + 1):
                labels.append(str(designer.part_choice_menu.entrycget(index, "label")))
        assert labels[0] == "組合體"
        assert labels[-1] == "截角資料"
        assert "箱身" in labels

        active_before = designer.designer_workspace.active_part

        bridge._phase6_show_assembly(designer)
        root.update_idletasks(); root.update()
        assert designer._phase6_3d_display_mode == "assembly"
        assert designer.part_var.get() == "組合體"
        assert designer.assembly_parts_panel.winfo_manager() == "pack"
        assert designer.fold_editor_host.winfo_manager() == ""
        assert designer.designer_workspace.active_part == active_before

        bridge._phase6_show_corner_data(designer)
        root.update_idletasks(); root.update()
        assert designer._phase6_3d_display_mode == "corner_data"
        assert designer.part_var.get() == "截角資料"
        assert designer.corner_data_panel.winfo_manager() == "pack"
        assert designer.assembly_parts_panel.winfo_manager() == ""
        assert designer.fold_editor_host.winfo_manager() == ""
        assert designer.designer_workspace.active_part == active_before

        designer.activate_part(active_before)
        root.update_idletasks(); root.update()
        assert designer._phase6_3d_display_mode == "single"
        assert designer.fold_editor_host.winfo_manager() == "pack"
        assert designer.assembly_parts_panel.winfo_manager() == ""
        assert designer.corner_data_panel.winfo_manager() == ""
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

        import fold_designer_bridge as bridge
        bridge._phase6_show_assembly(designer)
        root.update_idletasks(); root.update()
        assert designer.part_choice_menu.winfo_ismapped() == 0
    finally:
        root.destroy()
