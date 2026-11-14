# -*- coding: utf-8 -*-
"""#2517 direct Settings service/controller staging must obey public Engine."""
from copy import deepcopy
import inspect
import json
import pytest
from ae_engine import manufacturing_api as api
from phase6_settings_service import Phase6SettingsTransactionService as Service
from phase6_settings_transaction_controller import Phase6SettingsTransactionController as Controller


def _maps():
    state = {
        "w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0, "fw": 25.0,
        "zl1": 15.0, "door_fold_l": 19.0,
        "draw_stock": False, "ui_text_size": "small",
    }
    return deepcopy(state), deepcopy(state), {}, {}


def _service():
    settings, snapshot, box, pending = _maps()
    return Service(settings_values=settings, input_snapshot=snapshot,
                   box_whd=box, pending_settings=pending), settings, snapshot, box, pending


@pytest.mark.parametrize("key,raw", [
    ("w", "801.125"), ("h", "1601.25"), ("d", "350.001"),
    ("t", "2.375"), ("fw", "29.75"),
])
def test_raw_physical_staging_delegates_public_engine_and_preserves_pending(
    monkeypatch, key, raw,
):
    original = api.normalize_operator_source_dimension
    calls = []
    def spy(value, *, field):
        calls.append((field, value))
        return original(value, field=field)
    monkeypatch.setattr(api, "normalize_operator_source_dimension", spy)
    svc, settings, snapshot, box, pending = _service()
    svc.install_debounce_job("after#1")
    plan = svc.stage_setting_update(key, raw)
    expected = original(raw, field=key)
    assert calls == [(key, raw)]
    assert plan.changed and plan.value == expected
    assert plan.schedule_after_ms == 150 and plan.cancel_job == "after#1"
    assert settings[key] == snapshot[key] == pending[key] == expected
    assert svc.drain_pending().pending == {key: expected}
    assert box == {}


@pytest.mark.parametrize("key", ["w", "h", "d", "t", "fw"])
@pytest.mark.parametrize("bad", [
    True, False, "nan", "inf", float("nan"), float("inf"),
    "0", "-0.001", "-3", None, "bad",
])
def test_bad_physical_never_pollutes_service_drafts(key, bad):
    svc, settings, snapshot, box, pending = _service()
    svc.install_debounce_job("after#1")
    before = deepcopy((settings, snapshot, box, pending))
    with pytest.raises(ValueError):
        svc.stage_setting_update(key, bad)
    assert (settings, snapshot, box, pending) == before
    assert svc.debounce_job == "after#1"


@pytest.mark.parametrize("key,raw,expected", [
    ("zl1", "-2.125", -2.125),
    ("door_fold_l", "0", 0.0),
    ("draw_stock", "false", False),
    ("draw_stock", "true", True),
    ("ui_text_size", "大", "large"),
])
def test_numeric_bool_and_ui_stage_existing_semantics(key, raw, expected):
    svc, settings, snapshot, box, pending = _service()
    plan = svc.stage_setting_update(key, raw)
    if key == "draw_stock" and not expected:
        assert not plan.changed and pending == {}
    else:
        assert plan.changed and plan.value == expected
        assert settings[key] == snapshot[key] == pending[key] == expected


@pytest.mark.parametrize("key,bad", [
    ("zl1", True), ("door_fold_l", float("nan")), ("zl1", "inf"),
    ("draw_stock", "maybe"), ("draw_stock", 2),
    ("not_a_declared_settings_field", 5),
])
def test_bad_numeric_bool_or_unknown_key_atomic(key, bad):
    svc, settings, snapshot, box, pending = _service()
    before = deepcopy((settings, snapshot, box, pending))
    with pytest.raises(ValueError):
        svc.stage_setting_update(key, bad)
    assert (settings, snapshot, box, pending) == before


def test_legacy_missing_declared_setting_uses_schema_and_engine():
    svc, settings, snapshot, box, pending = _service()
    assert "base_plate_shrink_top" not in settings
    plan = svc.stage_setting_update("base_plate_shrink_top", "55.5")
    assert plan.changed and plan.value == 55.5
    assert settings["base_plate_shrink_top"] == snapshot["base_plate_shrink_top"] == 55.5


def test_same_value_and_destroying_bypass_do_not_modify_drafts():
    svc, settings, snapshot, box, pending = _service()
    before = deepcopy((settings, snapshot, box, pending))
    assert not svc.stage_setting_update("w", "800").changed
    assert not svc.stage_setting_update("w", "invalid", destroying=True).changed
    assert (settings, snapshot, box, pending) == before


def test_controller_calls_same_public_guard_and_json_roundtrip():
    settings, snapshot, box, pending = _maps()
    controller = Controller(settings_values=settings, input_snapshot=snapshot,
                            box_whd=box, pending_settings=pending)
    before = deepcopy((settings, snapshot, box, pending))
    with pytest.raises(ValueError):
        controller.stage_setting_update("t", "0")
    with pytest.raises(ValueError):
        controller.stage_setting_update("draw_stock", "2")
    assert (settings, snapshot, box, pending) == before
    assert controller.stage_setting_update("fw", "29.125").changed
    assert controller.stage_setting_update("draw_stock", "true").changed
    assert controller.drain_pending().pending == {"fw": 29.125, "draw_stock": True}
    roundtrip = json.loads(json.dumps(snapshot, ensure_ascii=False))
    assert roundtrip["fw"] == 29.125 and roundtrip["draw_stock"] is True


def test_stage_does_not_implement_own_manufacturing_numeric_formula():
    source = inspect.getsource(Service.stage_setting_update)
    assert "manufacturing_api.normalize_operator_source_dimension(" in source
    assert "settings_transitions.normalize_updates(" in source
    assert "float(value)" not in source and "bool(value)" not in source
