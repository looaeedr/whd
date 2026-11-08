# -*- coding: utf-8 -*-
"""#2517 SETTINGS checkbox construction/sync must preserve raw Engine booleans."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from phase6_settings_center import settings_for_context
from phase6_settings_panel import Phase6SettingsPanel


def _panel(snapshot):
    staged = []
    panel = Phase6SettingsPanel(
        values_snapshot=lambda: deepcopy(snapshot),
        stage_setting_update=lambda key, value: staged.append((key, value)),
        flush_settings=lambda: None,
        save_defaults=lambda context: None,
    )
    return panel, staged


def _stock_spec():
    return next(spec for spec in settings_for_context("global")
                if spec.key == "draw_stock")


@pytest.mark.parametrize("raw,enabled", [
    ("false", False), ("False", False), ("0", False), ("off", False),
    (0, False), (False, False),
    ("true", True), ("TRUE", True), ("1", True), ("on", True),
    (1, True), (True, True),
])
@pytest.mark.parametrize("owner", ["normal", "inspector"])
def test_real_settings_checkbox_matches_headless_engine_raw_source(raw, enabled, owner):
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.withdraw()
    try:
        snapshot = json.loads(json.dumps({"draw_stock": raw}))
        original = deepcopy(snapshot)
        panel, staged = _panel(snapshot)
        parent = ttk.Frame(root)
        if owner == "normal":
            panel._add_setting_widget(parent, _stock_spec(), 0, 0)
        else:
            panel._add_inspector_property_row(parent, _stock_spec(), 0)
        var = panel.setting_vars["draw_stock"]
        assert isinstance(var, tk.BooleanVar)
        assert var.get() is enabled
        assert var.get() is manufacturing_api.normalize_operator_settings_boolean(raw)
        assert snapshot == original and staged == []
    finally:
        root.destroy()


@pytest.mark.parametrize("raw", [None, "false-ish", "2", 2, 0.5, [], {},
                                 float("nan"), float("inf")])
@pytest.mark.parametrize("owner", ["normal", "inspector"])
def test_bad_saved_stock_cannot_become_a_checked_manufacturing_setting(raw, owner):
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.withdraw()
    try:
        snapshot = {"draw_stock": raw}
        panel, staged = _panel(snapshot)
        before = repr(snapshot)
        parent = ttk.Frame(root)
        with pytest.raises(ValueError):
            if owner == "normal":
                panel._add_setting_widget(parent, _stock_spec(), 0, 0)
            else:
                panel._add_inspector_property_row(parent, _stock_spec(), 0)
        assert "draw_stock" not in panel.setting_vars
        assert repr(snapshot) == before and staged == []
    finally:
        root.destroy()


@pytest.mark.parametrize("raw,expected", [
    ("false", False), ("0", False), ("true", True), ("1", True),
])
def test_sync_values_updates_real_tk_stock_without_staging(raw, expected):
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        stock = tk.BooleanVar(master=root, value=not expected)
        stock_global = tk.BooleanVar(master=root, value=not expected)
        label = tk.StringVar(master=root, value="800")
        events = []
        host = SimpleNamespace(
            page_cache={"global": {"setting_vars": {"w": label, "draw_stock": stock}}},
            left_global_vars={"draw_stock": stock_global},
            _guard=False,
            refresh_panel_name=lambda: events.append("refresh"),
        )
        source = json.loads(json.dumps({"w": 801, "draw_stock": raw}))
        Phase6SettingsPanel.sync_values(host, source)
        assert stock.get() is expected and stock_global.get() is expected
        assert label.get() == "801"
        assert events == ["refresh"] and host._guard is False
        assert source["draw_stock"] == raw
    finally:
        root.destroy()


@pytest.mark.parametrize("raw", ["bad", "2", 2, None, float("nan")])
def test_invalid_stock_sync_rejects_before_any_display_write(raw):
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    try:
        label = tk.StringVar(master=root, value="800")
        stock = tk.BooleanVar(master=root, value=False)
        refresh_events = []
        host = SimpleNamespace(
            page_cache={"global": {"setting_vars": {"w": label, "draw_stock": stock}}},
            left_global_vars={},
            _guard=False,
            refresh_panel_name=lambda: refresh_events.append("refresh"),
        )
        with pytest.raises(ValueError):
            Phase6SettingsPanel.sync_values(host, {"w": 900, "draw_stock": raw})
        assert label.get() == "800" and stock.get() is False
        assert host._guard is False and refresh_events == []
    finally:
        root.destroy()


def test_saved_setting_boolean_display_has_no_gui_truthiness_fallback():
    standard = inspect.getsource(Phase6SettingsPanel._add_setting_widget)
    inspector = inspect.getsource(Phase6SettingsPanel._add_inspector_property_row)
    sync = inspect.getsource(Phase6SettingsPanel.sync_values)
    assert "normalize_operator_settings_boolean(value)" in standard
    assert "normalize_operator_settings_boolean(value)" in inspector
    assert "normalize_operator_settings_boolean(snapshot[key])" in sync
    assert "value=bool(value)" not in standard + inspector
    assert "var.set(bool(value))" not in sync
