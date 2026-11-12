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
    assert "door_c1_r1" not in source and "door_c1_r2" not in source
    assert "from gui_modules" not in inspect.getsource(
        __import__("ae_engine.door_layout_feature_projection", fromlist=["project_fold_designer_snapshot_part_features"])
    )


@pytest.mark.parametrize("raw_flag", (
    False, "false", " FALSE ", "off", "0", 0,
))
def test_serialized_disabled_multidoor_does_not_overwrite_saved_physical_holes(raw_flag):
    snap = _snapshot()
    snap["multi_door_enabled"] = raw_flag
    saved = {"door_c1_r1": [{"id": "saved-hole"}], "head": [{"id": "head"}]}
    authored = {"0:0": [{"id": "live-but-disabled"}]}
    before = deepcopy((snap, saved, authored))
    result = api.project_fold_designer_snapshot_part_features(snap, saved, authored)
    assert result == saved
    assert (snap, saved, authored) == before


@pytest.mark.parametrize("raw_flag", (
    True, "true", " TRUE ", "on", "1", 1,
))
def test_serialized_enabled_multidoor_uses_same_canonical_engine_cell_keys(raw_flag):
    snap = _snapshot()
    snap["multi_door_enabled"] = raw_flag
    saved = {"door_c1_r1": [{"id": "stale"}]}
    authored = {"0:0": [{"id": "new-hole"}]}
    result = api.project_fold_designer_snapshot_part_features(snap, saved, authored)
    assert result["door_c1_r1"] == [{"id": "new-hole"}]
    assert result["door_c1_r2"] == []


@pytest.mark.parametrize("bad_flag", (
    None, "maybe", 2, -1, 0.5, [], {}, float("nan"),
))
def test_invalid_saved_multidoor_flag_never_authorizes_feature_reprojection(bad_flag):
    snap = _snapshot()
    snap["multi_door_enabled"] = bad_flag
    saved = {"door_c1_r1": [{"id": "saved"}]}
    authored = {"0:0": [{"id": "unverified"}]}
    before = deepcopy((snap, saved, authored))
    with pytest.raises(ValueError, match="設定的布林值"):
        api.project_fold_designer_snapshot_part_features(snap, saved, authored)
    assert (snap, saved, authored) == before


@pytest.mark.parametrize("bad_grid", (
    False,
    "800x1600",
    [[True, [1100.0, 500.0]]],
    [[800.0, [False, 500.0]]],
    [[800.0, [float("nan"), 500.0]]],
    [[800.0, [1100.0, float("inf")]]],
    [[800.0, []]],
))
def test_enabled_mode_cannot_turn_corrupt_saved_door_grid_into_physical_features(bad_grid):
    snap = _snapshot()
    snap["door_layout_columns"] = bad_grid
    before = deepcopy(snap)
    saved = {"door_c1_r1": [{"id": "saved"}]}
    with pytest.raises((ValueError, TypeError)):
        api.project_fold_designer_snapshot_part_features(
            snap, saved, {"0:0": [{"id": "unverified"}]},
        )
    assert snap == before
    assert saved == {"door_c1_r1": [{"id": "saved"}]}


def test_saved_fractional_grid_and_raw_flag_have_stable_physical_feature_identity():
    snap = _snapshot()
    snap["multi_door_enabled"] = "true"
    snap["door_layout_columns"] = [["800.125", ["1100.25", "499.875"]]]
    saved = {"door_c1_r1": [{"id": "old"}]}
    authored = {"0:0": [{"id": "new"}], "0:1": []}
    before = deepcopy((snap, saved, authored))
    result = api.project_fold_designer_snapshot_part_features(snap, saved, authored)
    assert result["door_c1_r1"] == [{"id": "new"}]
    assert result["door_c1_r2"] == []
    assert (snap, saved, authored) == before


