# -*- coding: utf-8 -*-
"""#335 T2 — UI v3 top-row and right-control compact layout contract.

The test guards presentation only. Existing output variables/callbacks, settings
state, renderer, workspace and manufacturing authority remain untouched.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
import tkinter as tk

import pytest

import fold_designer_bridge as bridge


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"
SETTINGS = ROOT / "phase6_settings_panel.py"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _func(path: Path, name: str) -> str:
    source = _text(path)
    tree = ast.parse(source)
    node = next(
        n for n in tree.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name
    )
    return ast.get_source_segment(source, node) or ""


def test_v3_red_top_file_output_one_row_and_right_titles_removed():
    persistent = _func(BRIDGE, "_phase6_build_persistent_top_area")
    output = _func(BRIDGE, "_phase6_build_output_controls")
    visual = _func(BRIDGE, "_phase6_build_visual_controls")
    settings = _func(SETTINGS, "build_left_global_controls")

    failures = []
    if "_phase6_build_output_controls(self, self.top_command_row)" not in persistent:
        failures.append("output-not-hosted-by-top-command-row")
    if "_phase6_build_output_controls(self)" in persistent:
        failures.append("right-side-output-builder-call-remains")
    if "LabelFrame" in output or 'text="輸出"' in output or "text='輸出'" in output:
        failures.append("output-still-has-section-frame-title")
    if "LabelFrame" in visual or 'text="3D 顯示"' in visual or "text='3D 顯示'" in visual:
        failures.append("3d-display-still-has-section-title")
    if "LabelFrame" in settings or 'text="全域設定"' in settings or "text='全域設定'" in settings:
        failures.append("global-settings-still-has-section-title")

    assert not failures, f"#335 EXPECTED RED: UI v3 compact layout gaps={failures!r}"


def test_output_authority_routes_are_unchanged():
    source = _text(BRIDGE)
    assert '_phase6_stage_setting_update(self, "draw_stock", value)' in source
    assert "_phase6_export_selected_dxf_callback" in source
    assert "return callback()" in source


def test_settings_and_renderer_authority_routes_are_unchanged():
    source = _text(BRIDGE)
    assert "_phase6_ensure_settings_panel(self)" in source
    assert "_phase6_install_renderer_view(self)" in source
    assert "self.renderer.canvas.get_tk_widget()" in source


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="#335 requires real Tk/Xvfb")
def test_v3_real_tk_top_row_and_right_stack():
    import gui

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    try:
        for _ in range(4):
            root.update_idletasks()
            root.update()

        assert designer.project_toolbar.master is designer.top_command_row
        assert designer.output_controls_frame.master is designer.top_command_row
        assert designer.project_toolbar.winfo_ismapped()
        assert designer.output_controls_frame.winfo_ismapped()

        # Same toolbar band: their vertical ranges must overlap.
        p0 = designer.project_toolbar.winfo_rooty()
        p1 = p0 + designer.project_toolbar.winfo_height()
        o0 = designer.output_controls_frame.winfo_rooty()
        o1 = o0 + designer.output_controls_frame.winfo_height()
        assert min(p1, o1) - max(p0, o0) > 0

        # Right side order is display controls, then global settings, then renderer.
        visual = designer.visual_controls
        global_controls = designer.left_global_controls
        canvas = designer.renderer.canvas.get_tk_widget()
        for widget in (visual, global_controls, canvas):
            assert widget.winfo_ismapped()
            assert widget.winfo_width() > 1 and widget.winfo_height() > 1
        assert visual.winfo_rooty() <= global_controls.winfo_rooty()
        assert global_controls.winfo_rooty() < canvas.winfo_rooty()
        assert canvas.winfo_height() >= 250
    finally:
        root.destroy()


@pytest.mark.parametrize("scale", ("small", "medium", "large"))
@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="#335 requires real Tk/Xvfb")
def test_v3_top_output_actions_remain_reachable_at_all_text_scales(scale):
    import gui

    root = tk.Tk()
    root.geometry("1400x900+0+0")
    root.update_idletasks()
    app = gui.Phase6PrimaryApplication(root)
    designer = app.fold_designer_app
    try:
        designer.apply_external_settings({"ui_text_size": scale})
        for _ in range(4):
            root.update_idletasks()
            root.update()
        frame = designer.output_controls_frame
        button = designer.output_export_button
        assert frame.winfo_ismapped() and button.winfo_ismapped()
        assert frame.winfo_width() > 1 and frame.winfo_height() > 1
        assert button.winfo_width() > 1 and button.winfo_height() > 1
        assert frame.master is designer.top_command_row
    finally:
        root.destroy()
