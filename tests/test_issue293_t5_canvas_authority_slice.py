from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
VIEW = ROOT / "gui_modules" / "editors" / "hole_editor_view.py"
COMPOSITION = ROOT / "gui_modules" / "editors" / "hole_editor_composition.py"


class _FakeCanvasView:
    def __init__(self, canvas, **kwargs):
        self.canvas = canvas
        self.kwargs = kwargs


def _factory_class():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorCanvasViewFactory"), None)
    assert node is not None, "T5 RED: HoleEditorCanvasViewFactory is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {"Phase6HoleEditorCanvasView": _FakeCanvasView}
    exec(compile(module, str(VIEW), "exec"), ns)
    return ns["HoleEditorCanvasViewFactory"], node


def _unified_method() -> ast.FunctionDef:
    source = GUI.read_text(encoding="utf-8")
    tree = ast.parse(source)
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost")
    return next(n for n in host.body if isinstance(n, ast.FunctionDef) and n.name == "_open_unified_hole_editor")


def test_editor_view_imports_existing_canvas_authority_without_redefining_it():
    source = VIEW.read_text(encoding="utf-8")
    assert "from phase6_hole_editor_canvas_view import Phase6HoleEditorCanvasView" in source
    assert "class Phase6HoleEditorCanvasView" not in source


def test_canvas_factory_is_tiny_and_delegates_to_existing_authority():
    factory, node = _factory_class()
    assert node.end_lineno - node.lineno + 1 <= 16
    canvas = object()
    view = factory.create(
        canvas,
        draw_grid="GRID",
        render_secondary_scene="SECONDARY",
        render_resolved_features="RESOLVED",
        overlay_widgets={"panel": "P"},
    )
    assert view.canvas is canvas
    assert view.kwargs == {
        "draw_grid": "GRID",
        "render_secondary_scene": "SECONDARY",
        "render_resolved_features": "RESOLVED",
        "overlay_widgets": {"panel": "P"},
    }


def test_unified_composition_uses_editor_canvas_factory_not_direct_constructor():
    gui = GUI.read_text(encoding="utf-8")
    assert "HoleEditorCanvasViewFactory as _HoleEditorCanvasViewFactory" in gui
    method = _unified_method()
    root_segment = ast.get_source_segment(gui, method) or ""
    assert "Phase6HoleEditorCanvasView(" not in root_segment
    assert COMPOSITION.is_file(), "T5 RED: canvas authority handoff composition is missing"
    composition = COMPOSITION.read_text(encoding="utf-8")
    assert "_HoleEditorCanvasViewFactory.create(" in composition
    assert "Phase6HoleEditorCanvasView(" not in composition
