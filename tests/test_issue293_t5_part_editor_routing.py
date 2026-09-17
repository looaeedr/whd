from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
EDITOR = ROOT / "gui_modules" / "editors" / "hole_editor.py"
MAX_ROOT_DELEGATE_LINES = 12
MAX_EDITOR_METHOD_LINES = 150


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def _root_method(name: str) -> ast.FunctionDef:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    return next(
        node for node in host.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def test_issue293_open_part_hole_editor_is_thin_root_delegate():
    method = _root_method("open_part_hole_editor")
    assert _span(method) <= MAX_ROOT_DELEGATE_LINES, (
        f"T5 RED: open_part_hole_editor remains rooted ({_span(method)} LOC)"
    )
    assert "_open_part_hole_editor_impl" in GUI.read_text(encoding="utf-8")


def test_issue293_part_editor_module_has_decomposed_entrypoint_without_giant_function():
    source = EDITOR.read_text(encoding="utf-8")
    tree = ast.parse(source)
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    assert "open_part_hole_editor" in functions, (
        "T5 RED: part editor routing has not moved into hole_editor.py"
    )
    oversized = {
        name: _span(node)
        for name, node in functions.items()
        if _span(node) > MAX_EDITOR_METHOD_LINES
    }
    assert not oversized, f"T5 RED: hole_editor.py has giant functions: {oversized}"


def test_issue293_part_editor_preserves_multi_door_short_circuit():
    from gui_modules.editors.hole_editor import open_part_hole_editor

    events = []

    class Workspace:
        def set_active_part(self, part_key):
            events.append(("active", part_key))

    class Flag:
        def get(self):
            return True

    class Host:
        workspace_controller = Workspace()
        multi_door_enabled_var = Flag()

        def get_selected_door_layout_cell(self):
            return type("Cell", (), {"column_index": 2, "row_index": 3})()

        def open_door_layout_cell_editor(self, column, row):
            events.append(("door_cell", column, row))

        def get_float_values(self):
            raise AssertionError("multi-door route must short-circuit before scalar parsing")

    result = open_part_hole_editor(Host(), "door")
    assert result is None
    assert events == [("active", "door"), ("door_cell", 2, 3)]


def test_issue293_part_editor_preserves_box_body_face_short_circuit():
    from gui_modules.editors.hole_editor import open_part_hole_editor

    events = []

    class Workspace:
        def set_active_part(self, part_key):
            events.append(("active", part_key))

    class Flag:
        def get(self):
            return False

    class Face:
        def get(self):
            return "left"

    class Host:
        workspace_controller = Workspace()
        multi_door_enabled_var = Flag()
        box_body_face_selected_var = Face()

        def open_box_body_face_editor(self, face):
            events.append(("box_face", face))

        def get_float_values(self):
            raise AssertionError("box-body route must short-circuit before scalar parsing")

    result = open_part_hole_editor(Host(), "box_body")
    assert result is None
    assert events == [("active", "box_body"), ("box_face", "left")]
