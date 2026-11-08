"""#2517: Fold Designer physical fold/gap/shrink Save sources never use GUI float fallback."""
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


FOLD_KEYS = (
    "zl1", "zl2", "zr2", "zr1", "yl1", "yr1", "ytop1", "ybottom1",
    "door_gap_w", "door_gap_h", "door_fold_l", "door_fold_r",
    "door_fold_t", "door_fold_b", "base_plate_shrink_top",
    "base_plate_shrink_bottom", "base_plate_shrink_left",
    "base_plate_shrink_right", "base_plate_bend",
)


@pytest.mark.parametrize("field", FOLD_KEYS)
@pytest.mark.parametrize("bad", (
    True, False, None, "nan", "inf", "-inf", float("nan"),
    float("inf"), "not-a-number",
))
def test_invalid_present_fold_numeric_must_fail_without_factory_default(field, bad):
    defaults = api.project_operator_fold_designer_snapshot_numeric_defaults()
    expected = api.normalize_operator_settings_updates(
        {field: defaults[field]}, {field: bad},
    )
    assert expected == {}
    with pytest.raises(ValueError, match=field):
        gui._read_snapshot_numeric_control(
            Var(bad), defaults[field], fold_field=field,
        )


@pytest.mark.parametrize("field", FOLD_KEYS)
@pytest.mark.parametrize("raw", ("0", "-3.125", "23.375"))
def test_valid_fold_numeric_parity_with_public_engine_including_sign_and_precision(field, raw):
    defaults = api.project_operator_fold_designer_snapshot_numeric_defaults()
    expected = api.normalize_operator_settings_updates(
        {field: defaults[field]}, {field: raw},
    )[field]
    assert gui._read_snapshot_numeric_control(
        Var(raw), defaults[field], fold_field=field,
    ) == expected


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_actual_fold_snapshot_rejects_bad_gap_or_fold_control_before_save(family):
    for field in ("zl1", "door_fold_b", "door_gap_w", "base_plate_shrink_left"):
        host = SnapshotHost(family, {"model": family})
        setattr(host, f"{field}_var", Var("nan"))
        before = deepcopy(host.fold_designer_app._phase6_input_snapshot)
        with pytest.raises(ValueError, match=field):
            gui._snapshot_base_state(host)
        assert host.fold_designer_app._phase6_input_snapshot == before


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_overlay_cannot_replace_valid_fold_control_with_corrupted_source(family):
    for field in ("zl2", "door_gap_h", "base_plate_bend", "indicator_box_fold"):
        host = SnapshotHost(family, {"model": family})
        host._collect_main_setting_values = lambda field=field: {
            "yl1": "19.125", field: "infinity",
        }
        before = deepcopy(host.fold_designer_app._phase6_input_snapshot)
        with pytest.raises(ValueError, match=field):
            gui._snapshot_base_state(host)
        assert host.fold_designer_app._phase6_input_snapshot == before


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_settings_overlay_serialized_flags_cannot_bypass_engine(family):
    for bad in ("maybe", 2, float("nan")):
        host = SnapshotHost(family, {"model": family})
        host._collect_main_setting_values = lambda: {
            "use_box_distance": bad, "multi_door_enabled": "false",
        }
        with pytest.raises(ValueError, match="布林值"):
            gui._snapshot_base_state(host)


@pytest.mark.parametrize("family", ("金庫型", "受電箱"))
def test_valid_overlay_has_same_physical_and_fold_sources_after_true_project_save_reload(
    family, tmp_path,
):
    host = SnapshotHost(family, {"model": family})
    host.door_gap_w_var = Var("4.125")
    host.zl1_var = Var("10")
    host._collect_main_setting_values = lambda: {
        "zl1": "-3.375",
        "door_gap_w": "1.625",
        "base_plate_shrink_left": "0",
        "indicator_box_fold": "50.875",
        "use_box_distance": "false",
        "multi_door_enabled": "on",
    }
    before = deepcopy(host.fold_designer_app._phase6_input_snapshot)
    snapshot = gui._snapshot_base_state(host)
    defaults = api.project_operator_fold_designer_snapshot_numeric_defaults()
    fold = api.normalize_operator_settings_updates(
        defaults, {key: snapshot[key] for key in defaults},
    )
    assert len(fold) == len(defaults)
    assert snapshot["zl1"] == snapshot["settings"]["zl1"] == -3.375
    assert snapshot["door_gap_w"] == snapshot["settings"]["door_gap_w"] == 1.625
    assert snapshot["base_plate_shrink_left"] == 0.0
    assert snapshot["indicator_box_fold"] == 50.875
    assert snapshot["use_box_distance"] is False
    assert snapshot["multi_door_enabled"] is True
    assert host.fold_designer_app._phase6_input_snapshot == before
    target = project.write_project(tmp_path / "fold-numeric.p6fold", {
        "schema": project.PROJECT_SCHEMA, "snapshot": snapshot,
    })
    readback = project.read_project(target)["snapshot"]
    for key in fold:
        assert readback[key] == snapshot[key] == fold[key]
    for flag in ("use_box_distance", "multi_door_enabled"):
        assert readback[flag] is snapshot[flag]


def test_unreadable_fold_source_fails_closed_but_unrelated_ui_fallback_survives():
    def broken():
        raise ValueError("Tk input cannot be read")
    var = SimpleNamespace(get=broken)
    with pytest.raises(ValueError, match="禁止使用預設值"):
        gui._read_snapshot_numeric_control(var, 12.5, fold_field="yl1")
    assert gui._read_snapshot_numeric_control(var, 12.5) == 12.5


def test_fold_snapshot_gui_routes_sources_to_public_engine_only():
    source = inspect.getsource(gui._snapshot_base_state)
    helper = inspect.getsource(gui._read_snapshot_numeric_control)
    defaults = api.project_operator_fold_designer_snapshot_numeric_defaults()
    assert "manufacturing_api.normalize_operator_settings_updates(" in source
    assert "manufacturing_api.normalize_operator_settings_updates(" in helper
    assert "if len(fold_source) != len(defaults)" in source
    assert "manufacturing_api.normalize_operator_settings_boolean(" in source
    for key in FOLD_KEYS:
        assert f'fold_field="{key}"' in source
        assert key in defaults
