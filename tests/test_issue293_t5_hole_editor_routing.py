from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
EDITOR = ROOT / "gui_modules" / "editors" / "hole_editor.py"
VIEW = ROOT / "gui_modules" / "editors" / "hole_editor_view.py"
MAX_ROOT_DELEGATE_LINES = 12


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


def _module_function(name: str) -> ast.FunctionDef:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def test_issue293_hole_editor_routing_modules_exist_without_reverse_gui_imports():
    assert EDITOR.is_file(), "T5 RED: hole_editor.py has not been extracted"
    assert VIEW.is_file(), "T5 RED: hole_editor_view.py has not been extracted"
    joined = EDITOR.read_text(encoding="utf-8") + "\n" + VIEW.read_text(encoding="utf-8")
    assert "from gui import" not in joined
    assert "import gui" not in joined
    assert "compatibility.legacy_exports" not in joined


def test_issue293_root_head_tail_entrypoint_and_hint_are_thin_delegates():
    open_method = _host_method("open_hole_editor")
    hint = _module_function("draw_hole_editor_hint")
    assert _span(open_method) <= MAX_ROOT_DELEGATE_LINES, (
        f"T5 RED: open_hole_editor remains rooted ({_span(open_method)} LOC)"
    )
    assert _span(hint) <= MAX_ROOT_DELEGATE_LINES, (
        f"T5 RED: draw_hole_editor_hint remains rooted ({_span(hint)} LOC)"
    )
    gui_source = GUI.read_text(encoding="utf-8")
    assert "_open_hole_editor_impl" in gui_source
    assert "_draw_hole_editor_hint_impl" in gui_source


def test_issue293_view_hint_preserves_current_presentation_contract():
    from gui_modules.editors.hole_editor_view import draw_hole_editor_hint

    calls = []

    class Canvas:
        def create_text(self, *args, **kwargs):
            calls.append((args, kwargs))

    draw_hole_editor_hint(Canvas(), 640, endcap=True)
    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args[:2] == (622, 18)
    assert kwargs["text"] == "雙擊：開孔"
    assert kwargs["anchor"] == "ne"
    assert kwargs["fill"] == "#ff9f0a"
    assert kwargs["font"] == ("Microsoft JhengHei", 9, "bold")
    assert kwargs["tags"] == ("phase6_hole_hint",)


def test_issue293_head_tail_routing_preserves_adapter_contract(monkeypatch):
    from gui_modules.editors import hole_editor

    errors = []
    monkeypatch.setattr(hole_editor.messagebox, "showerror", lambda *a, **k: errors.append((a, k)))

    guide = SimpleNamespace(min_point="MIN", max_point="MAX")
    surface = object()
    reference_guide = object()
    monkeypatch.setattr(hole_editor, "resolve_endcap_finished_face_guide", lambda w, h, t: guide)
    monkeypatch.setattr(
        hole_editor,
        "feature_surface_from_rect",
        lambda key, min_point, max_point: surface,
    )
    monkeypatch.setattr(hole_editor, "legacy_hole_to_feature", lambda hole: f"feature:{hole}")
    monkeypatch.setattr(hole_editor, "feature_to_legacy_hole", lambda feature, w, h: f"legacy:{feature}:{w}:{h}")
    monkeypatch.setattr(hole_editor, "Vec2", lambda x, y: (x, y))
    monkeypatch.setattr(hole_editor, "RectGuide", lambda a, b, kind: reference_guide)

    class Host:
        def __init__(self):
            self.head_holes = ["H1"]
            self.tail_holes = ["T1"]
            self.surface_features = {"head": [], "tail": []}
            self.calls = []

        def get_float_values(self):
            return {"w": 800, "d": 300, "t": 2}

        def _open_unified_hole_editor(self, *args, **kwargs):
            self.calls.append((args, kwargs))

    host = Host()
    hole_editor.open_hole_editor(host, "head")
    assert errors == []
    assert host.surface_features["head"] == ["feature:H1"]
    assert len(host.calls) == 1
    args, kwargs = host.calls[0]
    assert args[:5] == ("head", "封頭", surface, 800.0, 300.0)
    assert kwargs["reference_guide"] is reference_guide
    assert callable(kwargs["sync_callback"])

    host.surface_features["head"][:] = ["edited"]
    kwargs["sync_callback"]()
    assert host.head_holes == ["legacy:edited:800.0:300.0"]

    bad = Host()
    hole_editor.open_hole_editor(bad, "bogus")
    assert bad.calls == []
    assert errors[-1][0] == ("開孔失敗", "未知板面: bogus")


def test_issue293_head_tail_routing_preserves_invalid_input_error(monkeypatch):
    from gui_modules.editors import hole_editor

    errors = []
    monkeypatch.setattr(hole_editor.messagebox, "showerror", lambda *a, **k: errors.append((a, k)))

    class Host:
        head_holes = []
        tail_holes = []
        surface_features = {"head": [], "tail": []}

        def get_float_values(self):
            raise ValueError("bad")

        def _open_unified_hole_editor(self, *args, **kwargs):
            raise AssertionError("must not open")

    hole_editor.open_hole_editor(Host(), "head")
    assert errors == [(('輸入錯誤', '請先確保主畫面所有數值輸入正確'), {})]
