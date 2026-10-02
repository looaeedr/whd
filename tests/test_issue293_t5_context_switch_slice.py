from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
ORCH = ROOT / "gui_modules" / "editors" / "hole_editor.py"
TRACKED = {"feature_list", "surface", "width", "height", "reference_guide", "baseline_scene"}


def _unified_method():
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost")
    return next(n for n in host.body if isinstance(n, ast.FunctionDef) and n.name == "_open_unified_hole_editor")


def _nested_names():
    unified = _unified_method()
    return {n.name for n in ast.walk(unified) if isinstance(n, ast.FunctionDef) and n is not unified}


def _class(name):
    tree = ast.parse(ORCH.read_text(encoding="utf-8"))
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name), None)
    assert node is not None, f"T5 RED: {name} is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {}
    exec(compile(module, str(ORCH), "exec"), ns)
    return ns[name], node


def _span(node):
    return int(node.end_lineno) - int(node.lineno) + 1


class _Session:
    def __init__(self):
        self.has_active_edit = True
        self.active_features = ["active"]
        self.calls = []

    def activate_context(self, key, features):
        self.calls.append((key, list(features)))


class _Button:
    def __init__(self):
        self.kwargs = []

    def configure(self, **kwargs):
        self.kwargs.append(kwargs)


class _Var:
    def __init__(self):
        self.value = None

    def set(self, value):
        self.value = value


class _Label(_Button):
    pass


def test_context_switch_moves_out_of_unified_root_and_has_bounded_owners():
    assert "_switch_editor_context" not in _nested_names(), "T5 RED: context switch remains rooted"
    _, state_node = _class("HoleEditorLiveContext")
    _, switch_node = _class("HoleEditorContextSwitcher")
    assert _span(state_node) <= 70
    assert _span(switch_node) <= 120
    for node in (state_node, switch_node):
        for method in (n for n in node.body if isinstance(n, ast.FunctionDef)):
            assert _span(method) <= 80, f"{node.name}.{method.name} is too large"


def test_live_context_is_transient_mapping_owner():
    cls, _ = _class("HoleEditorLiveContext")
    live = cls(
        feature_list=["door"], surface="S0", width=800, height=600,
        reference_guide="G0", baseline_scene="B0", part_key="door",
    )
    assert live.as_dict() == {
        "feature_list": ["door"], "surface": "S0", "width": 800.0, "height": 600.0,
        "reference_guide": "G0", "baseline_scene": "B0", "part_key": "door",
    }
    live.apply({
        "feature_list": ["box"], "surface": "S1", "width": 320, "height": 210,
        "reference_guide": "G1", "baseline_scene": "B1", "part_key": "indicator_box",
    })
    assert live.feature_list == ["box"]
    assert live.surface == "S1"
    assert live.width == 320.0
    assert live.height == 210.0
    assert live.reference_guide == "G1"
    assert live.baseline_scene == "B1"
    assert live.part_key == "indicator_box"


def test_context_switcher_reuses_session_and_updates_live_presentation_state():
    state_cls, _ = _class("HoleEditorLiveContext")
    switch_cls, _ = _class("HoleEditorContextSwitcher")
    live = state_cls(
        feature_list=["door"], surface="S0", width=800, height=600,
        reference_guide="G0", baseline_scene="B0", part_key="door",
    )
    session = _Session()
    insert_mode = [True]
    insert_btn = _Button()
    active_part_key = ["door"]
    position_authority = [object()]
    status_var = _Var()
    status_label = _Label()
    cancelled = []
    refreshed = []
    contexts = {
        "indicator_box": {
            "feature_list": ["candidate"], "surface": "S1", "width": 320, "height": 210,
            "reference_guide": "G1", "baseline_scene": "B1", "part_key": "indicator_box",
            "baseline_status_text": "基準檔：indicator_box.dxf",
        }
    }
    switcher = switch_cls(
        live_context=live,
        hole_session=session,
        door_context={"feature_list": ["door"], "surface": "S0", "width": 800, "height": 600,
                      "reference_guide": "G0", "baseline_scene": "B0", "part_key": "door"},
        indicator_contexts=contexts,
        cancel_active_edit=lambda: cancelled.append(True),
        insert_mode=insert_mode,
        insert_button=insert_btn,
        active_part_key=active_part_key,
        position_authority=position_authority,
        baseline_status_var=status_var,
        baseline_status_label=status_label,
        baseline_status_color=lambda text: "BLUE" if text.startswith("基準檔：") else "ORANGE",
        refresh_created=lambda: refreshed.append("created"),
        refresh_reference_fields=lambda: refreshed.append("reference"),
        redraw=lambda: refreshed.append("redraw"),
    )
    assert switcher.switch("indicator_box") is True
    assert cancelled == [True]
    assert insert_mode == [False]
    assert insert_btn.kwargs == [{"text": "插入", "bg": "#30d158"}]
    assert session.calls == [("indicator_box", ["candidate"])]
    assert live.feature_list == ["active"]
    assert live.surface == "S1" and live.width == 320.0 and live.height == 210.0
    assert live.reference_guide == "G1" and live.baseline_scene == "B1"
    assert live.part_key == "indicator_box" and active_part_key == ["indicator_box"]
    assert position_authority == [None]
    assert status_var.value == "基準檔：indicator_box.dxf"
    assert status_label.kwargs == [{"fg": "BLUE"}]
    assert refreshed == ["created", "reference", "redraw"]


def test_missing_context_is_noop_after_transient_cleanup_guard():
    state_cls, _ = _class("HoleEditorLiveContext")
    switch_cls, _ = _class("HoleEditorContextSwitcher")
    live = state_cls(feature_list=["door"], surface="S0", width=1, height=2,
                     reference_guide="G0", baseline_scene=None, part_key="door")
    session = _Session()
    session.has_active_edit = False
    insert_mode = [False]
    switcher = switch_cls(
        live_context=live, hole_session=session, door_context=None, indicator_contexts={},
        cancel_active_edit=lambda: None, insert_mode=insert_mode, insert_button=_Button(),
        active_part_key=["door"], position_authority=[None], baseline_status_var=_Var(),
        baseline_status_label=None, baseline_status_color=lambda text: "X",
        refresh_created=lambda: None, refresh_reference_fields=lambda: None, redraw=lambda: None,
    )
    before = live.as_dict()
    assert switcher.switch("missing") is False
    assert live.as_dict() == before
    assert session.calls == []


def test_gui_wiring_uses_live_context_instead_of_stale_lambda_captures():
    gui = GUI.read_text(encoding="utf-8")
    composition = (ROOT / "gui_modules" / "editors" / "hole_editor_composition.py").read_text(encoding="utf-8")
    assert "HoleEditorLiveContext as _HoleEditorLiveContext" in gui
    assert "HoleEditorContextSwitcher as _HoleEditorContextSwitcher" in gui
    assert "s.live_context = d._HoleEditorLiveContext(" in composition
    assert "context_switcher = d._HoleEditorContextSwitcher(" in composition
    assert "s.switch_editor_context = context_switcher.switch" in composition
    assert "switch_editor_context=s.switch_editor_context" in composition

    tree = ast.parse(composition)
    stale = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Lambda):
            continue
        loaded = {
            child.id for child in ast.walk(node)
            if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load) and child.id in TRACKED
        }
        if loaded:
            stale.append((node.lineno, sorted(loaded)))
    assert not stale, f"T5 RED: composition callbacks still capture stale context locals: {stale}"
