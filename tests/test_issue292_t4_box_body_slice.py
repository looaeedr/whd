from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
BOX_BODY = ROOT / "gui_modules" / "parts" / "panels" / "box_body.py"


def _module_functions(path: Path) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def _host_method_span(name: str) -> int:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    method = next(
        node for node in host.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    return (method.end_lineno or method.lineno) - method.lineno + 1


def test_box_body_panel_owns_setup_tab_z_ui_and_root_is_thin_delegate():
    functions = _module_functions(BOX_BODY)
    assert "setup_tab_z_ui" in functions, "box_body panel must own setup_tab_z_ui"
    assert _host_method_span("setup_tab_z_ui") <= 4, (
        "gui.py still owns the box-body panel implementation instead of a thin delegate"
    )


def test_box_body_panel_keeps_t3_piece_identity_and_existing_routing_contract():
    text = BOX_BODY.read_text(encoding="utf-8")
    required_tokens = {
        "build_box_body_piece_selector",
        "fw_z_var",
        "box_assembly_type_var",
        "on_box_assembly_changed",
        "on_box_body_canvas_press",
        "on_box_body_piece_double_click",
        "canvas_z",
    }
    missing = sorted(token for token in required_tokens if token not in text)
    assert not missing, f"box-body presentation/routing parity tokens missing: {missing}"
