from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from phase6_hole_editor_session import HoleEditorAction


ROOT = Path(__file__).resolve().parents[1]
HOLE_EDITOR = ROOT / "gui_modules" / "editors" / "hole_editor.py"
TARGET_CLASSES = {"HoleEditorTransientActions", "HoleEditorCreatedListActions"}


def _classes():
    tree = ast.parse(HOLE_EDITOR.read_text(encoding="utf-8"))
    nodes = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name in TARGET_CLASSES
    }
    assert TARGET_CLASSES <= nodes.keys()
    module = ast.Module(body=[nodes[name] for name in sorted(TARGET_CLASSES)], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"HoleEditorAction": HoleEditorAction}
    exec(compile(module, str(HOLE_EDITOR), "exec"), namespace)
    return namespace


def test_extracted_actions_use_live_feature_list_provider_not_initial_list_snapshot():
    tree = ast.parse(HOLE_EDITOR.read_text(encoding="utf-8"))
    classes = {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name in TARGET_CLASSES
    }
    for name in TARGET_CLASSES:
        init = next(node for node in classes[name].body if isinstance(node, ast.FunctionDef) and node.name == "__init__")
        args = {arg.arg for arg in init.args.args + init.args.kwonlyargs}
        assert "feature_list_provider" in args, f"T5 RED: {name} still snapshots feature_list"


def test_context_switch_rebinding_is_visible_to_transient_and_created_list_actions():
    namespace = _classes()
    transient_cls = namespace["HoleEditorTransientActions"]
    created_cls = namespace["HoleEditorCreatedListActions"]

    class FakeSession:
        def __init__(self):
            self.selected_index = 0
            self.actions = []

        def execute(self, action):
            self.actions.append(action)
            if action.kind == "select":
                self.selected_index = int(action.index)

    class FakeVar:
        def __init__(self):
            self.values = []

        def set(self, value):
            self.values.append(value)

    class FakeList:
        def curselection(self):
            return (0,)

    door_features = [SimpleNamespace(rotation_deg=10, layer="CUTTING", marker="door")]
    indicator_features = [SimpleNamespace(rotation_deg=90, layer="BLIND_HOLE", marker="indicator")]
    active_features = [door_features]
    session = FakeSession()
    rotation = FakeVar()
    no_op = lambda: None

    transient = transient_cls(
        hole_session=session,
        feature_list_provider=lambda: active_features[0],
        var_rotation=rotation,
        refresh_created=no_op,
        refresh_reference_fields=no_op,
        redraw=no_op,
        sync_all=no_op,
    )
    transient.begin_edit(0)
    assert rotation.values[-1] == "10°"

    active_features[0] = indicator_features
    transient.begin_edit(0)
    assert rotation.values[-1] == "90°"

    transformed = []
    created = created_cls(
        hole_session=session,
        feature_list_provider=lambda: active_features[0],
        created_list=FakeList(),
        select_feature=lambda idx: None,
        feature_with_process=lambda feature, process: transformed.append((feature, process)) or feature,
        refresh_created=no_op,
        refresh_reference_fields=no_op,
        redraw=no_op,
        sync_all=no_op,
    )
    created.toggle_created_process()
    assert transformed[-1][0] is indicator_features[0]
    assert transformed[-1][1] == "CUTTING"
