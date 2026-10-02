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
    current = {
        "mode": None,
        "layers": None,
        "groups": [],
        "x": None,
        "y": None,
        "box": None,
    }
    normalized = []

    def normalize(state):
        normalized.append(state)
        return {"normalized": state}

    collector = cls(
        mode_var_provider=lambda: current["mode"],
        layers_var_provider=lambda: current["layers"],
        group_vars_provider=lambda: current["groups"],
        offset_x_var_provider=lambda: current["x"],
        offset_y_var_provider=lambda: current["y"],
        box_dist_var_provider=lambda: current["box"],
        normalize_state=normalize,
    )
    assert collector.collect() is None
    assert normalized == []

    current.update({
        "mode": _Var("indicator_box"),
        "layers": _Var("2"),
        "groups": [_Var("3"), _Var("bad")],
        "x": _Var("12.5"),
        "y": _Var("-4"),
        "box": _Var(1),
    })
    result = collector.collect()
    expected = {
        "mode": "indicator_box",
        "layers": 2,
        "groups": [3, 2, 2, 2, 2, 2],
        "offset_x": 12.5,
        "offset_y": -4.0,
        "is_box_dist": True,
    }
    assert normalized == [expected]
    assert result == {"normalized": expected}


def test_collector_preserves_fallbacks_and_six_group_limit():
    cls = _collector_class()
    captured = []
    collector = cls(
        mode_var_provider=lambda: _Var("indicator"),
        layers_var_provider=lambda: _Var("bad"),
        group_vars_provider=lambda: [_Var("0"), _Var("4"), _Var("5"), _Var("6"), _Var("7"), _Var("8"), _Var("9")],
        offset_x_var_provider=lambda: _Var("bad"),
        offset_y_var_provider=lambda: _Var("bad"),
        box_dist_var_provider=lambda: _Var(False),
        normalize_state=lambda state: captured.append(state) or state,
    )
    result = collector.collect()
    assert result["layers"] == 1
    assert result["groups"] == [1, 4, 5, 6, 7, 8]
    assert result["offset_x"] == 0.0
    assert result["offset_y"] == 0.0
    assert result["is_box_dist"] is False
    assert captured == [result]
