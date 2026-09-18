from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
APP = ROOT / "gui_modules" / "application" / "render_snapshots.py"
DOOR_VIEW = ROOT / "gui_modules" / "rendering" / "door_view.py"


def _span(node: ast.AST) -> int:
    return int(getattr(node, "end_lineno")) - int(getattr(node, "lineno")) + 1


def _host_methods():
    source = GUI.read_text(encoding="utf-8")
    tree = ast.parse(source)
    host = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    return source, {
        node.name: node
        for node in host.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_task4c1_door_view_exports_multidoor_overview_presenter():
    source = DOOR_VIEW.read_text(encoding="utf-8")
    assert "def draw_door_layout_overview_preview(" in source, (
        "T6 TASK4C1 RED: multi-door overview presenter missing"
    )


def test_task4c1_root_overview_entrypoint_is_thin():
    _source, methods = _host_methods()
    node = methods["draw_door_layout_overview"]
    span = _span(node)
    assert span <= 8, f"T6 TASK4C1 RED: draw_door_layout_overview span={span} > 8"


def test_task4c1_application_keeps_overview_snapshot_acquisition():
    source = APP.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    body = ast.get_source_segment(
        source, functions["door_layout_overview_snapshot"]
    ) or ""
    for token in (
        "get_door_layout_columns",
        "get_door_layout_cells",
        "get_float_values",
        "_door_layout_cell_result",
        "_door_layout_baseline_scene",
        "_door_layout_cell_resolved_features",
        "_baseline_source_model",
    ):
        assert token in body, f"snapshot builder missing authority/data token: {token}"
def test_task4c1_presenter_does_not_acquire_geometry_or_manufacturing_state():
    source = DOOR_VIEW.read_text(encoding="utf-8")
    forbidden = (
        "_door_layout_cell_result",
        "_door_layout_baseline_scene",
        "_door_layout_cell_resolved_features",
        "_authoritative_render_data",
        "_manufacturing_context",
        "manufacturing_api",
        "derive_box_body_dividers",
        "resolve_assembly_placement",
        "inner_door_frame",
    )
    hits = [token for token in forbidden if token in source]
    assert not hits, f"presenter stole authority/acquisition: {hits}"
