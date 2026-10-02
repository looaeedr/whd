from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
VIEW = ROOT / "gui_modules" / "editors" / "hole_editor_view.py"
TARGET_CALLBACKS = {"on_catalog_select", "set_insert_mode", "on_catalog_double_click"}


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


def _controls_class():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    node = next(
        (item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == "HoleEditorCatalogControls"),
        None,
    )
    assert node is not None, "T5 RED: HoleEditorCatalogControls is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, object] = {}
    exec(compile(module, str(VIEW), "exec"), namespace)
    return namespace["HoleEditorCatalogControls"]


def test_catalog_controls_move_out_of_unified_root_into_view():
    nested = _unified_nested_names()
    assert not (nested & TARGET_CALLBACKS), f"T5 RED: rooted catalog callbacks remain: {sorted(nested & TARGET_CALLBACKS)}"

    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    cls = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "HoleEditorCatalogControls"),
        None,
    )
    assert cls is not None, "T5 RED: HoleEditorCatalogControls is missing"
    assert _span(cls) <= 100
    methods = {node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)}
    assert TARGET_CALLBACKS <= methods.keys()
    assert all(_span(methods[name]) <= 30 for name in TARGET_CALLBACKS)


def test_catalog_controls_preserve_selection_insert_and_double_click_behavior():
    cls = _controls_class()
    calls: list[object] = []

    class FakeVar:
        def __init__(self, value=""):
            self.value = value

        def get(self):
            return self.value

        def set(self, value):
            self.value = value
            calls.append(("selected", value))

    class FakeList:
        def __init__(self, values, selection=()):
            self.values = list(values)
            self.selection = list(selection)
            self.active = None

        def curselection(self):
            return tuple(self.selection)

        def get(self, idx):
            return self.values[idx]

        def selection_clear(self, start, end):
            calls.append(("clear", id(self), start, end))
            self.selection = []

        def nearest(self, y):
            calls.append(("nearest", id(self), y))
            return min(max(int(y), 0), len(self.values) - 1)

        def size(self):
            return len(self.values)

        def selection_set(self, idx):
            calls.append(("selection_set", id(self), idx))
            self.selection = [idx]

        def activate(self, idx):
            calls.append(("activate", id(self), idx))
            self.active = idx

    class FakeButton:
        def configure(self, **kwargs):
            calls.append(("button", kwargs))

    class FakeCanvas:
        def focus_set(self):
            calls.append("focus")

    catalog = FakeList(["A", "＋ 自訂圓孔"], selection=[0])
    pipe = FakeList(["P"], selection=[0])
    selected = FakeVar()
    insert_mode = [False]
    controls = cls(
        catalog_list=catalog,
        pipe_catalog_list=pipe,
        selected_catalog_text=selected,
        insert_mode=insert_mode,
        insert_btn=FakeButton(),
        canvas=FakeCanvas(),
        redraw=lambda: calls.append("redraw"),
    )

    controls.on_catalog_select(source_list=catalog)
    assert selected.get() == "A"
    assert pipe.selection == []

    calls.clear()
    controls.set_insert_mode()
    assert insert_mode == [True]
    assert calls == [
        ("button", {"text": "停止插入", "bg": "#ff9f0a"}),
        "redraw",
    ]

    calls.clear()
    event = SimpleNamespace(widget=catalog, y=1)
    assert controls.on_catalog_double_click(event) == "break"
    assert selected.get() == "＋ 自訂圓孔"
    assert insert_mode == [True]
    assert "focus" not in calls

    calls.clear()
    event = SimpleNamespace(widget=catalog, y=0)
    assert controls.on_catalog_double_click(event) == "break"
    assert selected.get() == "A"
    assert insert_mode == [True]
    assert ("button", {"text": "停止插入", "bg": "#ff9f0a"}) in calls
    assert calls[-1] == "focus"
