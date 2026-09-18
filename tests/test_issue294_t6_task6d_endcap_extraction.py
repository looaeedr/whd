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


def test_task6d_box_body_view_exports_endcap_presenters():
    source = BOX_VIEW.read_text(encoding="utf-8")
    missing = [
        name for name in ("draw_end_cap_preview", "draw_end_cap_error")
        if f"def {name}(" not in source
    ]
    assert not missing, f"T6 TASK6D RED: Endcap presenters missing: {missing}"


def test_task6d_root_draw_end_cap_is_thin_delegate():
    _source, methods = _host_methods()
    node = methods["draw_end_cap"]
    span = _span(node)
    assert span <= 8, f"T6 TASK6D RED: draw_end_cap span={span} > 8"


def test_task6d_application_keeps_endcap_snapshot_orchestration():
    source = APP.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    body = ast.get_source_segment(
        source, functions["end_cap_render_snapshot"]
    ) or ""
    for token in (
        "_end_cap_part_spec",
        "_authoritative_render_data",
        "_manufacturing_context",
        "_baseline_source_model",
        "is_unknown_model",
    ):
        assert token in body, f"Endcap snapshot missing authority token: {token}"
def test_task6d_endcap_presenter_is_render_data_consumer_only():
    source = BOX_VIEW.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    presenter = "\n".join(
        ast.get_source_segment(source, functions[name]) or ""
        for name in ("draw_end_cap_preview", "draw_end_cap_error")
    )
    forbidden = (
        "manufacturing_api",
        "_authoritative_render_data",
        "_manufacturing_context",
        "_end_cap_part_spec",
        "_baseline_source_model",
        "is_unknown_model",
        "build_end_cap",
        "resolve_surface_features",
    )
    hits = [token for token in forbidden if token in presenter]
    assert not hits, f"Endcap presenter stole acquisition/geometry authority: {hits}"

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert _span(node) <= 150, (node.name, _span(node))
        if isinstance(node, ast.ClassDef):
            assert _span(node) <= 800, (node.name, _span(node))