@pytest.mark.parametrize("authored_key", ("0:0", (0, 0)))
def test_real_p6fold_reload_feature_holes_match_engine_dxf_source(
    tmp_path, authored_key,
):
    """Same saved physical Hole source feeds PartSpec and verified/reopened DXF."""
    import ezdxf
    import phase6_project_file as project
    from ae_engine.sheetmetal_features import CircleFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2

    old = CircleFeature(
        diameter=11.0, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(90.0, 100.0), layer="CUTTING", source_type="old",
    )
    new = CircleFeature(
        diameter=13.75, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(101.5, 125.25), layer="CUTTING", source_type="authored",
    )
    snap = {
        "model": "金庫型", "w": 800.0, "h": 1600.0,
        "d": 350.0, "t": 2.0, "fw": 25.0,
        "multi_door_enabled": "true",
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
    }
    physical = api.project_fold_designer_snapshot_part_features(
        snap, {"door_c1_r1": [old]}, {authored_key: [new]},
    )
    assert physical["door_c1_r1"] == [new]
    before = deepcopy((snap, physical))
    path = project.write_project(
        tmp_path / "door-source-feature.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": {**snap, "part_features": physical}},
    )
    reopened = project.read_project(path)["snapshot"]
    assert reopened["part_features"]["door_c1_r1"] == [new]
    assert (snap, physical) == before
    spec = api.build_door_operator_part_spec(
        {
            "w": 800.0, "h": 1100.0, "t": 2.0, "fw": 25.0,
            "door_gap_w": 2.0, "door_gap_h": 2.0,
            "door_fold_l": 10.0, "door_fold_r": 10.0,
            "door_fold_t": 10.0, "door_fold_b": 10.0,
        },
        model_name="金庫型", features=tuple(reopened["part_features"]["door_c1_r1"]),
    )
    scene = api.build_part_render_data(spec)
    assert scene.material is not None and scene.material.area > 0
    output = tmp_path / "door_c1_r1.dxf"
    api.save_part_render_data_dxf(scene, output, verify_reopen=True)
    assert api.verify_saved_part_render_data_dxf(scene, output).ok
    cutting_circles = [
        entity for entity in ezdxf.readfile(output).modelspace()
        if entity.dxftype() == "CIRCLE" and entity.dxf.layer == "CUTTING"
    ]
    assert any(abs(float(c.dxf.radius) - 6.875) < 1e-6 for c in cutting_circles)



def test_original_engine_formal_feature_mapper_supports_legacy_tuple_with_real_hole():
    columns = ((800.0, (1100.0, 500.0)),)
    hole = {"id": "physical-cutting-hole", "layer": "CUTTING"}
    before = {(0, 0): [hole]}
    copied = deepcopy(before)
    via_tuple = door_layout_feature_map_to_part_features(columns, before)
    via_string = door_layout_feature_map_to_part_features(columns, {"0:0": [hole]})
    assert via_tuple == via_string
    assert via_tuple["door_c1_r1"] == [hole]
    assert via_tuple["door_c1_r2"] == []
    assert before == copied
    via_tuple["door_c1_r1"].append({"id": "other"})
    assert before == copied


def test_saved_legacy_nonempty_cell_replaces_stale_physical_door_hole():
    saved = {"door_c1_r1": [{"id": "old-hole"}]}
    authored = {(0, 0): [{"id": "new-hole"}]}
    before = deepcopy((saved, authored))
    projected = api.project_fold_designer_snapshot_part_features(
        _snapshot(), saved, authored,
    )
    assert projected["door_c1_r1"] == [{"id": "new-hole"}]
    assert projected["door_c1_r2"] == []
    assert (saved, authored) == before


def test_duplicate_cell_aliases_fail_closed_before_publishing_any_physical_feature():
    source = {
        (0, 0): [{"id": "original-hole"}],
        "0:0": [{"id": "other-hole"}],
    }
    prior = deepcopy(source)
    with pytest.raises(ValueError, match="DOOR_LAYOUT_FEATURE_AMBIGUOUS_CELL_SOURCE"):
        door_layout_feature_map_to_part_features(
            ((800.0, (1100.0, 500.0)),), source,
        )
    with pytest.raises(ValueError, match="DOOR_LAYOUT_FEATURE_AMBIGUOUS_CELL_SOURCE"):
        api.project_fold_designer_snapshot_part_features(
            _snapshot(), {"door_c1_r1": [{"id": "saved"}]}, source,
        )
    assert source == prior


