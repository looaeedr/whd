# -*- coding: utf-8 -*-
"""#333 T0 — source-only characterization for the UI v3 branch cut.

T0 intentionally contains one RED describing the known layout gap.  The other
tests protect authority boundaries so later presentation work cannot use this
RED as permission to create new state or callback owners.
"""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "fold_designer_bridge.py"
THEME = ROOT / "whd_theme.py"


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_source(path: Path, name: str) -> str:
    source = _source(path)
    tree = ast.parse(source)
    node = next(
        item for item in tree.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name
    )
    return ast.get_source_segment(source, node) or ""


def test_authority_guard_part_selector_still_projects_designer_workspace():
    source = _source(BRIDGE)
    assert "self.designer_workspace.active_part" in source
    assert "_phase6_activate_operator_part" in source
    assert "part_choice_menu" in source
    assert "same authoritative part_var / workspace callbacks" in source


def test_authority_guard_output_reuses_existing_callbacks_and_setting_owner():
    export_source = _function_source(BRIDGE, "_phase6_export_selected_dxf_from_3d")
    stock_source = _function_source(BRIDGE, "_phase6_commit_output_draw_stock")
    assert "_phase6_export_selected_dxf_callback" in export_source
    assert "return callback()" in export_source
    assert '_phase6_stage_setting_update(self, "draw_stock", value)' in stock_source


def test_authority_guard_shared_theme_is_presentation_only():
    source = _source(THEME)
    assert "configure_tk_menu" in source
    assert "apply_ttk_dark_theme" in source
    assert "ae_engine" not in source
    assert "manufacturing" not in source.lower()


def test_authority_guard_renderer_remains_existing_canvas_sink():
    source = _source(BRIDGE)
    assert "self.renderer.canvas.get_tk_widget()" in source
    assert "_phase6_install_renderer_view(self)" in source


def test_v3_red_file_and_output_are_not_yet_one_top_row():
    persistent = _function_source(BRIDGE, "_phase6_build_persistent_top_area")
    output = _function_source(BRIDGE, "_phase6_build_output_controls")

    top_hosts_output = "_phase6_build_output_controls(self, self.top_command_row)" in persistent
    no_second_output_section = (
        "LabelFrame" not in output
        and 'text="輸出"' not in output
        and "text='輸出'" not in output
    )

    assert top_hosts_output and no_second_output_section, (
        "#333 EXPECTED RED: v3 requires File + Output in one top row and forbids "
        "a second right-side Output section; baseline still builds "
        "_phase6_build_output_controls(self) as a right-side LabelFrame."
    )
