from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from phase6_hole_editor_session import HoleEditorAction

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
HOLE_EDITOR = ROOT / "gui_modules" / "editors" / "hole_editor.py"
TARGET_CALLBACKS = {"set_reference_anchor", "apply_reference_value", "schedule_reference_value"}


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def _unified_nested_names() -> set[str]:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost")
    unified = next(n for n in host.body if isinstance(n, ast.FunctionDef) and n.name == "_open_unified_hole_editor")
    return {n.name for n in ast.walk(unified) if isinstance(n, ast.FunctionDef) and n is not unified}


def _reference_class():
    tree = ast.parse(HOLE_EDITOR.read_text(encoding="utf-8"))
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorReferenceActions"), None)
    assert node is not None, "T5 RED: HoleEditorReferenceActions is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {"HoleEditorAction": HoleEditorAction}
    exec(compile(module, str(HOLE_EDITOR), "exec"), ns)
    return ns["HoleEditorReferenceActions"]


def test_reference_callbacks_move_out_of_unified_root():
    nested = _unified_nested_names()
    assert not (nested & TARGET_CALLBACKS), f"T5 RED: rooted reference callbacks remain: {sorted(nested & TARGET_CALLBACKS)}"
    tree = ast.parse(HOLE_EDITOR.read_text(encoding="utf-8"))
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorReferenceActions"), None)
    assert cls is not None, "T5 RED: HoleEditorReferenceActions is missing"
    assert _span(cls) <= 130
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    assert TARGET_CALLBACKS <= methods.keys()
    assert all(_span(methods[name]) <= 40 for name in TARGET_CALLBACKS)


def test_reference_actions_use_live_context_and_preserve_apply_semantics():
    cls = _reference_class()
    calls: list[object] = []
    suppress = [False]
    features = [SimpleNamespace(anchor="LEFT", marker="door")]
    context = {"feature_list": features, "surface": "door", "width": 100.0, "height": 80.0}

    class Var:
        def __init__(self, value=""):
            self.value = value
        def get(self):
            return self.value

    class Session:
        selected_index = 0
        def __init__(self): self.actions = []
        def execute(self, action):
            self.actions.append(action)
            if action.kind == "replace_selected":
                context["feature_list"][self.selected_index] = action.feature

    class Editor:
        def __init__(self): self.cancelled = []; self.scheduled = []
        def after_cancel(self, ident): self.cancelled.append(ident)
        def after(self, delay, callback):
            self.scheduled.append((delay, callback)); return f"after-{len(self.scheduled)}"

    session = Session(); editor = Editor(); pending = {}
    vars_map = {("x", "edge"): Var("12.5"), ("x", "neighbor"): Var(), ("y", "edge"): Var(), ("y", "neighbor"): Var()}

    def with_anchor(feature, anchor):
        return SimpleNamespace(anchor=anchor, marker=feature.marker)

    def move(surface, feature_list, idx, anchor, width, height, **kwargs):
        calls.append(("move", surface, feature_list[idx].marker, anchor, width, height, kwargs))
        return SimpleNamespace(anchor=anchor, marker="moved")

    actions = cls(
        hole_session=session,
        context_provider=lambda: context,
        suppress_entry_events=suppress,
        reference_variables=vars_map,
        pending_after=pending,
        editor=editor,
        feature_with_reference_anchor=with_anchor,
        feature_reference_anchor=lambda feature: feature.anchor,
        move_feature_by_reference_distance=move,
        active_reference_guide=lambda: "guide",
        refresh_reference_fields=lambda: calls.append("reference"),
        redraw=lambda: calls.append("redraw"),
        sync_all=lambda: calls.append("sync"),
        show_format_error=lambda: calls.append("format-error"),
    )

    actions.set_reference_anchor("RIGHT")
    assert context["feature_list"][0].anchor == "RIGHT"
    assert [a.kind for a in session.actions] == ["replace_selected"]
    assert calls == ["reference", "redraw", "sync"]

    session.actions.clear(); calls.clear()
    context.clear(); context.update({"feature_list": [SimpleNamespace(anchor="TOP", marker="indicator")], "surface": "indicator", "width": 44.0, "height": 33.0})
    actions.apply_reference_value("x", "edge", True)
    assert [a.kind for a in session.actions] == ["replace_selected"]
    assert calls[0][0:6] == ("move", "indicator", "indicator", "TOP", 44.0, 33.0)
    assert calls[0][6]["axis"] == "x" and calls[0][6]["mode"] == "edge" and calls[0][6]["value"] == 12.5
    assert calls[0][6]["reference_guide"] == "guide"
    assert calls[1:] == ["reference", "redraw", "sync"]


def test_reference_schedule_and_invalid_input_semantics():
    cls = _reference_class()
    calls: list[object] = []
    class Var:
        def __init__(self, value): self.value = value
        def get(self): return self.value
    class Session:
        selected_index = 0
        def execute(self, action): calls.append(action.kind)
    class Editor:
        def __init__(self): self.cancelled = []; self.callbacks = []
        def after_cancel(self, ident): self.cancelled.append(ident)
        def after(self, delay, callback): self.callbacks.append((delay, callback)); return "new-id"
    editor = Editor(); pending = {("x", "edge"): "old-id"}
    vars_map = {("x", "edge"): Var("bad"), ("x", "neighbor"): Var(""), ("y", "edge"): Var("-1"), ("y", "neighbor"): Var("0")}
    actions = cls(
        hole_session=Session(), context_provider=lambda: {"feature_list": [SimpleNamespace(anchor="LEFT")], "surface": "s", "width": 1.0, "height": 1.0},
        suppress_entry_events=[False], reference_variables=vars_map, pending_after=pending, editor=editor,
        feature_with_reference_anchor=lambda f, a: f, feature_reference_anchor=lambda f: f.anchor,
        move_feature_by_reference_distance=lambda *a, **k: a[1][a[2]], active_reference_guide=lambda: None,
        refresh_reference_fields=lambda: calls.append("reference"), redraw=lambda: calls.append("redraw"), sync_all=lambda: calls.append("sync"),
        show_format_error=lambda: calls.append("format-error"),
    )
    actions.apply_reference_value("x", "edge", True)
    assert calls == ["format-error", "reference"]
    calls.clear(); actions.apply_reference_value("y", "edge", True); assert calls == []
    actions.schedule_reference_value("x", "edge")
    assert editor.cancelled == ["old-id"] and pending[("x", "edge")] == "new-id"
    assert editor.callbacks[0][0] == 350
