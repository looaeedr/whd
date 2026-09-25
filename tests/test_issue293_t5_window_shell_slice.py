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


def _builder_class():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorWindowShellBuilder"), None)
    assert node is not None, "T5 RED: HoleEditorWindowShellBuilder is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {}
    exec(compile(module, str(VIEW), "exec"), ns)
    return ns["HoleEditorWindowShellBuilder"], node


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def test_window_shell_builder_is_bounded_and_keeps_geometry_policy_exact():
    builder, node = _builder_class()
    assert _span(node) <= 125
    for method in (n for n in node.body if isinstance(n, ast.FunctionDef)):
        assert _span(method) <= 100, f"{method.name} is too large: {_span(method)}"

    assert builder.window_geometry(1920, 1080) == (1280, 820, 320, 130, "1280x820+320+130")
    assert builder.window_geometry(800, 600) == (720, 560, 40, 20, "720x560+40+20")


def test_composition_root_delegates_window_shell_construction():
    gui = GUI.read_text(encoding="utf-8")
    method = _unified_method()
    root_segment = ast.get_source_segment(gui, method) or ""

    assert "HoleEditorWindowShellBuilder as _HoleEditorWindowShellBuilder" in gui
    assert COMPOSITION.is_file(), "T5 RED: window-shell composition handoff is missing"
    composition = COMPOSITION.read_text(encoding="utf-8")
    assert "_HoleEditorWindowShellBuilder(host).build(" in composition
    assert "tk.Toplevel(self.root)" not in root_segment
    assert "editor.winfo_screenwidth()" not in root_segment
    assert "ttk.Notebook(center" not in root_segment


def test_window_shell_slice_materially_reduces_root_without_creating_monolith():
    method = _unified_method()
    assert _span(method) <= 735, f"T5 RED: window-shell slice did not shrink root enough: {_span(method)}"
    gui_loc = len(GUI.read_text(encoding="utf-8").splitlines())
    assert gui_loc <= 6610, f"T5 RED: gui.py did not shed window-shell composition: {gui_loc}"
