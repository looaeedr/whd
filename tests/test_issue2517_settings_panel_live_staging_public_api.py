# -*- coding: utf-8 -*-
"""#2517 Settings Panel stages only public Engine-qualified physical/numeric input."""
from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from phase6_settings_center import SettingSpec
from phase6_settings_panel import Phase6SettingsPanel


class Var:
    def __init__(self, raw):
        self.raw = raw

    def get(self):
        return self.raw


def _host():
    saved = {
        "w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0,
        "zl1": 15.0, "door_fold_l": 19.0,
        "enabled": True,
    }
    staged = []
    host = SimpleNamespace(
        _guard=False, _rendering=False,
        _values_snapshot=lambda: deepcopy(saved),
        _stage_setting_update=lambda key, value: staged.append((key, value)),
    )
    return host, saved, staged


@pytest.mark.parametrize("key", ["w", "h", "d", "t"])
@pytest.mark.parametrize("raw", [
    "nan", "inf", "-inf", "bad", "0", "-2", 0, -3, True, False,
])
def test_live_global_physical_invalid_source_is_never_staged(key, raw):
    host, saved, staged = _host()
    before = deepcopy(saved)
    Phase6SettingsPanel._on_left_numeric_changed(host, key, Var(raw))
    assert staged == [] and saved == before
    with pytest.raises(ValueError):
        api.normalize_operator_source_dimension(raw, field=key)


@pytest.mark.parametrize(("key", "raw", "expected"), [
    ("w", "800.0000000001", 800.0000000001),
    ("h", "1600.25", 1600.25),
    ("d", "350.125", 350.125),
    ("t", "2.375", 2.375),
])
def test_global_stages_exact_engine_physical_value_without_ui_rounding(key, raw, expected):
    host, saved, staged = _host()
    before = deepcopy(saved)
    Phase6SettingsPanel._on_left_numeric_changed(host, key, Var(raw))
    assert staged == [(key, api.normalize_operator_source_dimension(raw, field=key))]
    assert staged[0][1] == expected
    assert saved == before


def test_global_equivalent_source_is_not_re_staged():
    host, saved, staged = _host()
    Phase6SettingsPanel._on_left_numeric_changed(host, "w", Var("800.000"))
    assert staged == [] and saved["w"] == 800.0


@pytest.mark.parametrize("raw", [
    True, False, "nan", "Infinity", "-inf", "bad", None,
])
def test_right_numeric_inspector_rejects_bad_fold_source(raw):
    host, saved, staged = _host()
    spec = SettingSpec("zl1", "折邊", ("box_body",), "mm", "normal", 15.0)
    Phase6SettingsPanel._on_setting_var_changed(host, "zl1", Var(raw), spec)
    assert staged == [] and saved["zl1"] == 15.0


@pytest.mark.parametrize(("key", "raw"), [
    ("zl1", "-2.125"),
    ("door_fold_l", "0"),
    ("zl1", "27.375"),
])
def test_right_inspector_preserves_engine_legal_negative_and_fractional_fold(key, raw):
    host, saved, staged = _host()
    spec = SettingSpec(key, "折邊", ("door",), "mm", "normal", 19.0)
    Phase6SettingsPanel._on_setting_var_changed(host, key, Var(raw), spec)
    assert staged == [(key, api.normalize_operator_settings_updates(saved, {key: raw})[key])]


@pytest.mark.parametrize("raw", ["nan", "0", "-1", True])
def test_right_physical_t_is_not_staged_on_invalid_source(raw):
    host, saved, staged = _host()
    spec = SettingSpec("t", "板厚", ("box_body",), "mm", "normal", 2.0)
    Phase6SettingsPanel._on_setting_var_changed(host, "t", Var(raw), spec)
    assert staged == [] and saved["t"] == 2.0


@pytest.mark.parametrize(("raw", "expected"), [
    ("false", False), ("0", False), (0, False),
    ("true", True), ("1", True), (1, True),
])
def test_right_boolean_source_uses_engine_not_truthiness(raw, expected):
    host, saved, staged = _host()
    spec = SettingSpec("enabled", "勾選", ("box_body",), "", "bool", True)
    Phase6SettingsPanel._on_setting_var_changed(host, "enabled", Var(raw), spec)
    assert staged == [("enabled", expected)]
    assert saved["enabled"] is True


def test_real_tk_global_controls_reject_nan_and_keep_fractional_t():
    import tkinter as tk
    from tkinter import ttk
    root = tk.Tk()
    root.withdraw()
    try:
        saved = {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0,
                 "ui_text_size": "small"}
        staged = []
        panel = Phase6SettingsPanel(
            values_snapshot=lambda: deepcopy(saved),
            stage_setting_update=lambda key, value: staged.append((key, value)),
            flush_settings=lambda: None,
            save_defaults=lambda _context: True,
        )
        panel.build_left_global_controls(
            ttk.Frame(root), baseline_models=("自訂",), initial_model="自訂",
        )
        panel.left_global_vars["t"].set("nan")
        panel.left_global_vars["w"].set("0")
        assert staged == [] and saved["t"] == 2.0 and saved["w"] == 800.0
        panel.left_global_vars["t"].set("2.375")
        panel.left_global_vars["w"].set("800.0000000001")
        assert ("t", 2.375) in staged
        assert ("w", 800.0000000001) in staged
    finally:
        root.destroy()


def test_settings_panel_never_casts_manufacturing_numeric_before_engine():
    left = inspect.getsource(Phase6SettingsPanel._on_left_numeric_changed)
    right = inspect.getsource(Phase6SettingsPanel._on_setting_var_changed)
    assert "normalize_operator_source_dimension(" in left
    assert "normalize_operator_source_dimension(" in right
    assert "normalize_operator_settings_updates(" in right
    assert "normalize_operator_settings_boolean(" in right
    assert "value = float(raw)" not in right
    assert "value = float(var.get())" not in left
