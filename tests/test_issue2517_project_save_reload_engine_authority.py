# -*- coding: utf-8 -*-
"""#2517 no-Tk Engine-owned saved project state and real persistence parity."""
from copy import deepcopy
import json

import pytest

from ae_engine import manufacturing_api
from ae_engine.door_dividers import derive_box_body_dividers
import phase6_project_file as project


def _vault_source():
    return {
        "model": "金庫型", "d": 200.0, "t": 2.0,
        "multi_door_enabled": True, "door_layout_scope": "main",
        "door_layout_columns": [[200, [100, 120]]],
        "door_handle_edges": {"0:0": "左", "0:1": "RIGHT", "9:9": "TOP"},
        "inner_doors": [{
            "stable_id": "door:0:1",
            "lower_frame_role": {"role": "lower_frame", "divider_stable_id": "stale"},
            "frame_spans": {"derived": 999},
            "inner_door_finished_size": [999, 999],
        }],
        "divider_parts": [{"stale": "geometry"}],
        "inner_door_frame_parts": [{"stale": "frame"}],
        "_receiving_runtime_selection": {"fake": True},
    }


def test_engine_repairs_saved_door_source_without_mutating_request():
    source = _vault_source()
    before = deepcopy(source)
    result = manufacturing_api.normalize_authoritative_door_state(source)
    assert source == before
    assert result["door_layout_columns"] == [[200.0, [100.0, 120.0]]]
    assert result["door_handle_edges"] == {"0:0": "LEFT", "0:1": "RIGHT"}
    for transient in ("divider_parts", "inner_door_frame_parts", "_receiving_runtime_selection"):
        assert transient not in result
    inner = result["inner_doors"][0]
    assert "frame_spans" not in inner and "inner_door_finished_size" not in inner
    dividers = derive_box_body_dividers(
        ((200.0, (100.0, 120.0)),), depth=200.0, thickness=2.0,
        layout_scope="main", handle_edges=result["door_handle_edges"],
    )
    horizontal_ids = [row.stable_id for row in dividers if row.axis == "HORIZONTAL"]
    assert len(horizontal_ids) == 1
    assert inner["lower_frame_role"] == {
        "role": "lower_frame", "divider_stable_id": horizontal_ids[0],
    }


def test_real_save_reload_uses_same_engine_authority_and_drops_preview(tmp_path):
    source = _vault_source()
    expected = manufacturing_api.normalize_project_snapshot_authority(source)
    target = project.write_project(tmp_path / "operator.p6fold", {
        "schema": project.PROJECT_SCHEMA, "snapshot": source,
        "final_geometry": {"door": {"fake": "preview"}},
    })
    persisted = json.loads(target.read_text(encoding="utf-8"))
    assert persisted["final_geometry"] == {}
    assert persisted["snapshot"]["door_handle_edges"] == expected["door_handle_edges"]
    restored = project.read_project(target)
    assert restored["final_geometry"] == {}
    assert restored["snapshot"] == manufacturing_api.normalize_project_snapshot_authority(
        persisted["snapshot"]
    )
    assert restored["snapshot"]["inner_doors"][0]["lower_frame_role"] == (
        expected["inner_doors"][0]["lower_frame_role"]
    )


def test_receiving_project_save_reload_keeps_bay_source(tmp_path):
    snapshot = {"model": "受電箱", "w": 400.0, "h": 500.0, "d": 200.0, "t": 2.0}
    expected = manufacturing_api.normalize_project_snapshot_authority(snapshot)
    assert expected["receiving_layout"]["sets"][0]["bays"]
    assert expected["door_nameplate_center_datum_top"] is not None
    target = project.write_project(tmp_path / "receiving.p6fold", {
        "schema": project.PROJECT_SCHEMA, "snapshot": snapshot, "final_geometry": {},
    })
    restored = project.read_project(target)
    assert restored["schema"] == project.PROJECT_SCHEMA_V2
    assert restored["snapshot"]["receiving_layout"] == expected["receiving_layout"]
    saved_bytes = json.loads(target.read_text(encoding="utf-8"))
    assert all(key not in saved_bytes["snapshot"] for key in ("w", "h", "d"))
    assert restored["final_geometry"] == {}


@pytest.mark.parametrize("invalid", [
    {"door_layout_columns": [[True, [100.0]]]},
    {"door_layout_columns": [[200.0, ["100"]]]},
    {"door_handle_edges": False},
    {"inner_doors": [{"stable_id": True}]},
    {"d": True},
    {"t": float("nan")},
])
def test_invalid_authority_rejected_before_save(tmp_path, invalid):
    source = {**_vault_source(), **invalid}
    with pytest.raises(ValueError):
        manufacturing_api.normalize_project_snapshot_authority(source)
    path = tmp_path / "invalid.p6fold"
    with pytest.raises(ValueError):
        project.write_project(path, {"schema": project.PROJECT_SCHEMA, "snapshot": source})
    assert not path.exists()


def test_phase6_project_file_forwards_to_public_engine(monkeypatch):
    expected = {"engine": "only"}
    observed = []
    def delegated(snapshot):
        observed.append(snapshot)
        return expected
    monkeypatch.setattr(manufacturing_api, "normalize_project_snapshot_authority", delegated)
    source = {"model": "金庫型"}
    assert project._materialize_project_snapshot(source) is expected
    assert observed == [source]
