from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
VIEW = ROOT / "gui_modules" / "editors" / "hole_editor_view.py"
TARGET_CALLBACKS = {"_baseline_status_color", "_refresh_indicator_component_contexts"}


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def _unified_nested_names() -> set[str]:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost")
    unified = next(n for n in host.body if isinstance(n, ast.FunctionDef) and n.name == "_open_unified_hole_editor")
    return {n.name for n in ast.walk(unified) if isinstance(n, ast.FunctionDef) and n is not unified}


class _FakeTk:
    X = "x"


def _refresh_class():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorIndicatorContextRefresh"), None)
    assert node is not None, "T5 RED: HoleEditorIndicatorContextRefresh is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {"tk": _FakeTk}
    exec(compile(module, str(VIEW), "exec"), ns)
    return ns["HoleEditorIndicatorContextRefresh"]


class _Var:
    def __init__(self, value=""):
        self.value = value
    def set(self, value):
        self.value = value


class _Label:
    def __init__(self):
        self.config = {}
    def configure(self, **kwargs):
        self.config.update(kwargs)


class _Tabs:
    def __init__(self, selected="main"):
        self.selected = selected
        self.managed = ""
        self.calls = []
    def select(self):
        return self.selected
    def winfo_manager(self):
        return self.managed
    def pack(self, **kwargs):
        self.calls.append(("pack", kwargs))
        self.managed = "pack"
    def pack_forget(self):
        self.calls.append(("pack_forget",))
        self.managed = ""


def _make_controller(*, state_fn, context_provider, active_key, editor_selected="main"):
    cls = _refresh_class()
    status = _Var()
    label = _Label()
    editor_tabs = _Tabs(editor_selected)
    component_tabs = _Tabs("box-component")
    contexts = {}
    visible_calls = []
    redraw_calls = []
    switch_calls = []
    active = [active_key]

    def switch(key):
        switch_calls.append(key)
        active[0] = key

    controller = cls(
        component_context_provider=context_provider,
        indicator_mode_available=True,
        collect_indicator_state=state_fn,
        component_contexts=contexts,
        baseline_status_var=status,
        baseline_status_label=label,
        set_indicator_page_visible=lambda visible: visible_calls.append(bool(visible)),
        active_context_key_provider=lambda: active[0],
        switch_editor_context=switch,
        redraw=lambda: redraw_calls.append("redraw"),
        editor_tabs=editor_tabs,
        indicator_page="indicator-page",
        component_tabs=component_tabs,
        toolbar="toolbar",
        selected_component_key_provider=lambda: "indicator_box",
    )
    return controller, contexts, status, label, editor_tabs, component_tabs, visible_calls, redraw_calls, switch_calls, active


def test_indicator_context_refresh_callbacks_move_out_of_unified_root_into_view():
    nested = _unified_nested_names()
    assert not (nested & TARGET_CALLBACKS), f"T5 RED: rooted indicator context callbacks remain: {sorted(nested & TARGET_CALLBACKS)}"
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorIndicatorContextRefresh"), None)
    assert cls is not None, "T5 RED: HoleEditorIndicatorContextRefresh is missing"
    assert _span(cls) <= 125
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    assert {"baseline_status_color", "refresh"} <= methods.keys()
    assert _span(methods["baseline_status_color"]) <= 5
    assert _span(methods["refresh"]) <= 60


def test_baseline_status_color_preserves_existing_status_semantics():
    cls = _refresh_class()
    assert cls.baseline_status_color("基準檔：door.dxf") == "#64d2ff"
    assert cls.baseline_status_color("指示燈盒資料錯誤") == "#ff9f0a"
    assert cls.baseline_status_color(None) == "#ff9f0a"


def test_refresh_returns_to_door_when_indicator_mode_is_not_active():
    controller, contexts, status, label, editor_tabs, component_tabs, visible, redraws, switches, active = _make_controller(
        state_fn=lambda: {"mode": "normal"},
        context_provider=lambda state: {"indicator_box": {"part_key": "indicator_box"}},
        active_key="indicator_box",
        editor_selected="main",
    )
    controller.refresh()
    assert component_tabs.calls == [("pack_forget",)]
    assert switches == ["door"]
    assert active == ["door"]
    assert visible == [False]
    assert redraws == ["redraw"]
    assert contexts == {}


def test_refresh_surfaces_provider_error_without_mutating_contexts():
    def boom(_state):
        raise RuntimeError("bad data")

    controller, contexts, status, label, editor_tabs, component_tabs, visible, redraws, switches, active = _make_controller(
        state_fn=lambda: {"mode": "indicator_box"},
        context_provider=boom,
        active_key="door",
        editor_selected="main",
    )
    controller.refresh()
    assert contexts == {}
    assert status.value == "指示燈盒資料錯誤：bad data"
    assert label.config == {"fg": "#ff453a"}
    assert visible == [True]
    assert redraws == ["redraw"]
    assert switches == []


def test_refresh_updates_live_contexts_and_routes_selected_indicator_component():
    new_box = {"part_key": "indicator_box", "baseline_status_text": "基準檔：box.dxf"}
    new_door = {"part_key": "indicator_door", "baseline_status_text": "基準檔：door.dxf"}
    controller, contexts, status, label, editor_tabs, component_tabs, visible, redraws, switches, active = _make_controller(
        state_fn=lambda: {"mode": "indicator_box", "version": 1},
        context_provider=lambda state: {"indicator_box": new_box, "indicator_door": new_door},
        active_key="door",
        editor_selected="indicator-page",
    )
    controller.refresh()
    assert contexts == {"indicator_box": new_box, "indicator_door": new_door}
    assert visible == [True]
    assert component_tabs.calls == [("pack", {"fill": "x", "pady": (0, 4), "before": "toolbar"})]
    assert switches == ["indicator_box"]
    assert redraws == []
