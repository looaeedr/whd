from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
INTERACTION = ROOT / "gui_modules" / "rendering" / "interaction.py"

ROOT_METHODS = {
    "_box_body_face_at_canvas_point",
    "select_box_body_face",
    "on_box_body_canvas_press",
}

EXPECTED_FUNCTIONS = {
    "box_body_face_at_canvas_point",
    "select_box_body_face",
    "on_box_body_canvas_press",
}


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


def test_task6a_interaction_module_exports_box_body_face_routing():
    assert INTERACTION.is_file()
    source = INTERACTION.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = sorted(EXPECTED_FUNCTIONS - functions)
    assert not missing, f"T6 TASK6A RED: box-body interaction functions missing: {missing}"


def test_task6a_root_box_body_interaction_methods_are_thin():
    methods = _host_methods()
    oversized = []
    for name in sorted(ROOT_METHODS):
        node = methods[name]
        if _span(node) > 4:
            oversized.append((name, _span(node)))
    assert not oversized, (
        "T6 TASK6A RED: root box-body interaction methods are not thin: "
        + ", ".join(f"{name}={span}" for name, span in oversized)
    )


def test_task6a_interaction_module_stays_presentation_only():
    source = INTERACTION.read_text(encoding="utf-8")
    forbidden_tokens = (
        "manufacturing_api",
        "_authoritative_render_data",
        "_manufacturing_context",
        "_box_body_part_spec",
        "host.surface_features =",
        "host.project_controller =",
        "host.workspace_controller =",
    )
    hits = [token for token in forbidden_tokens if token in source]
    assert not hits, f"interaction stole box-body/manufacturing authority: {hits}"

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            assert _span(node) <= 150, (node.name, _span(node))
