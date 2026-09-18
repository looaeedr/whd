from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
OWNER = ROOT / "gui_modules" / "project" / "export_actions.py"

ROOT_METHODS = (
    "export_multi_door_layout_dxfs",
    "export_multi_door_indicator_box_parts",
    "export_selected_dxf",
    "_single_door_indicator_state_snapshot",
    "_apply_single_door_indicator_state",
    "_apply_multi_door_indicator_state",
)


class Var:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


def _host_methods():
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    return {
        node.name: node
        for node in host.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _loc(node):
    return node.end_lineno - node.lineno + 1


def test_project_export_owner_exists_and_root_is_thin():
    assert OWNER.is_file()
    funcs = {
        node.name: node
        for node in ast.parse(OWNER.read_text(encoding="utf-8")).body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for name in ROOT_METHODS:
        assert name in funcs, f"project/export owner missing: {name}"
        assert _loc(funcs[name]) <= 150, f"{name} exceeds 150 lines"

    for helper in (
        "_selected_export_flags",
        "_validate_selected_indicator_exports",
        "_export_selected_parts",
    ):
        assert helper in funcs, f"split export helper missing: {helper}"
        assert _loc(funcs[helper]) <= 150

    methods = _host_methods()
    thick = {
        name: _loc(methods[name])
        for name in ROOT_METHODS
        if name in methods and _loc(methods[name]) > 5
    }
    assert not thick, f"project/export implementation still owned by gui.py: {thick}"


def test_single_door_indicator_state_snapshot_contract():
    import gui

    host = object.__new__(gui.Phase6ApplicationHost)
    host.is_indicator_box_var = Var(False)
    host.is_door_indicator_var = Var(True)
    host.indicator_l_var = Var("1")
    host.indicator_layer_g_vars = [Var("2") for _ in range(6)]
    host.door_indicator_l_var = Var("3")
    host.door_indicator_layer_g_vars = [Var(v) for v in ("2","3","4","5","6","7")]
    host.door_indicator_offset_x = 12.5
    host.door_indicator_offset_y = -3.0
    host.is_box_dist_var = Var(True)
    host._normalize_door_indicator_state = lambda state: state

    state = host._single_door_indicator_state_snapshot()
    assert state["mode"] == "indicator"
    assert state["layers"] == 3
    assert state["groups"][:3] == [2, 3, 4]
    assert state["offset_x"] == 12.5
    assert state["offset_y"] == -3.0
    assert state["is_box_dist"] is True


def test_project_export_module_does_not_own_project_or_manufacturing_truth():
    if not OWNER.is_file():
        pytest.skip("RED: project/export owner not created yet")
    text = OWNER.read_text(encoding="utf-8")
    assert "Phase6ProjectController(" not in text
    assert "Phase6WorkspaceController(" not in text
    assert "PROJECT_SCHEMA =" not in text
    assert "write_project(" not in text
    assert "import gui" not in text
    assert "from gui import" not in text
    assert "manufacturing_api." in text
