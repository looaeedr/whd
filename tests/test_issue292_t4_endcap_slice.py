from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
ENDCAP = ROOT / "gui_modules" / "parts" / "panels" / "endcap.py"


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


def test_endcap_panel_owns_setup_and_root_is_thin_delegate():
    functions = _functions(ENDCAP)
    assert "setup_tab_endcap_ui" in functions, "endcap panel must own setup_tab_endcap_ui"

    root_method = _host_method("setup_tab_endcap_ui")
    assert root_method.end_lineno is not None
    span = root_method.end_lineno - root_method.lineno + 1
    assert span <= 4, f"gui.py setup_tab_endcap_ui must be a thin delegate, got {span} lines"


def test_endcap_panel_preserves_existing_fw_and_hole_routing_contract():
    text = ENDCAP.read_text(encoding="utf-8")
    required_tokens = {
        "fw_head_follow_var",
        "fw_tail_follow_var",
        "fw_head_var",
        "fw_tail_var",
        "_sync_endcap_fw_controls",
        "on_fw_selected",
        "canvas_head",
        "canvas_tail",
        "open_hole_editor",
        "draw_preview",
    }
    missing = sorted(token for token in required_tokens if token not in text)
    assert not missing, f"endcap presentation/routing parity tokens missing: {missing}"
