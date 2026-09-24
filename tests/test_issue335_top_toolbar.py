# -*- coding: utf-8 -*-
"""#335 T2 — compact one-row top toolbar and right-workspace relief."""
from __future__ import annotations

import ast
import os
from pathlib import Path
import tkinter as tk

import pytest


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"
SHELL = ROOT / "phase6_workspace_shell.py"


def _source() -> str:
    return BRIDGE.read_text(encoding="utf-8")


def _function_source(name: str) -> str:
    source = _source()
    tree = ast.parse(source)
    node = next(
        item for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    )
    return ast.get_source_segment(source, node) or ""

def _owner_method_source(name: str) -> str:
    source = SHELL.read_text(encoding="utf-8")
    tree = ast.parse(source)
    owner = next(
        item for item in tree.body
        if isinstance(item, ast.ClassDef) and item.name == "WorkspaceShellOwner"
    )
    node = next(
        item for item in owner.body
        if isinstance(item, ast.FunctionDef) and item.name == name
    )
    return ast.get_source_segment(source, node) or ""


def test_v3_top_toolbar_source_contract():
    persistent = _owner_method_source("build_persistent_top_area")
    output = _owner_method_source("build_output_controls")
    visual = _owner_method_source("build_visual_controls")

    assert "self.build_output_controls(self.top_command_row)" in persistent, (
        "#335 EXPECTED RED: DXF/STOCK output controls must share top_command_row "
        "with File/Corner Data instead of consuming the right workspace."
    )
    assert "LabelFrame" not in output
    assert 'text="輸出"' not in output
    assert "LabelFrame" not in visual
    assert 'text="3D 顯示"' not in visual

    visual_pack = persistent.index("self.right_controls_primary.pack")
    global_pack = persistent.index("self.right_global_host.pack")
    assert visual_pack < global_pack, (
        "3D display controls must be packed above global settings."
    )


def test_output_authority_routes_are_unchanged():
    export_source = _function_source("_phase6_export_selected_dxf_from_3d")
    stock_source = _function_source("_phase6_commit_output_draw_stock")
    assert "_phase6_export_selected_dxf_callback" in export_source
    assert "Phase6ProjectController.route_selected_dxf_export" in export_source
    assert "Phase6ProjectController.commit_output_stock" in stock_source
    assert "_phase6_stage_setting_update" in stock_source


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires real Tk/Xvfb")
@pytest.mark.parametrize("ui_text_size", ("small", "medium", "large"))
def test_runtime_top_toolbar_and_right_workspace_geometry(ui_text_size):
    import gui

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    try:
        designer.apply_external_settings({"ui_text_size": ui_text_size})
        for _ in range(5):
            root.update_idletasks()
            root.update()

        assert designer.project_toolbar.master is designer.top_command_row
        assert designer.output_controls_frame.master is designer.top_command_row
        assert designer.output_controls_frame.winfo_ismapped()
        assert designer.output_export_button.winfo_ismapped()
        assert designer.output_draw_stock_check.winfo_ismapped()

        # One toolbar row: both groups share the same vertical band rather than
        # creating a second stacked output section.
        project_y = designer.project_toolbar.winfo_rooty()
        output_y = designer.output_controls_frame.winfo_rooty()
        assert abs(project_y - output_y) <= max(
            designer.project_toolbar.winfo_height(),
            designer.output_controls_frame.winfo_height(),
        )

        assert designer.visual_controls.master is designer.right_controls_primary
        assert designer.right_global_host.winfo_rooty() >= (
            designer.right_controls_primary.winfo_rooty()
            + designer.right_controls_primary.winfo_height()
        )

        canvas = designer.renderer.canvas.get_tk_widget()
        right = designer.right
        canvas_h = canvas.winfo_height()
        right_h = right.winfo_height()
        assert canvas.winfo_viewable() == 1
        assert canvas_h >= 220
        assert canvas_h / max(1, right_h) >= 0.35, (
            f"renderer lost too much usable height at {ui_text_size}: "
            f"canvas={canvas_h}, right={right_h}"
        )
    finally:
        root.destroy()


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires real Tk/Xvfb")
def test_output_selection_remains_independent_of_presence_and_visibility():
    import gui

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    try:
        for _ in range(3):
            root.update_idletasks()
            root.update()
        export_var = designer.output_export_vars["head"]
        visibility_var = designer.assembly_part_visible_vars["head"]
        visible_before = bool(visibility_var.get())
        parts_before = tuple(designer.designer_workspace.available_parts)

        export_var.set(not bool(export_var.get()))
        root.update_idletasks()
        root.update()

        assert bool(visibility_var.get()) is visible_before
        assert tuple(designer.designer_workspace.available_parts) == parts_before
    finally:
        root.destroy()
