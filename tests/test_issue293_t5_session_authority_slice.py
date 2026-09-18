from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
EDITOR = ROOT / "gui_modules" / "editors" / "hole_editor.py"
COMPOSITION = ROOT / "gui_modules" / "editors" / "hole_editor_composition.py"


def _unified_method() -> ast.FunctionDef:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost")
    return next(n for n in host.body if isinstance(n, ast.FunctionDef) and n.name == "_open_unified_hole_editor")


def _factory_class():
    tree = ast.parse(EDITOR.read_text(encoding="utf-8"))
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorSessionFactory"), None)
    assert node is not None, "T5 RED: HoleEditorSessionFactory is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {"Phase6HoleEditorSession": _FakeSession}
    exec(compile(module, str(EDITOR), "exec"), ns)
    return ns["HoleEditorSessionFactory"], node


class _FakeSession:
    def __init__(self, key, features, max_undo_steps=50):
        self.args = (key, features, max_undo_steps)


def test_editor_package_imports_existing_session_authority_without_redefining_it():
    source = EDITOR.read_text(encoding="utf-8")
    assert "from phase6_hole_editor_session import Phase6HoleEditorSession" in source
    assert "class Phase6HoleEditorSession" not in source


def test_session_factory_is_tiny_and_delegates_to_existing_authority():
    factory, node = _factory_class()
    assert node.end_lineno - node.lineno + 1 <= 12
    features = ["F1"]
    session = factory.create("door", features, max_undo_steps=37)
    assert session.args == ("door", features, 37)


def test_unified_composition_uses_editor_session_factory_not_direct_constructor():
    gui = GUI.read_text(encoding="utf-8")
    assert "HoleEditorSessionFactory as _HoleEditorSessionFactory" in gui
    method = _unified_method()
    root_segment = ast.get_source_segment(gui, method) or ""
    assert "Phase6HoleEditorSession(" not in root_segment
    assert COMPOSITION.is_file(), "T5 RED: session authority handoff composition is missing"
    composition = COMPOSITION.read_text(encoding="utf-8")
    assert "_HoleEditorSessionFactory.create(" in composition
    assert "Phase6HoleEditorSession(" not in composition
