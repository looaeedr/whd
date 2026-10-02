from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from phase6_hole_editor_session import HoleEditorAction


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
HOLE_EDITOR = ROOT / "gui_modules" / "editors" / "hole_editor.py"
TARGET_CALLBACKS = {"on_created_select", "toggle_created_process", "delete_selected"}


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
        (item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == "HoleEditorCreatedListActions"),
        None,
    )
    assert node is not None, "T5 RED: HoleEditorCreatedListActions is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"HoleEditorAction": HoleEditorAction}
    exec(compile(module, str(HOLE_EDITOR), "exec"), namespace)
    return namespace["HoleEditorCreatedListActions"]


def test_created_list_actions_move_out_of_unified_root_into_editor_orchestration():
    nested = _unified_nested_names()
    assert not (nested & TARGET_CALLBACKS), f"T5 RED: rooted created-list callbacks remain: {sorted(nested & TARGET_CALLBACKS)}"

    tree = ast.parse(HOLE_EDITOR.read_text(encoding="utf-8"))
    cls = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "HoleEditorCreatedListActions"),
        None,
    )
    assert cls is not None, "T5 RED: HoleEditorCreatedListActions is missing"
    assert _span(cls) <= 120
    methods = {node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)}
    assert TARGET_CALLBACKS <= methods.keys()
    assert all(_span(methods[name]) <= 35 for name in TARGET_CALLBACKS)


def test_created_list_actions_preserve_select_toggle_delete_and_refresh_order():
    cls = _actions_class()
    calls: list[object] = []

    class FakeList:
        def __init__(self, selection=()):
            self.selection = tuple(selection)

        def curselection(self):
            return self.selection

    class FakeSession:
        def __init__(self):
            self.selected_index = 0
            self.actions = []

        def execute(self, action):
            self.actions.append(action)
            if action.kind == "select":
                self.selected_index = int(action.index)
            elif action.kind == "delete_selected":
                self.selected_index = -1

    session = FakeSession()
    created = FakeList((1,))
    features = [SimpleNamespace(layer="CUTTING"), SimpleNamespace(layer="BLIND_HOLE")]

    def transform(feature, process):
        calls.append(("transform", feature, process))
        return SimpleNamespace(layer=process, original=feature)

    actions = cls(
        hole_session=session,
        feature_list=features,
        created_list=created,
        select_feature=lambda idx: calls.append(("select_feature", idx)),
        feature_with_process=transform,
        refresh_created=lambda: calls.append("created"),
        refresh_reference_fields=lambda: calls.append("reference"),
        redraw=lambda: calls.append("redraw"),
        sync_all=lambda: calls.append("sync"),
    )

    actions.on_created_select()
    assert calls == [("select_feature", 1)]

    calls.clear()
    session.actions.clear()
    actions.toggle_created_process()
    assert [action.kind for action in session.actions] == ["select", "replace_selected_committed"]
    assert calls[0][0] == "transform"
    assert calls[0][2] == "CUTTING"
    assert calls[1:] == ["created", "reference", "redraw", "sync"]

    calls.clear()
    session.actions.clear()
    session.selected_index = 0
    actions.delete_selected()
    assert [action.kind for action in session.actions] == ["delete_selected"]
    assert calls == ["created", "reference", "redraw", "sync"]

    calls.clear()
    session.actions.clear()
    session.selected_index = -1
    actions.delete_selected()
    assert session.actions == []
    assert calls == []
