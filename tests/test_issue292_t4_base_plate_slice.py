from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
BASE_PLATE = ROOT / "gui_modules" / "parts" / "panels" / "base_plate.py"


def _functions(path: Path) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def _host_method(name: str) -> ast.FunctionDef:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    return next(
        node
        for node in host.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def test_base_plate_panel_owns_setup_and_root_is_thin_delegate():
    functions = _functions(BASE_PLATE)
    assert "setup_tab_base_plate_ui" in functions, "base_plate panel must own setup_tab_base_plate_ui"

    root_method = _host_method("setup_tab_base_plate_ui")
    assert root_method.end_lineno is not None
    span = root_method.end_lineno - root_method.lineno + 1
    assert span <= 4, f"gui.py setup_tab_base_plate_ui must be a thin delegate, got {span} lines"


def test_base_plate_panel_preserves_preview_hole_and_legacy_container_contract():
    text = BASE_PLATE.read_text(encoding="utf-8")
    required_tokens = {
        "tab_base_plate",
        "canvas_base_plate",
        "draw_preview",
        "_attach_part_hole_entrypoint",
        "canvas_frames",
        "canvas_window_ids",
        '"base_plate"',
    }
    missing = sorted(token for token in required_tokens if token not in text)
    assert not missing, f"base-plate presentation/routing parity tokens missing: {missing}"
