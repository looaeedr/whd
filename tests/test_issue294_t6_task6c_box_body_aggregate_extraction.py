from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
APP = ROOT / "gui_modules" / "application" / "render_snapshots.py"
BOX_VIEW = ROOT / "gui_modules" / "rendering" / "box_body_view.py"


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


def test_task6c_box_body_view_exports_aggregate_presenter():
    source = BOX_VIEW.read_text(encoding="utf-8")
    assert "def draw_box_body_aggregate_preview(" in source, (
        "T6 TASK6C RED: aggregate box-body presenter missing"
    )


def test_task6c_root_draw_box_body_is_thin_delegate():
    _source, methods = _host_methods()
    node = methods["draw_box_body"]
    span = _span(node)
    assert span <= 8, f"T6 TASK6C RED: draw_box_body span={span} > 8"


def test_task6c_application_keeps_box_body_snapshot_orchestration():
    source = APP.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    body = ast.get_source_segment(
        source, functions["box_body_render_snapshot"]
    ) or ""
    for token in (
        "_box_body_part_spec",
        "_authoritative_render_data",
        "_manufacturing_context",
        "_refresh_box_body_piece_tabs_2d",
        "_baseline_source_model",
        "face_dimensions_fn",
    ):
        assert token in body, f"snapshot builder missing authority token: {token}"
def test_task6c_box_body_presenter_consumes_render_data_only():
    source = BOX_VIEW.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    presenter = ast.get_source_segment(
        source, functions["draw_box_body_aggregate_preview"]
    ) or ""
    forbidden = (
        "manufacturing_api",
        "_authoritative_render_data",
        "_manufacturing_context",
        "_box_body_part_spec",
        "box_body_face_dimensions",
        "_baseline_source_model",
        "_refresh_box_body_piece_tabs_2d",
        "build_box_body",
        "resolve_surface_features",
    )
    hits = [token for token in forbidden if token in presenter]
    assert not hits, f"box-body presenter stole acquisition/geometry authority: {hits}"

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert _span(node) <= 150, (node.name, _span(node))
        if isinstance(node, ast.ClassDef):
            assert _span(node) <= 800, (node.name, _span(node))
