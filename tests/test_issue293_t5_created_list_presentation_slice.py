from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
VIEW = ROOT / "gui_modules" / "editors" / "hole_editor_view.py"
TARGET_CALLBACKS = {"feature_display", "refresh_created"}


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def _unified_nested_names() -> set[str]:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost")
    unified = next(n for n in host.body if isinstance(n, ast.FunctionDef) and n.name == "_open_unified_hole_editor")
    return {n.name for n in ast.walk(unified) if isinstance(n, ast.FunctionDef) and n is not unified}


def _presentation_class():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorCreatedListPresentation"), None)
    assert node is not None, "T5 RED: HoleEditorCreatedListPresentation is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)

    class CircleFeature:
        pass

    class RectFeature:
        pass

    ns = {"CircleFeature": CircleFeature, "RectFeature": RectFeature}
    exec(compile(module, str(VIEW), "exec"), ns)
    return ns["HoleEditorCreatedListPresentation"], CircleFeature, RectFeature


def test_created_list_presentation_callbacks_move_out_of_unified_root():
    nested = _unified_nested_names()
    assert not (nested & TARGET_CALLBACKS), f"T5 RED: rooted created-list presentation callbacks remain: {sorted(nested & TARGET_CALLBACKS)}"
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorCreatedListPresentation"), None)
    assert cls is not None, "T5 RED: HoleEditorCreatedListPresentation is missing"
    assert _span(cls) <= 80
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    assert TARGET_CALLBACKS <= methods.keys()
    assert all(_span(methods[name]) <= 30 for name in TARGET_CALLBACKS)


def test_feature_display_preserves_shape_and_blind_hole_labels():
    cls, CircleFeature, RectFeature = _presentation_class()

    circle = CircleFeature(); circle.diameter = 12.5; circle.layer = "CUTTING"
    rect = RectFeature(); rect.width = 20.0; rect.height = 15.0; rect.layer = "BLIND_HOLE"
    profile = SimpleNamespace(source_type="DB9", layer="CUTTING")

    presentation = cls(
        created_list=None,
        feature_list_provider=lambda: [],
        selected_index_provider=lambda: -1,
        end_token="end",
    )

    assert presentation.feature_display(circle, 0) == "01  Ø12.5           "
    assert presentation.feature_display(rect, 1) == "02  20×15           盲孔"
    assert presentation.feature_display(profile, 2) == "03  DB9             "


def test_refresh_created_uses_live_features_and_selection_each_call():
    cls, CircleFeature, RectFeature = _presentation_class()
    active_features = [[]]
    selected = [-1]

    class FakeList:
        def __init__(self): self.calls = []
        def delete(self, start, end): self.calls.append(("delete", start, end))
        def insert(self, end, text): self.calls.append(("insert", end, text))
        def selection_set(self, idx): self.calls.append(("select", idx))
        def see(self, idx): self.calls.append(("see", idx))

    widget = FakeList()
    presentation = cls(
        created_list=widget,
        feature_list_provider=lambda: active_features[0],
        selected_index_provider=lambda: selected[0],
        end_token="END",
    )

    c = CircleFeature(); c.diameter = 6.4; c.layer = "CUTTING"
    active_features[0] = [c]; selected[0] = 0
    presentation.refresh_created()
    assert widget.calls == [
        ("delete", 0, "END"),
        ("insert", "END", "01  Ø6.4            "),
        ("select", 0),
        ("see", 0),
    ]

    widget.calls.clear()
    r = RectFeature(); r.width = 8; r.height = 9; r.layer = "BLIND_HOLE"
    active_features[0] = [r]; selected[0] = -1
    presentation.refresh_created()
    assert widget.calls == [
        ("delete", 0, "END"),
        ("insert", "END", "01  8×9             盲孔"),
    ]
