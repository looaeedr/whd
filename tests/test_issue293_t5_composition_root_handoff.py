from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
COMPOSITION = ROOT / "gui_modules" / "editors" / "hole_editor_composition.py"


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def _unified_method() -> ast.FunctionDef:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost")
    return next(n for n in host.body if isinstance(n, ast.FunctionDef) and n.name == "_open_unified_hole_editor")


def test_composition_module_exists_without_gate_bypasses_or_reverse_gui_imports():
    assert COMPOSITION.is_file(), "T5 RED: hole_editor_composition.py is missing"
    source = COMPOSITION.read_text(encoding="utf-8")
    assert "from gui import" not in source
    assert "import gui" not in source
    assert "exec(" not in source
    assert "eval(" not in source


def test_composition_functions_stay_bounded():
    assert COMPOSITION.is_file(), "T5 RED: composition root is not extracted"
    tree = ast.parse(COMPOSITION.read_text(encoding="utf-8"))
    oversized = {
        node.name: _span(node)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _span(node) > 150
    }
    assert not oversized, f"T5 composition functions exceed 150 lines: {oversized}"


def test_gui_root_is_a_thin_composition_delegate_and_meets_loc_gate():
    gui = GUI.read_text(encoding="utf-8")
    method = _unified_method()
    segment = ast.get_source_segment(gui, method) or ""
    assert _span(method) <= 12, f"T5 RED: unified root remains {_span(method)} lines"
    assert "_open_unified_hole_editor_impl(" in segment
    assert "_HoleEditorCompositionDependencies.from_namespace(globals())" in segment
    assert len(gui.splitlines()) <= 5884, f"T5 RED: gui.py still {len(gui.splitlines())} LOC"
