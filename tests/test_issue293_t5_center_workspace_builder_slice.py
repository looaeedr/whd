from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
VIEW = ROOT / "gui_modules" / "editors" / "hole_editor_view.py"
COMPOSITION = ROOT / "gui_modules" / "editors" / "hole_editor_composition.py"


def _unified_method() -> ast.FunctionDef:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost")
    return next(n for n in host.body if isinstance(n, ast.FunctionDef) and n.name == "_open_unified_hole_editor")


def _builder_node() -> ast.ClassDef:
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorCenterWorkspaceBuilder"), None)
    assert node is not None, "T5 RED: HoleEditorCenterWorkspaceBuilder is missing"
    return node


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def test_center_workspace_builder_is_bounded_and_presentation_only():
    node = _builder_node()
    assert _span(node) <= 105, f"center workspace builder too large: {_span(node)}"
    source = ast.get_source_segment(VIEW.read_text(encoding="utf-8"), node) or ""
    assert "HoleEditorFullscreenActions" not in source
    assert "manufacturing_api" not in source
    assert "Phase6HoleEditorSession" not in source


def test_composition_root_delegates_widgets_but_keeps_fullscreen_controller_authority():
    gui = GUI.read_text(encoding="utf-8")
    method = _unified_method()
    root_segment = ast.get_source_segment(gui, method) or ""
    assert "HoleEditorCenterWorkspaceBuilder as _HoleEditorCenterWorkspaceBuilder" in gui
    assert COMPOSITION.is_file(), "T5 RED: center-workspace composition handoff is missing"
    composition = COMPOSITION.read_text(encoding="utf-8")
    assert "_HoleEditorCenterWorkspaceBuilder(host).build(" in composition
    assert "_HoleEditorFullscreenActions(" in composition
    assert 'text="旋轉"' not in root_segment
    assert 'text="確定全部"' not in root_segment
    assert 'text="取消全部"' not in root_segment


def test_center_workspace_slice_materially_reduces_root():
    method = _unified_method()
    assert _span(method) <= 600, f"T5 RED: center-workspace slice did not shrink root enough: {_span(method)}"
    gui_loc = len(GUI.read_text(encoding="utf-8").splitlines())
    assert gui_loc <= 6485, f"T5 RED: gui.py did not shed center workspace: {gui_loc}"
