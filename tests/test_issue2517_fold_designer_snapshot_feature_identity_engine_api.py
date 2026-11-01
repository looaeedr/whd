"""#2517 Door-grid features must not derive physical part IDs in GUI."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_part_adapters import door_layout_feature_map_to_part_features
from gui_modules.application import fold_designer_snapshot_projection as gui


def _snapshot():
    return {
        "model": "受電箱", "multi_door_enabled": True,
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
    }


def test_public_engine_id_source_preserves_authored_cell_and_source_inputs():
    snap = _snapshot()
    surface = {"door_c1_r1": ["stale"], "head": [{"id": "head"}]}
    authored = {"0:0": [{"id": "hole"}]}
    source = deepcopy((snap, surface, authored))
    result = api.project_fold_designer_snapshot_part_features(snap, surface, authored)
    canonical = door_layout_feature_map_to_part_features(
        ((800.0, (1100.0, 500.0)),), authored,
    )
    assert result["door_c1_r1"] == canonical["door_c1_r1"] == [{"id": "hole"}]
    assert result["door_c1_r2"] == []
    assert result["head"] == [{"id": "head"}]
    assert (snap, surface, authored) == source
    result["door_c1_r1"].clear()
    assert authored["0:0"] == [{"id": "hole"}]


@pytest.mark.parametrize("empty_key", ["0:0", (0, 0)])
def test_authored_empty_cell_clears_saved_physical_feature(empty_key):
    result = api.project_fold_designer_snapshot_part_features(
        _snapshot(),
        {"door_c1_r1": [{"id": "previous"}], "door_c1_r2": [{"id": "unmodified"}]},
        {empty_key: []},
    )
    assert result["door_c1_r1"] == []
    assert result["door_c1_r2"] == [{"id": "unmodified"}]


def test_missing_cell_provenance_keeps_existing_part_features_and_custom_owners():
    source = {"door_c1_r1": [{"id": "saved"}], "custom:part": [{"id": "other"}]}
    first = api.project_fold_designer_snapshot_part_features(_snapshot(), source, {})
    assert first["door_c1_r1"] == source["door_c1_r1"]
    assert first["door_c1_r2"] == []
    assert first["custom:part"] == source["custom:part"]
    snapshot = {"multi_door_enabled": False, "door_layout_columns": [[800, [1600]]]}
    assert api.project_fold_designer_snapshot_part_features(snapshot, source, {"0:0": []}) == source


def test_invalid_door_topology_fails_closed_before_partial_physical_result():
    snap = _snapshot()
    snap["door_layout_columns"] = [[-10.0, [500.0]]]
    source = {"door_c1_r1": [{"id": "saved"}]}
    before = deepcopy(source)
    with pytest.raises(ValueError):
        api.project_fold_designer_snapshot_part_features(snap, source, {"0:0": []})
    assert source == before


def test_gui_submits_operator_store_and_receives_engine_projection(monkeypatch):
    calls = []
    original = api.project_fold_designer_snapshot_part_features
    def forwarded(snapshot, surface, authored):
        calls.append((snapshot, surface, authored))
        return original(snapshot, surface, authored)
    monkeypatch.setattr(api, "project_fold_designer_snapshot_part_features", forwarded)
    host = SimpleNamespace(
        surface_features={"door_c1_r1": [{"id": "before"}]},
        door_layout_features={"0:0": [{"id": "after"}]},
    )
    snap = _snapshot()
    assert gui._snapshot_part_features(host, snap) is snap
    assert snap["part_features"]["door_c1_r1"] == [{"id": "after"}]
    assert len(calls) == 1
    assert calls[0][1] is host.surface_features
    assert calls[0][2] is host.door_layout_features
    source = inspect.getsource(gui._snapshot_workspace_state)
    assert "_snapshot_part_features(self, snapshot)" in source
    assert "door_layout_feature_map_to_part_features(" not in source
    assert "door_c" not in source
    assert "from gui_modules" not in inspect.getsource(
        __import__("ae_engine.door_layout_feature_projection", fromlist=["project_fold_designer_snapshot_part_features"])
    )
