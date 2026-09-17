from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
VIEW = ROOT / "gui_modules" / "editors" / "hole_editor_view.py"
TARGET_CALLBACKS = {"small_row", "add_group_entry"}


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def _unified_nested_names() -> set[str]:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost")
    unified = next(n for n in host.body if isinstance(n, ast.FunctionDef) and n.name == "_open_unified_hole_editor")
    return {n.name for n in ast.walk(unified) if isinstance(n, ast.FunctionDef) and n is not unified}


class _Widget:
    created: list[tuple] = []

    def __init__(self, kind, parent=None, **kwargs):
        self.kind = kind
        self.parent = parent
        self.kwargs = kwargs
        self.pack_calls = []
        _Widget.created.append((kind, parent, kwargs, self))

    def pack(self, **kwargs):
        self.pack_calls.append(kwargs)
        return None


class _FakeTk:
    X = "x"
    LEFT = "left"
    RIGHT = "right"
    W = "w"

    @staticmethod
    def Frame(parent, **kwargs): return _Widget("Frame", parent, **kwargs)
    @staticmethod
    def Label(parent, **kwargs): return _Widget("Label", parent, **kwargs)
    @staticmethod
    def Entry(parent, **kwargs): return _Widget("Entry", parent, **kwargs)


def _builders_class():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorFormRowBuilders"), None)
    assert node is not None, "T5 RED: HoleEditorFormRowBuilders is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {"tk": _FakeTk}
    exec(compile(module, str(VIEW), "exec"), ns)
    return ns["HoleEditorFormRowBuilders"]


def test_form_row_callbacks_move_out_of_unified_root_into_view():
    nested = _unified_nested_names()
    assert not (nested & TARGET_CALLBACKS), f"T5 RED: rooted form-row callbacks remain: {sorted(nested & TARGET_CALLBACKS)}"
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorFormRowBuilders"), None)
    assert cls is not None, "T5 RED: HoleEditorFormRowBuilders is missing"
    assert _span(cls) <= 90
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    assert TARGET_CALLBACKS <= methods.keys()
    assert all(_span(methods[name]) <= 25 for name in TARGET_CALLBACKS)


def test_small_row_preserves_parent_styles_and_entry_layout():
    cls = _builders_class()
    _Widget.created.clear()
    registry = {}
    parent = object()
    variable = object()
    builders = cls(
        panel_bg="#panel", text_color="#text", normal_font="normal",
        entry_font="entry", ref_entries_provider=lambda: registry,
    )
    assert builders.small_row(parent, "直徑", variable) is None
    frame = next(item[3] for item in _Widget.created if item[0] == "Frame")
    label = next(item[3] for item in _Widget.created if item[0] == "Label")
    entry = next(item[3] for item in _Widget.created if item[0] == "Entry")
    assert frame.parent is parent and frame.kwargs == {"bg": "#panel"}
    assert frame.pack_calls == [{"fill": "x", "padx": 6, "pady": 2}]
    assert label.parent is frame
    assert label.kwargs == {"text": "直徑", "bg": "#panel", "fg": "#text", "width": 7, "anchor": "w", "font": "normal"}
    assert label.pack_calls == [{"side": "left"}]
    assert entry.parent is frame
    assert entry.kwargs == {"textvariable": variable, "font": ("Consolas", 13), "width": 9}
    assert entry.pack_calls == [{"side": "left", "fill": "x", "expand": True}]


def test_reference_group_row_uses_live_registry_and_returns_entry():
    cls = _builders_class()
    _Widget.created.clear()
    registry_a = {}
    registry_b = {}
    active = [registry_a]
    group = object(); label_var = object(); value_var = object()
    builders = cls(
        panel_bg="#panel", text_color="#text", normal_font="normal",
        entry_font="entry-font", ref_entries_provider=lambda: active[0],
    )
    active[0] = registry_b
    ent = builders.add_group_entry(group, label_var, value_var, "x", "edge")
    assert registry_a == {}
    assert registry_b[("x", "edge")] is ent
    frame = next(item[3] for item in _Widget.created if item[0] == "Frame")
    label = next(item[3] for item in _Widget.created if item[0] == "Label")
    assert frame.parent is group and frame.kwargs == {"bg": "#24242c"}
    assert frame.pack_calls == [{"fill": "x", "padx": 5, "pady": 2}]
    assert label.kwargs == {"textvariable": label_var, "bg": "#24242c", "fg": "#ffd60a", "font": ("Microsoft JhengHei", 10, "bold"), "width": 13, "anchor": "w"}
    assert ent.kwargs == {"textvariable": value_var, "font": "entry-font", "justify": "right", "width": 8}
    assert ent.pack_calls == [{"side": "left", "padx": (4, 0), "ipady": 2}]
