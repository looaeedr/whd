"""#2517: Saved Fold/Indicator operation flags are normalized by public Engine."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import fold_designer_snapshot_projection as gui
from tests.test_issue2517_receiving_base_plate_snapshot_alias_save_reload import (
    SnapshotHost, Var,
)
import phase6_project_file as project


def _host(family):
    host = SnapshotHost(family, {"model": family})
    host.is_box_dist_var = Var(False)
    host.multi_door_enabled_var = Var(False)
    host.is_indicator_box_var = Var(False)
    host.is_door_indicator_var = Var(False)
    host.door_indicator_offset_x = 0
    host.door_indicator_offset_y = 0
    return host


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("multi,boxdist,expected_multi,expected_dist", (
    ("false", "false", False, False),
    ("TRUE", "on", True, True),
    ("off", 1, False, True),
    (1, 0, True, False),
))
def test_saved_snapshot_bool_sources_match_engine_and_roundtrip(
    family, multi, boxdist, expected_multi, expected_dist, tmp_path
):
    host = _host(family)
    host.multi_door_enabled_var = Var(multi)
    host.is_box_dist_var = Var(boxdist)
    before = deepcopy(host.fold_designer_app._phase6_input_snapshot)
    saved = gui._snapshot_base_state(host)
    assert saved["multi_door_enabled"] is expected_multi
    assert saved["use_box_distance"] is expected_dist
    assert saved["multi_door_enabled"] == api.normalize_operator_settings_boolean(multi)
    assert saved["use_box_distance"] == api.normalize_operator_settings_boolean(boxdist)
    assert host.fold_designer_app._phase6_input_snapshot == before
    filename = project.write_project(tmp_path / "operator-flags.p6fold", {
        "schema": project.PROJECT_SCHEMA, "snapshot": saved,
    })
    loaded = project.read_project(filename)["snapshot"]
    assert loaded["multi_door_enabled"] is expected_multi
    assert loaded["use_box_distance"] is expected_dist


@pytest.mark.parametrize("field,bad", (
    ("is_box_dist_var", "maybe"),
    ("is_box_dist_var", 2),
    ("is_box_dist_var", None),
    ("is_box_dist_var", float("nan")),
    ("multi_door_enabled_var", "invalid"),
    ("multi_door_enabled_var", "2"),
    ("multi_door_enabled_var", -1),
    ("multi_door_enabled_var", None),
))
def test_invalid_snapshotted_source_flag_fails_without_saved_source_mutation(field, bad):
    host = _host("受電箱")
    setattr(host, field, Var(bad))
    before = deepcopy(host.fold_designer_app._phase6_input_snapshot)
    with pytest.raises(ValueError, match="布林值"):
        gui._snapshot_base_state(host)
    assert host.fold_designer_app._phase6_input_snapshot == before


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
@pytest.mark.parametrize("box_flag,door_flag,expected_box,expected_door", (
    ("false", "false", False, False),
    ("false", "true", False, True),
    ("on", "off", True, False),
    (1, 1, True, True),
))
def test_indicator_active_flags_select_only_engine_accepted_physical_holes(
    family, box_flag, door_flag, expected_box, expected_door
):
    host = _host(family)
    host.is_indicator_box_var = Var(box_flag)
    host.is_door_indicator_var = Var(door_flag)
    host.indicator_l_var = Var("1")
    host.indicator_layer_g_vars = [Var("3")] * 6
    host.door_indicator_l_var = Var("1")
    host.door_indicator_layer_g_vars = [Var("2")] * 6
    snapshot = gui._snapshot_base_state(host)
    gui._snapshot_part_dimensions(host, snapshot)
    assert snapshot["door_indicator_box_enabled"] is expected_box
    assert snapshot["door_indicator_groups"] == ([2] if expected_door else [])
    assert snapshot["indicator_layer_groups"] == [3] if expected_box else snapshot["indicator_layer_groups"] == [1]
    assert json.loads(json.dumps(snapshot, ensure_ascii=False))["door_indicator_box_enabled"] is expected_box


@pytest.mark.parametrize("field,bad", (
    ("is_indicator_box_var", "maybe"), ("is_indicator_box_var", 2),
    ("is_indicator_box_var", None), ("is_indicator_box_var", float("nan")),
    ("is_door_indicator_var", "maybe"), ("is_door_indicator_var", -1),
    ("is_door_indicator_var", 1.2), ("is_door_indicator_var", None),
))
def test_invalid_indicator_enablement_never_writes_part_dimensions_or_holes(field, bad):
    host = _host("金庫型")
    snapshot = gui._snapshot_base_state(host)
    before = deepcopy(snapshot)
    setattr(host, field, Var(bad))
    with pytest.raises(ValueError, match="布林值"):
        gui._snapshot_part_dimensions(host, snapshot)
    assert snapshot == before
    assert "part_dimensions" not in snapshot
    assert "door_indicator_groups" not in snapshot


def test_gui_snapshot_contains_no_private_boolean_manufacturing_conversion():
    base = inspect.getsource(gui._snapshot_base_state)
    parts = inspect.getsource(gui._snapshot_part_dimensions)
    for source in (base, parts):
        assert "manufacturing_api.normalize_operator_settings_boolean(" in source
    for forbidden in (
        "bool(self.is_box_dist_var.get())",
        "bool(self.multi_door_enabled_var.get())",
        "bool(self.is_indicator_box_var.get())",
        "bool(self.is_door_indicator_var.get())",
    ):
        assert forbidden not in (base + parts)
