from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
VIEW = ROOT / "gui_modules" / "editors" / "hole_editor_view.py"
TARGET_CALLBACKS = {"active_reference_guide", "refresh_reference_fields"}


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def _unified_nested_names() -> set[str]:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost")
    unified = next(n for n in host.body if isinstance(n, ast.FunctionDef) and n.name == "_open_unified_hole_editor")
    return {n.name for n in ast.walk(unified) if isinstance(n, ast.FunctionDef) and n is not unified}


class _FakeCircle:
    pass


class _FakeTk:
    NORMAL = "normal"
    DISABLED = "disabled"


def _presentation_class():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorReferencePresentation"), None)
    assert node is not None, "T5 RED: HoleEditorReferencePresentation is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns = {"tk": _FakeTk, "CircleFeature": _FakeCircle}
    exec(compile(module, str(VIEW), "exec"), ns)
    return ns["HoleEditorReferencePresentation"]


class _Var:
    def __init__(self, value=None):
        self.value = value
    def set(self, value):
        self.value = value


class _Widget:
    def __init__(self):
        self.config = {}
    def configure(self, **kwargs):
        self.config.update(kwargs)


def _make_presentation(*, selection_provider, context_provider, distances_fn, enclosure_fn=None):
    cls = _presentation_class()
    labels = {key: _Var() for key in ("x_edge", "x_neighbor", "y_edge", "y_neighbor")}
    values = {key: _Var("stale") for key in ("x_edge", "x_neighbor", "y_edge", "y_neighbor")}
    entries = {("x", "neighbor"): _Widget(), ("y", "neighbor"): _Widget()}
    button = _Widget()
    last_distances = ["stale"]
    suppress = [False]
    calls = []

    def anchor_fn(feature):
        calls.append(("anchor", feature))
        return "anchor"

    presentation = cls(
        selection_provider=selection_provider,
        context_provider=context_provider,
        feature_reference_anchor=anchor_fn,
        reference_distances=distances_fn,
        door_enclosure_reference_guide=(enclosure_fn or (lambda *args, **kwargs: "enclosure")),
        door_frame_edges_factory=lambda: "default-edges",
        round_settings_btn=button,
        labels=labels,
        values=values,
        ref_entries=entries,
        side_labels={"left": "左", "right": "右", "top": "上", "bottom": "下"},
        last_distances=last_distances,
        suppress_entry_events=suppress,
    )
    return presentation, labels, values, entries, button, last_distances, suppress, calls


def test_reference_presentation_callbacks_move_out_of_unified_root_into_view():
    nested = _unified_nested_names()
    assert not (nested & TARGET_CALLBACKS), f"T5 RED: rooted reference-presentation callbacks remain: {sorted(nested & TARGET_CALLBACKS)}"
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorReferencePresentation"), None)
    assert cls is not None, "T5 RED: HoleEditorReferencePresentation is missing"
    assert _span(cls) <= 130
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    assert {"active_reference_guide", "refresh_reference_fields"} <= methods.keys()
    assert _span(methods["active_reference_guide"]) <= 30
    assert _span(methods["refresh_reference_fields"]) <= 55


def test_active_reference_guide_uses_live_context_and_delegated_enclosure_authority():
    feature = _FakeCircle()
    context = [{
        "reference_guide": "door-guide",
        "active_part_key": "door",
        "indicator_box_dist_enabled": True,
        "door_frame_width": 11.0,
        "door_thickness": 2.0,
        "door_gap_w": 3.0,
        "door_gap_h": 4.0,
        "door_frame_edges": None,
        "surface": "surface",
        "width": 100.0,
        "height": 80.0,
    }]
    enclosure_calls = []

    def enclosure_fn(guide, edges, **kwargs):
        enclosure_calls.append((guide, edges, kwargs))
        return "enclosure-guide"

    presentation, *_ = _make_presentation(
        selection_provider=lambda: (0, [feature]),
        context_provider=lambda: context[0],
        distances_fn=lambda *args, **kwargs: None,
        enclosure_fn=enclosure_fn,
    )
    assert presentation.active_reference_guide() == "enclosure-guide"
    assert enclosure_calls == [("door-guide", "default-edges", {
        "frame_width": 11.0, "thickness": 2.0, "gap_w": 3.0, "gap_h": 4.0,
    })]

    context[0] = {
        **context[0],
        "reference_guide": "indicator-guide",
        "active_part_key": "indicator_box",
    }
    assert presentation.active_reference_guide() == "indicator-guide"
    assert len(enclosure_calls) == 1


def test_refresh_reference_fields_uses_live_selection_context_and_updates_controls():
    circle = _FakeCircle()
    other = object()
    current_features = [[circle]]
    selected = [0]
    current_context = [{
        "reference_guide": "guide-a",
        "active_part_key": "indicator_box",
        "indicator_box_dist_enabled": False,
        "door_frame_width": None,
        "door_thickness": None,
        "door_gap_w": None,
        "door_gap_h": None,
        "door_frame_edges": None,
        "surface": "surface-a",
        "width": 100.0,
        "height": 80.0,
    }]
    distance_calls = []
    d = SimpleNamespace(
        x_side="left", y_side="top",
        x_edge_distance=12.345, y_edge_distance=23.456,
        x_neighbor_distance=4.5, y_neighbor_distance=None,
        x_neighbor_index=2, y_neighbor_index=None,
    )

    def distances_fn(surface, features, idx, anchor, width, height, *, reference_guide):
        distance_calls.append((surface, features, idx, anchor, width, height, reference_guide))
        return d

    presentation, labels, values, entries, button, last_distances, suppress, calls = _make_presentation(
        selection_provider=lambda: (selected[0], current_features[0]),
        context_provider=lambda: current_context[0],
        distances_fn=distances_fn,
    )
    presentation.refresh_reference_fields()
    assert suppress == [False]
    assert calls == [("anchor", circle)]
    assert distance_calls == [("surface-a", [circle], 0, "anchor", 100.0, 80.0, "guide-a")]
    assert last_distances == [d]
    assert labels["x_edge"].value == "X 到左邊框"
    assert labels["x_neighbor"].value == "X 到左側鄰近孔"
    assert labels["y_edge"].value == "Y 到上邊框"
    assert labels["y_neighbor"].value == "Y 到上側鄰近孔"
    assert values["x_edge"].value == "12.35"
    assert values["y_edge"].value == "23.46"
    assert values["x_neighbor"].value == "4.50"
    assert values["y_neighbor"].value == ""
    assert button.config["state"] == "normal"
    assert entries[("x", "neighbor")].config["state"] == "normal"
    assert entries[("y", "neighbor")].config["state"] == "disabled"

    current_features[0] = [other]
    current_context[0] = {**current_context[0], "surface": "surface-b", "width": 200.0, "height": 160.0, "reference_guide": "guide-b"}
    selected[0] = -1
    presentation.refresh_reference_fields()
    assert last_distances == [None]
    assert all(var.value == "" for var in values.values())
    assert button.config["state"] == "disabled"
    assert suppress == [False]
