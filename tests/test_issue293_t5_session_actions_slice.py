from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from phase6_hole_editor_session import HoleEditorAction


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
HOLE_EDITOR = ROOT / "gui_modules" / "editors" / "hole_editor.py"
TARGET_CALLBACKS = {
    "commit_active_edit",
    "undo_last_action",
    "cancel_active_edit",
    "begin_edit",
    "select_feature",
}


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def _unified_nested_names() -> set[str]:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    unified = next(
        node for node in host.body
        if isinstance(node, ast.FunctionDef) and node.name == "_open_unified_hole_editor"
    )
    return {
        node.name
        for node in ast.walk(unified)
        if isinstance(node, ast.FunctionDef) and node is not unified
    }


def _actions_class():
    tree = ast.parse(HOLE_EDITOR.read_text(encoding="utf-8"))
    node = next(
        (item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == "HoleEditorTransientActions"),
        None,
    )
    assert node is not None, "T5 RED: HoleEditorTransientActions is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"HoleEditorAction": HoleEditorAction}
    exec(compile(module, str(HOLE_EDITOR), "exec"), namespace)
    return namespace["HoleEditorTransientActions"]


def test_session_actions_move_out_of_unified_root_into_editor_orchestration():
    nested = _unified_nested_names()
    assert not (nested & TARGET_CALLBACKS), f"T5 RED: rooted transient callbacks remain: {sorted(nested & TARGET_CALLBACKS)}"

    tree = ast.parse(HOLE_EDITOR.read_text(encoding="utf-8"))
    cls = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "HoleEditorTransientActions"),
        None,
    )
    assert cls is not None, "T5 RED: HoleEditorTransientActions is missing"
    assert _span(cls) <= 150
    methods = {node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)}
    assert TARGET_CALLBACKS <= methods.keys()
    assert all(_span(methods[name]) <= 40 for name in TARGET_CALLBACKS)


def test_session_action_callbacks_preserve_transaction_and_refresh_order():
    cls = _actions_class()

    calls: list[str] = []

    class FakeSession:
        def __init__(self):
            self.selected_index = -1
            self.has_active_edit = True
            self.actions = []

        def execute(self, action):
            self.actions.append(action)
            if action.kind == "select":
                self.selected_index = int(action.index)
                self.has_active_edit = True
            elif action.kind == "cancel_active":
                self.has_active_edit = False

    class FakeVar:
        def __init__(self):
            self.values = []

        def set(self, value):
            self.values.append(value)

    session = FakeSession()
    rotation = FakeVar()
    features = [SimpleNamespace(rotation_deg=90)]
    actions = cls(
        hole_session=session,
        feature_list=features,
        var_rotation=rotation,
        refresh_created=lambda: calls.append("created"),
        refresh_reference_fields=lambda: calls.append("reference"),
        redraw=lambda: calls.append("redraw"),
        sync_all=lambda: calls.append("sync"),
    )

    actions.begin_edit(0)
    assert [action.kind for action in session.actions] == ["select"]
    assert rotation.values == ["90°"]
    assert calls == ["created", "reference", "redraw"]

    session.actions.clear()
    calls.clear()
    actions.commit_active_edit(keep_selected=False)
    assert [(action.kind, action.keep_selected) for action in session.actions] == [("commit_active", False)]
    assert calls == ["created", "reference", "redraw"]

    session.actions.clear()
    calls.clear()
    assert actions.undo_last_action() == "break"
    assert [action.kind for action in session.actions] == ["undo"]
    assert calls == ["created", "reference", "redraw", "sync"]

    session.actions.clear()
    calls.clear()
    session.has_active_edit = False
    assert actions.cancel_active_edit() is False
    assert [action.kind for action in session.actions] == ["cancel_active"]
    assert calls == []

    session.actions.clear()
    calls.clear()
    session.has_active_edit = True
    assert actions.cancel_active_edit() is True
    assert [action.kind for action in session.actions] == ["cancel_active"]
    assert calls == ["created", "reference", "sync", "redraw"]
