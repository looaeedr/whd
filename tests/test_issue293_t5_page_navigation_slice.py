from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
VIEW = ROOT / "gui_modules" / "editors" / "hole_editor_view.py"
TARGET_CALLBACKS = {
    "_selected_indicator_component_key",
    "_on_editor_page_changed",
    "_on_indicator_component_page_changed",
}


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def _unified_nested_names() -> set[str]:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost")
    unified = next(n for n in host.body if isinstance(n, ast.FunctionDef) and n.name == "_open_unified_hole_editor")
    return {n.name for n in ast.walk(unified) if isinstance(n, ast.FunctionDef) and n is not unified}


class _FakeTk:
    X = "x"


def _navigation_class():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorPageNavigation"), None)
    assert node is not None, "T5 RED: HoleEditorPageNavigation is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {"tk": _FakeTk}
    exec(compile(module, str(VIEW), "exec"), ns)
    return ns["HoleEditorPageNavigation"]


def test_page_navigation_callbacks_move_out_of_unified_root_into_view():
    nested = _unified_nested_names()
    assert not (nested & TARGET_CALLBACKS), f"T5 RED: rooted page-navigation callbacks remain: {sorted(nested & TARGET_CALLBACKS)}"
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorPageNavigation"), None)
    assert cls is not None, "T5 RED: HoleEditorPageNavigation is missing"
    assert _span(cls) <= 90
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    expected = {"selected_indicator_component_key", "on_editor_page_changed", "on_indicator_component_page_changed"}
    assert expected <= methods.keys()
    assert all(_span(methods[name]) <= 25 for name in expected)


def test_selected_indicator_component_key_tracks_current_component_tab():
    cls = _navigation_class()

    class Tabs:
        def __init__(self): self.selected = "box-page"
        def select(self): return self.selected

    component_tabs = Tabs()
    actions = cls(
        editor_tabs=None,
        main_page=None,
        indicator_page=None,
        component_tabs=component_tabs,
        indicator_door_page="door-page",
        toolbar=object(),
        refresh_indicator_component_contexts=lambda: None,
        switch_editor_context=lambda key: None,
    )
    assert actions.selected_indicator_component_key() == "indicator_box"
    component_tabs.selected = "door-page"
    assert actions.selected_indicator_component_key() == "indicator_door"

    actions_no_tabs = cls(
        editor_tabs=None,
        main_page=None,
        indicator_page=None,
        component_tabs=None,
        indicator_door_page=None,
        toolbar=object(),
        refresh_indicator_component_contexts=lambda: None,
        switch_editor_context=lambda key: None,
    )
    assert actions_no_tabs.selected_indicator_component_key() == "indicator_box"


def test_page_change_routes_indicator_and_door_contexts_without_owning_state():
    cls = _navigation_class()
    calls = []

    class Tabs:
        def __init__(self, selected): self.selected = selected
        def select(self): return self.selected

    class ComponentTabs:
        def __init__(self):
            self.selected = "box-page"
            self.managed = ""
        def select(self): return self.selected
        def winfo_manager(self): return self.managed
        def pack(self, **kwargs):
            calls.append(("pack", kwargs))
            self.managed = "pack"
        def pack_forget(self):
            calls.append(("pack_forget",))
            self.managed = ""

    editor_tabs = Tabs("indicator-page")
    component_tabs = ComponentTabs()
    toolbar = object()
    actions = cls(
        editor_tabs=editor_tabs,
        main_page="main-page",
        indicator_page="indicator-page",
        component_tabs=component_tabs,
        indicator_door_page="door-page",
        toolbar=toolbar,
        refresh_indicator_component_contexts=lambda: calls.append(("refresh",)),
        switch_editor_context=lambda key: calls.append(("switch", key)),
    )

    actions.on_editor_page_changed()
    assert calls == [
        ("pack", {"fill": "x", "pady": (0, 4), "before": toolbar}),
        ("refresh",),
    ]

    calls.clear()
    component_tabs.selected = "door-page"
    actions.on_indicator_component_page_changed()
    assert calls == [("switch", "indicator_door")]

    calls.clear()
    editor_tabs.selected = "main-page"
    actions.on_editor_page_changed()
    assert calls == [("pack_forget",), ("switch", "door")]

    calls.clear()
    actions.on_indicator_component_page_changed()
    assert calls == []
