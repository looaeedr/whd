"""#2517 main GUI Door-grid saved physical Features read via public Engine."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_part_adapters import (
    door_layout_feature_map_to_part_features,
    door_part_features_to_layout_feature_map,
)
from gui_modules.application import lifecycle as gui


def _columns():
    return ((800.0, (900.0, 700.0)), (400.0, (1600.0,)))


def _parts():
    return {
        "door_c1_r1": [{"id": "upper"}],
        "door_c1_r2": [],
        "door_c2_r1": [{"id": "right"}],
        "head": [{"id": "unrelated"}],
    }


def test_headless_root_facade_and_original_engine_identity_are_exact():
    assert api.project_operator_door_layout_cell_features_from_parts is (
        door_part_features_to_layout_feature_map
    )
    assert ae_engine.project_operator_door_layout_cell_features_from_parts is (
        door_part_features_to_layout_feature_map
    )


def test_saved_physical_door_features_read_as_editable_cells_without_source_mutation():
    source = _parts()
    before = deepcopy(source)
    result = api.project_operator_door_layout_cell_features_from_parts(
        _columns(), source,
    )
    expected = door_part_features_to_layout_feature_map(_columns(), source)
    assert result == expected == {
        "0:0": [{"id": "upper"}],
        "0:1": [],
        "1:0": [{"id": "right"}],
    }
    assert source == before
    assert result["0:0"] is not source["door_c1_r1"]
    result["0:0"].append({"id": "new editor row"})
    assert source == before


def test_editor_cell_to_physical_door_roundtrip_uses_same_engine_identity():
    authored = {
        "0:0": [{"id": "first"}],
        "0:1": [],
        "1:0": [{"id": "second"}],
    }
    before = deepcopy(authored)
    formal = door_layout_feature_map_to_part_features(_columns(), authored)
    restored = api.project_operator_door_layout_cell_features_from_parts(
        _columns(), formal,
    )
    assert restored == authored
    assert authored == before


@pytest.mark.parametrize("columns", (
    [],
    [(-4.0, [900.0])],
    [(800.0, [0.0])],
    [(800.0, [])],
    [(800.0, [float("inf")])],
))
def test_invalid_door_layout_refuses_rehydration_without_editing_physical_features(columns):
    source = _parts()
    before = deepcopy(source)
    with pytest.raises(ValueError):
        api.project_operator_door_layout_cell_features_from_parts(
            columns, source,
        )
    assert source == before


def test_main_gui_real_project_open_delegates_to_public_engine(monkeypatch):
    class _StopAtPublicEngine(Exception):
        pass

    observed = []
    def intercept(columns, part_features):
        observed.append((columns, deepcopy(part_features)))
        raise _StopAtPublicEngine

    monkeypatch.setattr(
        api, "project_operator_door_layout_cell_features_from_parts",
        intercept,
    )
    source = {
        "model": "金庫型",
        "multi_door_enabled": True,
        "door_layout_columns": [[200.0, [100.0, 100.0]]],
        "part_features": {"door_c1_r1": [{"id": "saved"}]},
    }
    before = deepcopy(source)
    host = SimpleNamespace(
        workspace_controller=SimpleNamespace(
            reset_receiving_mode_session=lambda: None,
        ),
        _reset_manual_corner_parameter_locks=lambda: None,
        baseline_var=SimpleNamespace(get=lambda: "金庫型"),
        _apply_original_fold_designer_snapshot=lambda _snapshot: None,
        surface_features={},
    )
    with pytest.raises(_StopAtPublicEngine):
        gui._apply_phase6_project_snapshot(host, source)
    assert observed == [
        (((200.0, (100.0, 100.0)),), source["part_features"])
    ]
    assert source == before


def test_real_p6fold_save_reload_preserves_physical_door_sources_for_public_readback(tmp_path):
    import phase6_project_file as project

    source = {
        "model": "金庫型", "w": 200.0, "h": 200.0,
        "d": 200.0, "t": 2.0, "fw": 25.0,
        "multi_door_enabled": True,
        "door_layout_columns": [[200.0, [100.0, 100.0]]],
        "part_features": {
            "door_c1_r1": [{"id": "saved-hole"}],
            "door_c1_r2": [],
        },
    }
    before = deepcopy(source)
    target = project.write_project(
        tmp_path / "physical-door-readback.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": source},
    )
    restored = project.read_project(target)["snapshot"]
    cells = api.project_operator_door_layout_cell_features_from_parts(
        restored["door_layout_columns"], restored["part_features"],
    )
    assert cells == {"0:0": [{"id": "saved-hole"}], "0:1": []}
    assert source == before


def test_both_main_gui_project_restore_and_live_sync_only_call_public_engine():
    project_source = inspect.getsource(gui._apply_phase6_project_snapshot)
    live_source = inspect.getsource(gui._apply_fold_designer_live_snapshot)
    for source in (project_source, live_source):
        assert "manufacturing_api.project_operator_door_layout_cell_features_from_parts(" in source
        assert "door_part_features_to_layout_feature_map(" not in source
    module = inspect.getsource(gui)
    assert "    door_part_features_to_layout_feature_map," not in module
