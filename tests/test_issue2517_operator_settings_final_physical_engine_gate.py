# -*- coding: utf-8 -*-
"""#2517 public Engine external Settings and final commit guard T/FW like W/H/D."""
from copy import deepcopy
import inspect
import json

import pytest

from ae_engine import manufacturing_api as api
from phase6_settings_transitions import normalize_updates, commit_settings
from phase6_settings_transaction_controller import Phase6SettingsTransactionController


def _states():
    state = {
        "w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0,
        "fw": 25.0, "zl1": 15.0, "draw_stock": False,
    }
    return deepcopy(state), deepcopy(state), {
        "w": 800.0, "h": 1600.0, "d": 350.0,
    }


@pytest.mark.parametrize("field", ["w", "h", "d", "t", "fw"])
@pytest.mark.parametrize("bad", [
    True, False, "nan", float("inf"), 0, "0", -0.25,
    "-0.01", None, "invalid",
])
def test_public_external_and_final_commit_reject_invalid_physical(field, bad):
    settings, snapshot, box = _states()
    before = deepcopy((settings, snapshot, box))
    with pytest.raises(ValueError, match="包外尺寸"):
        api.normalize_operator_settings_updates(settings, {field: bad})
    with pytest.raises(ValueError, match="包外尺寸"):
        normalize_updates(settings, {field: bad})
    with pytest.raises(ValueError, match="包外尺寸"):
        api.commit_operator_settings_state(settings, snapshot, box, {field: bad})
    with pytest.raises(ValueError, match="包外尺寸"):
        commit_settings(settings, snapshot, box, {field: bad})
    assert (settings, snapshot, box) == before


@pytest.mark.parametrize("field,value", [
    ("w", "800.125"), ("h", "1600.5"), ("d", "350.0625"),
    ("t", "2.375"), ("fw", "29.125"),
])
def test_external_and_final_commit_match_canonical_physical_validator(field, value):
    settings, snapshot, box = _states()
    before = deepcopy((settings, snapshot, box))
    expected = api.normalize_operator_source_dimension(value, field=field)
    normalized = api.normalize_operator_settings_updates(settings, {field: value})
    assert normalized == {field: expected}
    assert normalize_updates(settings, {field: value}) == normalized
    saved = api.commit_operator_settings_state(settings, snapshot, box, normalized)
    assert commit_settings(settings, snapshot, box, normalized) == saved
    assert saved.settings_values[field] == expected
    assert saved.input_snapshot[field] == expected
    assert saved.committed[field] == expected
    if field in ("w", "h", "d"):
        assert saved.box_whd[field] == expected
    else:
        assert saved.box_whd == box
    assert (settings, snapshot, box) == before
    reloaded = json.loads(json.dumps(saved.input_snapshot, ensure_ascii=False))
    assert reloaded[field] == expected


def test_mixed_settings_request_with_invalid_final_fw_is_atomic():
    settings, snapshot, box = _states()
    before = deepcopy((settings, snapshot, box))
    source = {"w": "820.125", "t": "2.5", "fw": "nan"}
    with pytest.raises(ValueError):
        api.normalize_operator_settings_updates(settings, source)
    with pytest.raises(ValueError):
        api.commit_operator_settings_state(settings, snapshot, box, source)
    assert (settings, snapshot, box) == before


def test_legacy_nonphysical_skip_and_settings_boolean_are_unchanged():
    settings, snapshot, box = _states()
    value = normalize_updates(
        settings, {"zl1": "nan", "draw_stock": "false", "fw": "29.125"},
    )
    assert value == {"draw_stock": False, "fw": 29.125}
    committed = commit_settings(settings, snapshot, box, value)
    assert committed.settings_values["draw_stock"] is False
    assert committed.input_snapshot["fw"] == 29.125


def test_real_controller_final_commit_is_not_an_unchecked_physical_bypass():
    settings, snapshot, box = _states()
    controller = Phase6SettingsTransactionController(
        settings_values=settings, input_snapshot=snapshot, box_whd=box,
    )
    before = deepcopy((settings, snapshot, box))
    with pytest.raises(ValueError):
        controller.commit_settings({"t": 0, "fw": 29.5})
    assert (settings, snapshot, box) == before
    result = controller.commit_settings({"t": "2.375", "fw": "29.5"})
    assert result == {"t": 2.375, "fw": 29.5}
    assert snapshot["t"] == settings["t"] == 2.375
    assert snapshot["fw"] == settings["fw"] == 29.5
    assert box == before[2]


def test_original_public_engine_owns_final_source_rule_without_gui_formula():
    normalize = inspect.getsource(api.normalize_operator_settings_updates)
    commit = inspect.getsource(api.commit_operator_settings_state)
    assert "normalize_operator_source_dimension(raw, field=key)" in normalize
    assert "PHYSICAL_SNAPSHOT_SOURCE_KEYS" in normalize
    assert "PHYSICAL_SNAPSHOT_SOURCE_KEYS" in commit
    assert "normalize_operator_source_dimension(" in commit
