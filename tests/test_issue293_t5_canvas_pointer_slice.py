from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from phase6_hole_editor_session import HoleEditorAction


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
HOLE_EDITOR = ROOT / "gui_modules" / "editors" / "hole_editor.py"
TARGET_CALLBACKS = {"on_canvas_down", "on_canvas_drag", "on_canvas_up"}


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


def _pointer_class():
    tree = ast.parse(HOLE_EDITOR.read_text(encoding="utf-8"))
    node = next(
        (
            item for item in tree.body
            if isinstance(item, ast.ClassDef) and item.name == "HoleEditorCanvasPointerActions"
        ),
        None,
    )
    assert node is not None, "T5 RED: HoleEditorCanvasPointerActions is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"HoleEditorAction": HoleEditorAction}
    exec(compile(module, str(HOLE_EDITOR), "exec"), namespace)
    return namespace["HoleEditorCanvasPointerActions"]


def test_canvas_pointer_callbacks_move_out_of_unified_root_into_editor_orchestration():
    nested = _unified_nested_names()
    assert not (nested & TARGET_CALLBACKS), (
        f"T5 RED: rooted canvas pointer callbacks remain: {sorted(nested & TARGET_CALLBACKS)}"
    )

    tree = ast.parse(HOLE_EDITOR.read_text(encoding="utf-8"))
    cls = next(
        (
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "HoleEditorCanvasPointerActions"
        ),
        None,
    )
    assert cls is not None, "T5 RED: HoleEditorCanvasPointerActions is missing"
    assert _span(cls) <= 120
    methods = {node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)}
    assert TARGET_CALLBACKS <= methods.keys()
    assert all(_span(methods[name]) <= 35 for name in TARGET_CALLBACKS)


def test_canvas_down_preserves_hit_select_insert_boundary_and_sync_semantics():
    cls = _pointer_class()
    calls: list[object] = []
    dragging = [False]
    insert_mode = [False]
    context = {
        "surface": "door-surface",
        "width": 100.0,
        "height": 80.0,
        "feature_list": [SimpleNamespace(marker="existing")],
    }

    class CanvasView:
        hit = 0

        def canvas_to_world(self, x, y):
            return (float(x), float(y))

        def hit_test(self, x, y):
            return self.hit

    class Session:
        selected_index = -1

        def __init__(self):
            self.actions = []

        def execute(self, action):
            self.actions.append(action)
            features = context["feature_list"]
            if action.kind == "insert":
                features.append(action.feature)
                self.selected_index = len(features) - 1
            elif action.kind == "replace_selected":
                features[self.selected_index] = action.feature

    canvas = CanvasView()
    session = Session()
    inside = [True]
    next_feature = [SimpleNamespace(marker="inserted")]

    actions = cls(
        hole_session=session,
        canvas_view=canvas,
        dragging=dragging,
        insert_mode=insert_mode,
        context_provider=lambda: context,
        select_feature=lambda idx: calls.append(("select", idx)),
        make_feature=lambda point: next_feature[0],
        feature_is_within_surface=lambda surface, feature, width, height: inside[0],
        move_feature_within_surface=lambda feature, point, width, height, surface: feature,
        begin_edit=lambda idx, marker: calls.append(("begin", idx, marker)),
        refresh_reference_fields=lambda: calls.append("reference"),
        redraw=lambda: calls.append("redraw"),
        sync_all=lambda: calls.append("sync"),
        warn_out_of_bounds=lambda: calls.append("warn"),
    )

    actions.on_canvas_down(SimpleNamespace(x=10, y=20))
    assert dragging == [True]
    assert calls == [("select", 0)]
    assert session.actions == []

    dragging[0] = False
    calls.clear()
    canvas.hit = None
    insert_mode[0] = True
    actions.on_canvas_down(SimpleNamespace(x=30, y=40))
    assert [action.kind for action in session.actions] == ["insert"]
    assert context["feature_list"][-1].marker == "inserted"
    assert calls == [("begin", 1, "new"), "sync"]

    session.actions.clear()
    calls.clear()
    inside[0] = False
    next_feature[0] = SimpleNamespace(marker="outside")
    actions.on_canvas_down(SimpleNamespace(x=50, y=60))
    assert session.actions == []
    assert calls == ["warn"]
    assert all(feature.marker != "outside" for feature in context["feature_list"])


def test_canvas_drag_and_up_use_live_context_and_preserve_refresh_order():
    cls = _pointer_class()
    calls: list[object] = []
    dragging = [True]
    insert_mode = [False]
    old = SimpleNamespace(marker="indicator-old")
    context = {
        "surface": "door-surface",
        "width": 100.0,
        "height": 80.0,
        "feature_list": [SimpleNamespace(marker="door-old")],
    }

    class CanvasView:
        def canvas_to_world(self, x, y):
            return (float(x), float(y))

        def hit_test(self, x, y):
            return None

    class Session:
        selected_index = 0

        def __init__(self):
            self.actions = []

        def execute(self, action):
            self.actions.append(action)
            if action.kind == "replace_selected":
                context["feature_list"][self.selected_index] = action.feature

    session = Session()

    def move(feature, point, width, height, surface):
        calls.append(("move", feature.marker, point, width, height, surface))
        return SimpleNamespace(marker="indicator-moved")

    actions = cls(
        hole_session=session,
        canvas_view=CanvasView(),
        dragging=dragging,
        insert_mode=insert_mode,
        context_provider=lambda: context,
        select_feature=lambda idx: None,
        make_feature=lambda point: None,
        feature_is_within_surface=lambda surface, feature, width, height: True,
        move_feature_within_surface=move,
        begin_edit=lambda idx, marker: None,
        refresh_reference_fields=lambda: calls.append("reference"),
        redraw=lambda: calls.append("redraw"),
        sync_all=lambda: calls.append("sync"),
        warn_out_of_bounds=lambda: None,
    )

    context.clear()
    context.update({
        "surface": "indicator-surface",
        "width": 44.0,
        "height": 33.0,
        "feature_list": [old],
    })
    actions.on_canvas_drag(SimpleNamespace(x=7, y=9))

    assert [action.kind for action in session.actions] == ["replace_selected"]
    assert context["feature_list"][0].marker == "indicator-moved"
    assert calls == [
        ("move", "indicator-old", (7.0, 9.0), 44.0, 33.0, "indicator-surface"),
        "reference",
        "redraw",
    ]

    calls.clear()
    actions.on_canvas_up(SimpleNamespace())
    assert dragging == [False]
    assert calls == ["sync"]

    calls.clear()
    actions.on_canvas_up(SimpleNamespace())
    assert calls == []
