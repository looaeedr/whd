from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
HOLE_EDITOR = ROOT / "gui_modules" / "editors" / "hole_editor.py"
TARGET_CALLBACKS = {
    "confirm_reference_edit",
    "confirm_all",
    "cancel_all",
    "on_escape",
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


def _lifecycle_class():
    tree = ast.parse(HOLE_EDITOR.read_text(encoding="utf-8"))
    node = next(
        (item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == "HoleEditorModalLifecycle"),
        None,
    )
    assert node is not None, "T5 RED: HoleEditorModalLifecycle is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, object] = {}
    exec(compile(module, str(HOLE_EDITOR), "exec"), namespace)
    return namespace["HoleEditorModalLifecycle"]


def test_modal_lifecycle_moves_out_of_unified_root_into_editor_orchestration():
    nested = _unified_nested_names()
    assert not (nested & TARGET_CALLBACKS), f"T5 RED: rooted lifecycle callbacks remain: {sorted(nested & TARGET_CALLBACKS)}"

    tree = ast.parse(HOLE_EDITOR.read_text(encoding="utf-8"))
    cls = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "HoleEditorModalLifecycle"),
        None,
    )
    assert cls is not None, "T5 RED: HoleEditorModalLifecycle is missing"
    assert _span(cls) <= 150
    methods = {node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)}
    assert TARGET_CALLBACKS <= methods.keys()
    assert all(_span(methods[name]) <= 40 for name in TARGET_CALLBACKS)


def test_modal_lifecycle_preserves_confirm_cancel_and_escape_order():
    cls = _lifecycle_class()
    calls: list[object] = []

    class FakeSession:
        def __init__(self):
            self.has_active_edit = False

        def finish(self, *, commit):
            calls.append(("finish", commit))

    class FakeEditor:
        def destroy(self):
            calls.append("destroy")

    session = FakeSession()
    editor = FakeEditor()
    position_authority = [None]
    editor_closed = [False]
    insert_mode = [False]
    door_state = {"old": 1}
    has_selection = [True]
    valid_fit = [True]
    collected = {"mode": "indicator", "layers": 2}

    lifecycle = cls(
        hole_session=session,
        has_selected_feature=lambda: has_selection[0],
        position_authority=position_authority,
        commit_active_edit=lambda keep_selected=True: calls.append(("commit_active", keep_selected)),
        sync_all=lambda: calls.append("sync"),
        validate_current_indicator_fit=lambda show_error=False: calls.append(("validate", show_error)) or valid_fit[0],
        door_indicator_state=door_state,
        collect_indicator_state=lambda: calls.append("collect") or dict(collected),
        door_indicator_commit=lambda state: calls.append(("door_commit", dict(state))),
        editor_closed=editor_closed,
        editor=editor,
        on_close=lambda: calls.append("close"),
        insert_mode=insert_mode,
        set_insert_mode=lambda force=None: calls.append(("insert", force)) or insert_mode.__setitem__(0, bool(force)),
        cancel_active_edit=lambda: calls.append("cancel_active") or True,
    )

    lifecycle.confirm_reference_edit()
    assert position_authority == ["reference"]
    assert calls == [("commit_active", False), "sync"]

    calls.clear()
    valid_fit[0] = False
    lifecycle.confirm_all()
    assert calls == [("validate", True)]
    assert editor_closed == [False]

    calls.clear()
    valid_fit[0] = True
    lifecycle.confirm_all()
    assert calls == [
        ("validate", True),
        ("finish", True),
        "collect",
        ("door_commit", collected),
        "sync",
        "destroy",
        "close",
    ]
    assert door_state == collected
    assert editor_closed == [True]

    calls.clear()
    lifecycle.cancel_all()
    assert calls == []

    editor_closed[0] = False
    calls.clear()
    lifecycle.cancel_all()
    assert calls == [("finish", False), "sync", "destroy", "close"]
    assert editor_closed == [True]

    editor_closed[0] = False
    insert_mode[0] = True
    session.has_active_edit = True
    calls.clear()
    assert lifecycle.on_escape() == "break"
    assert calls == [("insert", False)]

    insert_mode[0] = False
    calls.clear()
    assert lifecycle.on_escape() == "break"
    assert calls == ["cancel_active"]

    session.has_active_edit = False
    calls.clear()
    assert lifecycle.on_escape() == "break"
    assert calls == [("finish", False), "sync", "destroy", "close"]
