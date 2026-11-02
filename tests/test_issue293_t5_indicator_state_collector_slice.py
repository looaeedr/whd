from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
VIEW = ROOT / "gui_modules" / "editors" / "hole_editor_view.py"
TARGET_CALLBACK = "collect_indicator_state"


def _span(node: ast.AST) -> int:
    return int(node.end_lineno) - int(node.lineno) + 1


def _unified_nested_names() -> set[str]:
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Phase6ApplicationHost")
    unified = next(n for n in host.body if isinstance(n, ast.FunctionDef) and n.name == "_open_unified_hole_editor")
    return {n.name for n in ast.walk(unified) if isinstance(n, ast.FunctionDef) and n is not unified}


class _Var:
    def __init__(self, value): self.value = value
    def get(self): return self.value


def _collector_class():
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    node = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorIndicatorStateCollector"), None)
    assert node is not None, "T5 RED: HoleEditorIndicatorStateCollector is missing"
    module = ast.Module(body=[node], type_ignores=[])
    ast.fix_missing_locations(module)
    ns: dict[str, object] = {}
    exec(compile(module, str(VIEW), "exec"), ns)
    return ns["HoleEditorIndicatorStateCollector"]


def test_indicator_state_callback_moves_out_of_unified_root():
    assert TARGET_CALLBACK not in _unified_nested_names(), "T5 RED: collect_indicator_state remains rooted"
    tree = ast.parse(VIEW.read_text(encoding="utf-8"))
    cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "HoleEditorIndicatorStateCollector"), None)
    assert cls is not None, "T5 RED: HoleEditorIndicatorStateCollector is missing"
    assert _span(cls) <= 70
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    assert "collect" in methods
    assert _span(methods["collect"]) <= 40


def test_collector_uses_late_bound_var_providers_and_delegates_normalization():
    cls = _collector_class()
    current = {"mode": None, "layers": None, "groups": [],
               "x": None, "y": None, "box": None}
    normalized = []
    collector = cls(
        mode_var_provider=lambda: current["mode"],
        layers_var_provider=lambda: current["layers"],
        group_vars_provider=lambda: current["groups"],
        offset_x_var_provider=lambda: current["x"],
        offset_y_var_provider=lambda: current["y"],
        box_dist_var_provider=lambda: current["box"],
        normalize_state=lambda raw: normalized.append(raw) or {"normalized": raw},
    )
    assert collector.collect() is None
    current.update({
        "mode": _Var("indicator_box"), "layers": _Var("2"),
        "groups": [_Var("3"), _Var("bad")],
        "x": _Var("12.5"), "y": _Var("-4"), "box": _Var(1),
    })
    raw = collector.collect()["normalized"]
    assert raw == {
        "mode": "indicator_box", "layers": "2", "groups": ["3", "bad"],
        "offset_x": "12.5", "offset_y": "-4", "is_box_dist": 1,
    }
    assert normalized == [raw]


def test_collector_does_not_read_inactive_controls_or_fabricate_physical_defaults():
    cls = _collector_class()
    observed = []
    collector = cls(
        mode_var_provider=lambda: _Var("none"),
        layers_var_provider=lambda: (_ for _ in ()).throw(AssertionError("inactive layers")),
        group_vars_provider=lambda: (_ for _ in ()).throw(AssertionError("inactive groups")),
        offset_x_var_provider=lambda: (_ for _ in ()).throw(AssertionError("inactive x")),
        offset_y_var_provider=lambda: (_ for _ in ()).throw(AssertionError("inactive y")),
        box_dist_var_provider=lambda: (_ for _ in ()).throw(AssertionError("inactive flag")),
        normalize_state=lambda state: observed.append(state) or state,
    )
    assert collector.collect() == {"mode": "none"}
    assert observed == [{"mode": "none"}]
