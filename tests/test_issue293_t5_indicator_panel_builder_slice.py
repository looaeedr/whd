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
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorIndicatorPanelBuilder"), None)
    assert node is not None, "T5 RED: HoleEditorIndicatorPanelBuilder is missing"
    return node


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def test_indicator_panel_builder_is_bounded_presentation_only():
    node = _builder_node()
    assert _span(node) <= 125
    for method in (n for n in node.body if isinstance(n, ast.FunctionDef)):
        assert _span(method) <= 100, f"{method.name} is too large: {_span(method)}"
    source = ast.get_source_segment(VIEW.read_text(encoding="utf-8"), node) or ""
    assert "manufacturing_api" not in source
    assert "Phase6HoleEditorSession" not in source


def test_composition_root_delegates_indicator_panel_construction():
    gui = GUI.read_text(encoding="utf-8")
    method = _unified_method()
    root_segment = ast.get_source_segment(gui, method) or ""
    assert "HoleEditorIndicatorPanelBuilder as _HoleEditorIndicatorPanelBuilder" in gui
    assert COMPOSITION.is_file(), "T5 RED: indicator-panel composition handoff is missing"
    composition = COMPOSITION.read_text(encoding="utf-8")
    assert "_HoleEditorIndicatorPanelBuilder(host).build(" in composition
    assert 'text=" 門指示燈 / 指示燈盒子 "' not in root_segment
    assert "tk.Radiobutton(" not in root_segment
    assert "rebuild_indicator_group_controls =" not in root_segment


def test_indicator_panel_slice_materially_reduces_root():
    method = _unified_method()
    assert _span(method) <= 685, f"T5 RED: indicator-panel slice did not shrink root enough: {_span(method)}"
    gui_loc = len(GUI.read_text(encoding="utf-8").splitlines())
    assert gui_loc <= 6560, f"T5 RED: gui.py did not shed indicator panel: {gui_loc}"
