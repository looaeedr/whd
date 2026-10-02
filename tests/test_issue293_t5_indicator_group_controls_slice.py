from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
VIEW = ROOT / "gui_modules" / "editors" / "hole_editor_view.py"
TARGET_CALLBACK = "rebuild_indicator_group_controls"


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def _unified_nested_names() -> set[str]:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost")
    unified = next(n for n in host.body if isinstance(n, ast.FunctionDef) and n.name == "_open_unified_hole_editor")
    return {n.name for n in ast.walk(unified) if isinstance(n, ast.FunctionDef) and n is not unified}


class _Widget:
    created: list["_Widget"] = []

    def __init__(self, kind, parent=None, **kwargs):
        self.kind = kind
        self.parent = parent
        self.kwargs = kwargs
        self.grid_calls = []
        self.bind_calls = []
        _Widget.created.append(self)

    def grid(self, **kwargs): self.grid_calls.append(kwargs)
    def bind(self, event, callback): self.bind_calls.append((event, callback))


class _FakeTk:
    W = "w"

    @staticmethod
    def Label(parent, **kwargs): return _Widget("Label", parent, **kwargs)


class _FakeTtk:
    @staticmethod
    def Combobox(parent, **kwargs): return _Widget("Combobox", parent, **kwargs)


class _Frame:
    def __init__(self):
        self.children = [self._Child(), self._Child()]

    class _Child:
        def __init__(self): self.destroyed = False
        def destroy(self): self.destroyed = True

    def winfo_children(self): return self.children


class _Var:
    def __init__(self, value): self.value = value
    def get(self): return self.value


def _controls_class():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorIndicatorGroupControls"), None)
    assert node is not None, "T5 RED: HoleEditorIndicatorGroupControls is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {"tk": _FakeTk, "ttk": _FakeTtk}
    exec(compile(module, str(VIEW), "exec"), ns)
    return ns["HoleEditorIndicatorGroupControls"]


def test_group_controls_callback_moves_out_of_unified_root():
    assert TARGET_CALLBACK not in _unified_nested_names(), "T5 RED: rebuild_indicator_group_controls remains rooted"
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorIndicatorGroupControls"), None)
    assert cls is not None, "T5 RED: HoleEditorIndicatorGroupControls is missing"
    assert _span(cls) <= 55
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    assert "rebuild" in methods
    assert _span(methods["rebuild"]) <= 25


def test_rebuild_preserves_layer_widgets_binding_and_single_redraw():
    cls = _controls_class()
    _Widget.created.clear()
    frame = _Frame()
    layer_var = _Var("2")
    group_vars = [_Var("3"), _Var("4"), _Var("5")]
    redraw_calls = []
    redraw = lambda *_args: redraw_calls.append("redraw")
    controls = cls(
        groups_frame=frame, layers_var=layer_var, group_vars=group_vars,
        request_redraw=redraw, panel_bg="#panel", muted_color="#muted",
    )
    assert controls.rebuild() is None
    assert all(child.destroyed for child in frame.children)
    labels = [w for w in _Widget.created if w.kind == "Label"]
    combos = [w for w in _Widget.created if w.kind == "Combobox"]
    assert [w.kwargs["text"] for w in labels] == ["1層", "2層"]
    assert all(w.kwargs["bg"] == "#panel" and w.kwargs["fg"] == "#muted" for w in labels)
    assert [w.kwargs["textvariable"] for w in combos] == group_vars[:2]
    assert all(w.kwargs["values"] == [str(v) for v in range(1, 9)] for w in combos)
    assert all(w.bind_calls == [("<<ComboboxSelected>>", redraw)] for w in combos)
    assert redraw_calls == ["redraw"]


def test_rebuild_invalid_layers_falls_back_to_one():
    cls = _controls_class()
    _Widget.created.clear()
    frame = _Frame()
    redraw_calls = []
    controls = cls(
        groups_frame=frame, layers_var=_Var("bad"), group_vars=[_Var("2")],
        request_redraw=lambda *_args: redraw_calls.append("redraw"),
        panel_bg="#panel", muted_color="#muted",
    )
    controls.rebuild()
    assert len([w for w in _Widget.created if w.kind == "Combobox"]) == 1
    assert redraw_calls == ["redraw"]
