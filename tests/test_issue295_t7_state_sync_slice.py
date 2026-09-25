from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUI = ROOT / "gui.py"
STATE_SYNC = ROOT / "gui_modules" / "application" / "state_sync.py"


def _host_method(name: str):
    tree = ast.parse(GUI.read_text(encoding="utf-8"))
    host = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Phase6ApplicationHost"
    )
    nodes = [
        node for node in host.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
    ]
    assert nodes, name
    return nodes


def _loc(node) -> int:
    return node.end_lineno - node.lineno + 1


def test_state_sync_extraction_owner_exists_and_root_is_thin():
    assert STATE_SYNC.is_file()
    text = STATE_SYNC.read_text(encoding="utf-8")
    for name in (
        "init_variables",
        "setting_var_map",
        "collect_main_setting_values",
        "serialize_corner_selection",
        "serialize_manual_corner_state",
        "phase6_external_sync_envelope",
        "on_main_setting_var_changed",
    ):
        assert f"def {name}(" in text

    for name in (
        "init_variables",
        "_setting_var_map",
        "_collect_main_setting_values",
        "_serialize_corner_selection",
        "_serialize_manual_corner_state",
        "_phase6_external_sync_envelope",
        "_on_main_setting_var_changed",
    ):
        assert all(_loc(node) <= 5 for node in _host_method(name))


def test_corner_selection_serialization_contract_is_preserved():
    import gui
    from ae_engine.sheetmetal_geometry import (
        CornerDirection,
        CornerTypeId,
        CornerTypeSelection,
        CrossCornerMode,
    )

    raw = CornerTypeSelection(
        CornerTypeId.CROSS,
        0,
        cross_mode=CrossCornerMode.RETAIN,
        direction=CornerDirection.WIDTH,
        amount_t=1.25,
        secondary_retain_t=0.5,
        secondary_depth_t=2.0,
    )
    result = gui.Phase6ApplicationHost._serialize_corner_selection(raw)
    assert result == {
        "type_id": CornerTypeId.CROSS.value,
        "rotation_quadrants": 0,
        "cross_mode": CrossCornerMode.RETAIN.value,
        "direction": CornerDirection.WIDTH.value,
        "amount_t": 1.25,
    }


def test_state_sync_module_may_not_own_committed_services():
    if not STATE_SYNC.is_file():
        pytest.skip("RED: state_sync owner not created yet")
    text = STATE_SYNC.read_text(encoding="utf-8")
    assert "Phase6ProjectController(" not in text
    assert "Phase6WorkspaceController(" not in text
    assert "SettingsService(" not in text
    assert "import gui" not in text
    assert "from gui import" not in text
