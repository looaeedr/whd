from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
VIEW = ROOT / "gui_modules" / "editors" / "hole_editor_view.py"
TARGET_CALLBACKS = {"set_indicator_page_visible", "request_indicator_redraw", "on_box_distance_toggle"}


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def _unified_nested_names() -> set[str]:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost")
    unified = next(n for n in host.body if isinstance(n, ast.FunctionDef) and n.name == "_open_unified_hole_editor")
    return {n.name for n in ast.walk(unified) if isinstance(n, ast.FunctionDef) and n is not unified}


def _ui_class():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorIndicatorUiActions"), None)
    assert node is not None, "T5 RED: HoleEditorIndicatorUiActions is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {}
    exec(compile(module, str(VIEW), "exec"), ns)
    return ns["HoleEditorIndicatorUiActions"]


def test_indicator_ui_callbacks_move_out_of_unified_root_into_view():
    nested = _unified_nested_names()
    assert not (nested & TARGET_CALLBACKS), f"T5 RED: rooted indicator UI callbacks remain: {sorted(nested & TARGET_CALLBACKS)}"
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorIndicatorUiActions"), None)
    assert cls is not None, "T5 RED: HoleEditorIndicatorUiActions is missing"
    assert _span(cls) <= 100
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    assert TARGET_CALLBACKS <= methods.keys()
    assert all(_span(methods[name]) <= 30 for name in TARGET_CALLBACKS)


def test_indicator_page_visibility_preserves_add_switch_forget_semantics():
    cls = _ui_class()
    calls: list[object] = []
    visible = [False]

    class Notebook:
        def __init__(self):
            self.items = {"main"}
            self.current = "main"
        def tabs(self): return tuple(self.items)
        def add(self, page, text): self.items.add(str(page)); calls.append(("add", str(page), text))
        def select(self, page=None):
            if page is None: return self.current
            self.current = str(page); calls.append(("select", str(page)))
        def forget(self, page): self.items.discard(str(page)); calls.append(("forget", str(page)))

    notebook = Notebook()
    actions = cls(
        editor_tabs=notebook, indicator_page="indicator", main_page="main",
        indicator_page_visible=visible, mode_provider=lambda: "none",
        context_refresh_provider=lambda: None, redraw_provider=lambda: None,
        schedule_idle=lambda fn: calls.append(("idle", fn)),
        refresh_reference_fields=lambda: calls.append("reference"),
    )
    actions.set_indicator_page_visible(True)
    assert visible == [True]
    assert calls == [("add", "indicator", "  指示燈盒  ")]

    calls.clear(); notebook.current = "indicator"
    actions.set_indicator_page_visible(False)
    assert visible == [False]
    assert calls == [("select", "main"), ("forget", "indicator")]


def test_indicator_redraw_prefers_context_refresh_then_falls_back_and_box_toggle_refreshes_reference():
    cls = _ui_class()
    calls: list[object] = []
    mode = ["indicator_box"]
    context_fn = [lambda: calls.append("context-refresh")]
    redraw_fn = [lambda: calls.append("redraw")]

    class Notebook:
        def __init__(self): self.items = {"main"}
        def tabs(self): return tuple(self.items)
        def add(self, page, text): self.items.add(str(page)); calls.append(("add", str(page)))
        def select(self, page=None): return "main"
        def forget(self, page): self.items.discard(str(page)); calls.append(("forget", str(page)))

    scheduled: list[object] = []
    def idle(fn): scheduled.append(fn); calls.append(("idle", fn))

    actions = cls(
        editor_tabs=Notebook(), indicator_page="indicator", main_page="main",
        indicator_page_visible=[False], mode_provider=lambda: mode[0],
        context_refresh_provider=lambda: context_fn[0], redraw_provider=lambda: redraw_fn[0],
        schedule_idle=idle, refresh_reference_fields=lambda: calls.append("reference"),
    )
    actions.request_indicator_redraw()
    assert calls[0] == ("add", "indicator")
    assert calls[1][0] == "idle" and scheduled[-1] is context_fn[0]

    calls.clear(); scheduled.clear(); context_fn[0] = None
    actions.request_indicator_redraw()
    assert calls[0][0] == "idle" and scheduled[-1] is redraw_fn[0]

    calls.clear(); scheduled.clear(); mode[0] = "none"
    actions.on_box_distance_toggle()
    assert any(item[0] == "forget" for item in calls if isinstance(item, tuple))
    assert len(scheduled) == 2
    scheduled[0](); scheduled[1]()
    assert calls[-2:] == ["redraw", "reference"]
