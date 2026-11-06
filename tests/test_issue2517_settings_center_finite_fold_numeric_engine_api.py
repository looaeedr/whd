"""#2517: Main GUI finite Fold/Hole/Relief numeric inputs reuse Engine authority."""
from __future__ import annotations

import configparser
import inspect
import math
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from phase6_settings_center import (
    SettingsService, _SPEC_BY_KEY, _coerce, apply_settings_to_ae,
    load_settings_from_ae, save_defaults_to_ini,
)


def _host(tmp_path):
    return SimpleNamespace(
        INI_PATH=tmp_path / "settings.ini",
        config=configparser.ConfigParser(),
        W=800.0, H=1600.0, D=350.0, T=2.0, FW=25.0,
        DRAW_STOCK=False, zl1_def=15.0, yl1_def=15.0,
        door_fold_left_def=19.0, hang_hole_r=3.2,
        base_plate_shrink_def=55.0,
    )


# All are real supported settings, not proposed physical dimensions.
NONPHYSICAL_NUMERIC_KEYS = (
    "zl1", "yl1", "ybottom1", "door_fold_l", "hang_hole_r",
    "sq_width", "relief_bottom_y_factor", "base_plate_shrink_top",
    "indicator_box_fold", "notch_bottom_gap",
)


@pytest.mark.parametrize("key", NONPHYSICAL_NUMERIC_KEYS)
@pytest.mark.parametrize("invalid", [
    True, False, float("nan"), float("inf"), float("-inf"),
    "nan", "Inf", "-Infinity", "not a number", None,
])
def test_bad_fold_hole_relief_numeric_skipped_by_gui_and_rejected_for_direct_commit(
    key, invalid, tmp_path,
):
    host = _host(tmp_path)
    service = SettingsService(host)
    original = service.snapshot().as_dict()
    assert service.update({key: invalid}).as_dict() == original
    assert service.snapshot().as_dict() == original
    assert manufacturing_api.normalize_operator_settings_updates(
        {key: _SPEC_BY_KEY[key].default}, {key: invalid},
    ) == {}
    with pytest.raises(ValueError, match="有限數值"):
        apply_settings_to_ae(host, {key: invalid})
    with pytest.raises(ValueError, match="有限數值"):
        save_defaults_to_ini(host, {key: invalid}, keys=(key,), apply_runtime=False)
    assert not host.INI_PATH.exists()


@pytest.mark.parametrize("key", NONPHYSICAL_NUMERIC_KEYS)
@pytest.mark.parametrize("raw", ["0.0", "-2.125", "27.375"])
def test_numeric_engine_acceptance_and_gui_ini_roundtrip_match_without_new_sign_policy(
    key, raw, tmp_path,
):
    host = _host(tmp_path)
    service = SettingsService(host)
    expected = manufacturing_api.normalize_operator_settings_updates(
        {key: _SPEC_BY_KEY[key].default}, {key: raw},
    )[key]
    assert expected == float(raw)
    assert service.update({key: raw})[key] == expected
    service.persist_defaults(keys=(key,))
    parser = configparser.ConfigParser()
    parser.read(host.INI_PATH, encoding="utf-8")
    spec = _SPEC_BY_KEY[key]
    assert parser.getfloat(spec.section, spec.option) == expected


def test_runtime_multi_setting_validation_is_atomic_with_invalid_later_fold(tmp_path):
    host = _host(tmp_path)
    original_box = host.zl1_def
    original_endcap = host.yl1_def
    with pytest.raises(ValueError, match="有限數值"):
        apply_settings_to_ae(host, {"zl1": "18.25", "yl1": "nan"})
    assert host.zl1_def == original_box
    assert host.yl1_def == original_endcap
    assert not host.INI_PATH.exists()


def test_service_skips_only_invalid_numeric_in_mixed_input(tmp_path):
    host = _host(tmp_path)
    service = SettingsService(host)
    after = service.update({"zl1": "inf", "yl1": "16.375"})
    assert after["zl1"] == 15.0
    assert after["yl1"] == 16.375
    assert host.zl1_def == 15.0
    assert host.yl1_def == 16.375


def test_invalid_ini_legacy_numeric_uses_existing_valid_runtime_default(tmp_path):
    host = _host(tmp_path)
    host.config.add_section("BOX_BODY_Z")
    host.config.set("BOX_BODY_Z", "zl1", "nan")
    host.zl1_def = 14.75
    loaded = load_settings_from_ae(host)
    assert loaded["zl1"] == 14.75
    assert math.isfinite(loaded["zl1"])


def test_gui_consumes_existing_public_engine_numeric_gate(monkeypatch):
    calls = []
    original = manufacturing_api.normalize_operator_settings_updates

    def recording(saved, updates, *, external_apply_guard=False):
        calls.append((dict(saved), dict(updates), external_apply_guard))
        return original(saved, updates, external_apply_guard=external_apply_guard)

    monkeypatch.setattr(manufacturing_api, "normalize_operator_settings_updates", recording)
    assert _coerce(_SPEC_BY_KEY["zl1"], "21.25") == 21.25
    assert calls == [({"zl1": 15.0}, {"zl1": "21.25"}, False)]
    code = inspect.getsource(_coerce)
    assert "manufacturing_api.normalize_operator_settings_updates(" in code
    assert "return float(raw)" not in code
    assert "manufacturing_api.normalize_operator_source_dimension(" in code
    assert "manufacturing_api.normalize_operator_settings_boolean(" in code
