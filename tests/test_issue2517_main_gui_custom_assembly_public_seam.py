"""#2517 main GUI live custom-model and legacy AssemblyCorner use public Engine API."""
from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.corner_type_ui import assembly_type_from_corner_state, is_unknown_model
from ae_engine.sheetmetal_geometry import CornerTypeId, CornerTypeSelection
from gui import Phase6ApplicationHost as GUI

ROOT = Path(__file__).resolve().parents[1]


def test_original_gui_module_compatibility_names_delegate_to_public_engine():
    import gui
    assert gui.is_unknown_model is api.is_unknown_operator_model
    assert gui.assembly_type_from_corner_state is api.operator_assembly_type_from_corner_state


@pytest.mark.parametrize("raw,custom", [
    ("自訂", True), ("未知類型", True), (" 自訂 ", True),
    ("金庫型", False), ("受電箱", False), ("", False), (None, False),
])
def test_live_main_gui_baseline_source_matches_engine_model_classification(raw, custom):
    original = {"source": raw}
    before = deepcopy(original)
    host = SimpleNamespace(baseline_var=SimpleNamespace(get=lambda: original["source"]))
    value = GUI._baseline_source_model(host)
    assert api.is_unknown_operator_model(raw) is custom
    assert api.is_unknown_operator_model(raw) == is_unknown_model(raw)
    assert value == (None if custom or not raw else str(raw).strip())
    assert original == before


@pytest.mark.parametrize("raw,expected", [
    ("未知類型", True), ("自訂", True), ("金庫型", False), ("受電箱", False),
])
def test_live_main_gui_corner_type_edit_permission_matches_engine(raw, expected):
    host = SimpleNamespace(
        baseline_var=SimpleNamespace(get=lambda: raw),
        manual_corner_state={"head": {}, "indicator_box": {}},
    )
    assert GUI._corner_part_type_editable(host, "head") is expected
    assert GUI._corner_part_type_editable(host, "indicator_box") is False
    assert GUI._corner_part_type_editable(host, "not-a-sheet") is False


@pytest.mark.parametrize("raw,expected", [
    ("未知類型", True), ("自訂", True), ("金庫型", False), ("受電箱", False),
])
def test_live_main_gui_assembly_commit_runs_only_for_custom_model(raw, expected):
    applied = []
    host = SimpleNamespace(
        baseline_var=SimpleNamespace(get=lambda: raw),
        _current_box_assembly_type=lambda: CornerTypeId.INSERT,
        _set_box_assembly_type=lambda value, **kwargs: applied.append((value, kwargs)),
    )
    GUI.on_box_assembly_changed(host)
    assert applied == ([(CornerTypeId.INSERT, {"reset_bottom_defaults": False})] if expected else [])


@pytest.mark.parametrize("type_id", [CornerTypeId.INSERT, CornerTypeId.OVERLAY, CornerTypeId.INSERT_OVERLAY])
def test_live_main_gui_legacy_corner_fallback_matches_engine_without_source_change(type_id):
    state = {
        "head": {"top_left": CornerTypeSelection(type_id)},
        "tail": {"top_right": CornerTypeSelection(type_id)},
    }
    before = deepcopy(state)
    host = SimpleNamespace(box_assembly_type_var=None, assembly_joint_state={}, manual_corner_state=state)
    assert GUI._current_box_assembly_type(host) == api.operator_assembly_type_from_corner_state(state)
    assert api.operator_assembly_type_from_corner_state is assembly_type_from_corner_state
    assert state == before


def test_live_main_gui_corrupt_legacy_corner_source_does_not_mutate_it():
    state = {"head": {"top_left": {"type_id": "INVALID"}, "unrecognized": [1, 2]}}
    before = deepcopy(state)
    host = SimpleNamespace(box_assembly_type_var=None, assembly_joint_state={}, manual_corner_state=state)
    assert GUI._current_box_assembly_type(host) == api.operator_assembly_type_from_corner_state(state)
    assert state == before


def test_main_gui_migrated_owners_only_use_public_seams():
    tree = ast.parse((ROOT / "gui.py").read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.ImportFrom)
        and node.module == "ae_engine.corner_type_ui"
        and any(alias.name in {"is_unknown_model", "assembly_type_from_corner_state"} for alias in node.names)
        for node in ast.walk(tree)
    )
    calls = [
        node.func.attr for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "manufacturing_api"
    ]
    assert calls.count("is_unknown_operator_model") == 3
    assert calls.count("operator_assembly_type_from_corner_state") == 1
