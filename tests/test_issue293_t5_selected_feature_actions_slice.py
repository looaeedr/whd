from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

from phase6_hole_editor_session import HoleEditorAction

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
HOLE_EDITOR = ROOT / "gui_modules" / "editors" / "hole_editor.py"
TARGET_CALLBACKS = {"on_canvas_right", "rotate_selected"}


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def _unified_nested_names() -> set[str]:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost")
    unified = next(n for n in host.body if isinstance(n, ast.FunctionDef) and n.name == "_open_unified_hole_editor")
    return {n.name for n in ast.walk(unified) if isinstance(n, ast.FunctionDef) and n is not unified}


def _selected_class():
    tree = ast.parse(HOLE_EDITOR.read_text(encoding="utf-8"))
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorSelectedFeatureActions"), None)
    assert node is not None, "T5 RED: HoleEditorSelectedFeatureActions is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {"HoleEditorAction": HoleEditorAction}
    exec(compile(module, str(HOLE_EDITOR), "exec"), ns)
    return ns["HoleEditorSelectedFeatureActions"]


def test_selected_feature_callbacks_move_out_of_unified_root():
    nested = _unified_nested_names()
    assert not (nested & TARGET_CALLBACKS), f"T5 RED: rooted selected-feature callbacks remain: {sorted(nested & TARGET_CALLBACKS)}"
    tree = ast.parse(HOLE_EDITOR.read_text(encoding="utf-8"))
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorSelectedFeatureActions"), None)
    assert cls is not None, "T5 RED: HoleEditorSelectedFeatureActions is missing"
    assert _span(cls) <= 120
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    assert TARGET_CALLBACKS <= methods.keys()
    assert all(_span(methods[name]) <= 35 for name in TARGET_CALLBACKS)


def test_right_click_uses_live_feature_context_and_preserves_anchor_menu():
    cls = _selected_class()
    calls: list[object] = []
    context = {"feature_list": [SimpleNamespace(anchor="LEFT", marker="door")], "surface": "door", "width": 100.0, "height": 80.0}

    class CanvasView:
        hit = None
        def hit_test(self, x, y): return self.hit

    class Menu:
        def __init__(self): self.commands = []; self.separators = 0; self.popup = None
        def add_command(self, **kwargs): self.commands.append(kwargs)
        def add_separator(self): self.separators += 1
        def tk_popup(self, x, y): self.popup = (x, y)

    canvas = CanvasView(); menus: list[Menu] = []
    def menu_factory():
        menu = Menu(); menus.append(menu); return menu

    actions = cls(
        hole_session=SimpleNamespace(selected_index=0, execute=lambda action: None),
        canvas_view=canvas,
        context_provider=lambda: context,
        select_feature=lambda idx: calls.append(("select", idx)),
        menu_factory=menu_factory,
        reference_anchor_labels={"LEFT": "左", "RIGHT": "右"},
        feature_reference_anchor=lambda feature: feature.anchor,
        set_reference_anchor=lambda anchor: calls.append(("anchor", anchor)),
        var_rotation=SimpleNamespace(set=lambda value: calls.append(("rotation-var", value))),
        rotate_feature=lambda feature, rotation: feature,
        feature_is_within_surface=lambda *args: True,
        warn_rotation_out_of_bounds=lambda: calls.append("warn"),
        refresh_reference_fields=lambda: calls.append("reference"),
        redraw=lambda: calls.append("redraw"),
        sync_all=lambda: calls.append("sync"),
    )

    actions.on_canvas_right(SimpleNamespace(x=1, y=2, x_root=10, y_root=20))
    assert calls == [] and menus == []

    canvas.hit = 0
    context.clear(); context.update({"feature_list": [SimpleNamespace(anchor="RIGHT", marker="indicator")], "surface": "indicator", "width": 44.0, "height": 33.0})
    actions.on_canvas_right(SimpleNamespace(x=3, y=4, x_root=30, y_root=40))
    assert calls == [("select", 0)]
    assert len(menus) == 1
    menu = menus[0]
    assert menu.commands[0]["label"] == "十字基準線" and menu.commands[0]["state"] == "disabled"
    assert menu.separators == 1
    assert [cmd["label"] for cmd in menu.commands[1:]] == ["   左", "✓ 右"]
    assert menu.popup == (30, 40)
    menu.commands[1]["command"]()
    assert calls[-1] == ("anchor", "LEFT")


def test_rotate_selected_preserves_normalization_boundary_and_refresh_order_with_live_context():
    cls = _selected_class()
    calls: list[object] = []
    context = {"feature_list": [SimpleNamespace(rotation_deg=0, marker="door")], "surface": "door", "width": 100.0, "height": 80.0}

    class Session:
        selected_index = 0
        def __init__(self): self.actions = []
        def execute(self, action):
            self.actions.append(action)
            if action.kind == "replace_selected": context["feature_list"][self.selected_index] = action.feature
    session = Session(); inside = [True]

    def rotate(feature, rotation):
        calls.append(("rotate", feature.marker, rotation))
        return SimpleNamespace(rotation_deg=rotation, marker=feature.marker)

    def within(surface, feature, width, height):
        calls.append(("within", surface, feature.marker, feature.rotation_deg, width, height))
        return inside[0]

    actions = cls(
        hole_session=session,
        canvas_view=SimpleNamespace(hit_test=lambda x, y: None),
        context_provider=lambda: context,
        select_feature=lambda idx: None,
        menu_factory=lambda: None,
        reference_anchor_labels={},
        feature_reference_anchor=lambda feature: None,
        set_reference_anchor=lambda anchor: None,
        var_rotation=SimpleNamespace(set=lambda value: calls.append(("rotation-var", value))),
        rotate_feature=rotate,
        feature_is_within_surface=within,
        warn_rotation_out_of_bounds=lambda: calls.append("warn"),
        refresh_reference_fields=lambda: calls.append("reference"),
        redraw=lambda: calls.append("redraw"),
        sync_all=lambda: calls.append("sync"),
    )

    context.clear(); context.update({"feature_list": [SimpleNamespace(rotation_deg=90, marker="indicator")], "surface": "indicator", "width": 44.0, "height": 33.0})
    actions.rotate_selected(360)
    assert [action.kind for action in session.actions] == ["replace_selected"]
    assert context["feature_list"][0].rotation_deg == 0
    assert calls == [
        ("rotation-var", "360°"),
        ("rotate", "indicator", 0),
        ("within", "indicator", "indicator", 0, 44.0, 33.0),
        "reference", "redraw", "sync",
    ]

    session.actions.clear(); calls.clear(); inside[0] = False
    actions.rotate_selected(90)
    assert session.actions == []
    assert calls == [
        ("rotation-var", "90°"),
        ("rotate", "indicator", 90),
        ("within", "indicator", "indicator", 90, 44.0, 33.0),
        "warn",
    ]
