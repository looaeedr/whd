from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
EDITORS = ROOT / "gui_modules" / "editors"
REQUIRED_EDITOR_FILES = {
    "__init__.py",
    "dialogs.py",
    "hole_editor.py",
    "hole_editor_view.py",
}
ROOT_EDITOR_ENTRYPOINTS = {
    "ask_xy_dialog",
    "open_part_hole_editor",
    "_open_unified_hole_editor",
    "open_hole_editor",
}
MAX_ROOT_DELEGATE_LINES = 12
MAX_EDITOR_CLASS_LINES = 800
MAX_EDITOR_METHOD_LINES = 150
MAX_GUI_LINES = 5_884


def _host_methods() -> dict[str, ast.FunctionDef]:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    return {
        node.name: node
        for node in host.body
        if isinstance(node, ast.FunctionDef)
    }


def _span(node: ast.AST) -> int:
    assert hasattr(node, "lineno") and getattr(node, "end_lineno", None) is not None
    return int(node.end_lineno) - int(node.lineno) + 1


def _editor_sources() -> dict[str, str]:
    assert EDITORS.is_dir(), "T5 RED: gui_modules/editors/ package is not extracted yet"
    missing = sorted(REQUIRED_EDITOR_FILES - {path.name for path in EDITORS.iterdir() if path.is_file()})
    assert not missing, f"T5 RED: missing editor modules: {missing}"
    return {
        name: (EDITORS / name).read_text(encoding="utf-8")
        for name in REQUIRED_EDITOR_FILES
    }


def test_issue293_editor_package_and_explicit_import_direction_exist():
    sources = _editor_sources()
    joined = "\n".join(sources.values())
    assert "from gui import" not in joined
    assert "import gui" not in joined
    assert "compatibility.legacy_exports" not in joined


def test_issue293_root_editor_entrypoints_are_thin_delegates():
    methods = _host_methods()
    missing = sorted(ROOT_EDITOR_ENTRYPOINTS - methods.keys())
    assert not missing, f"T5 root entrypoint inventory drifted: {missing}"
    oversized = {
        name: _span(methods[name])
        for name in sorted(ROOT_EDITOR_ENTRYPOINTS)
        if _span(methods[name]) > MAX_ROOT_DELEGATE_LINES
    }
    assert not oversized, f"T5 RED: editor implementation is still rooted in gui.py: {oversized}"


def test_issue293_editor_package_reuses_existing_session_and_canvas_authorities():
    sources = _editor_sources()
    joined = "\n".join(sources.values())
    assert "Phase6HoleEditorSession" in joined
    assert "Phase6HoleEditorCanvasView" in joined
    assert "class Phase6HoleEditorSession" not in joined
    assert "class Phase6HoleEditorCanvasView" not in joined


def test_issue293_editor_structure_has_no_new_monolith():
    sources = _editor_sources()
    violations: list[str] = []
    for filename, source in sources.items():
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and _span(node) > MAX_EDITOR_CLASS_LINES:
                violations.append(f"{filename}:class {node.name}={_span(node)}")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _span(node) > MAX_EDITOR_METHOD_LINES:
                violations.append(f"{filename}:method {node.name}={_span(node)}")
    assert not violations, f"T5 editor structural limits exceeded: {violations}"


def test_issue293_t5_root_loc_gate_is_reconciled_without_stealing_later_scope():
    gui_loc = len(GUI.read_text(encoding="utf-8").splitlines())
    assert gui_loc <= MAX_GUI_LINES, f"T5 RED: gui.py still {gui_loc} LOC > {MAX_GUI_LINES}"
