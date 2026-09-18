from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
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
    return {
        node.name: node
        for node in host.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def test_task6b_box_body_view_exports_piece_preview_presenter():
    assert BOX_VIEW.is_file(), "T6 TASK6B RED: box_body_view.py missing"
    source = BOX_VIEW.read_text(encoding="utf-8")
    assert "def draw_box_body_piece_preview(" in source, (
        "T6 TASK6B RED: piece preview presenter missing"
    )


def test_task6b_root_piece_preview_is_thin_delegate():
    methods = _host_methods()
    node = methods["_draw_box_body_piece_preview"]
    span = _span(node)
    assert span <= 4, (
        f"T6 TASK6B RED: _draw_box_body_piece_preview span={span} > 4"
    )


def test_task6b_piece_presenter_is_render_data_consumer_only():
    if not BOX_VIEW.is_file():
        return

    source = BOX_VIEW.read_text(encoding="utf-8")
    forbidden = (
        "manufacturing_api",
        "_authoritative_render_data",
        "_manufacturing_context",
        "_box_body_part_spec",
        "build_box_body",
        "resolve_surface_features",
    )
    hits = [token for token in forbidden if token in source]
    assert not hits, f"piece presenter stole geometry/manufacturing authority: {hits}"

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert _span(node) <= 150, (node.name, _span(node))
