# -*- coding: utf-8 -*-
"""#2517: main GUI physical presence flags consume public Engine raw boolean API."""
from __future__ import annotations

from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui import Phase6ApplicationHost as GUI


class Var:
    def __init__(self, raw):
        self.raw = raw

    def get(self):
        return self.raw


class Entry:
    def __init__(self):
        self.states = []

    def configure(self, **kwargs):
        self.states.append(kwargs)


def _inner_door_host(raw, *, checkbox=True):
    rows = [{
        "cell_key": "0:0", "stable_id": "upper",
        "inward_offset_mm": 60.25, "included_frame_sides": ["top", "left"],
        "nfb_draft_selection": {"version": "saved"},
    }]
    entry = Entry()
    events = []
    host = SimpleNamespace(
        baseline_var=Var("受電箱"),
        receiving_inner_doors=deepcopy(rows),
        door_layout_inner_door_vars={"0:0": Var(raw)} if checkbox else {},
        door_layout_inner_door_offset_entries={"0:0": entry},
        _derived_cache_owner=SimpleNamespace(
            invalidate=lambda reason: events.append(("invalidate", reason))
        ),
        _phase6_update_scheduler=SimpleNamespace(
            mark_dirty=lambda reason: events.append(("dirty", reason))
        ),
        canvas_door=object(),
        draw_door_layout_overview=lambda: events.append(("draw",)),
    )
    host._set_receiving_inner_door_enabled = (
        lambda key, enabled: GUI._set_receiving_inner_door_enabled(
            host, key, enabled
        )
    )
    return host, entry, events


@pytest.mark.parametrize("raw,expected", [
    (False, False), (0, False), ("false", False), ("FALSE", False),
    ("0", False), ("off", False), (True, True), (1, True),
    ("true", True), ("1", True), ("on", True),
])
def test_main_gui_checkbox_matches_public_engine_atomic_presence(raw, expected):
    host, entry, events = _inner_door_host(raw)
    previous = deepcopy(host.receiving_inner_doors)
    expected_rows = api.apply_operator_receiving_inner_door_presence(
        {"model": "受電箱"}, previous,
        cell_key="0:0", enabled=api.normalize_operator_settings_boolean(raw),
    )
    assert GUI._commit_receiving_inner_door_checkbox(host, "0:0") is expected
    assert host.receiving_inner_doors == expected_rows
    assert entry.states == [{"state": "normal" if expected else "disabled"}]
    assert events == [("invalidate", "geometry"), ("dirty", "inner_door"), ("draw",)]


@pytest.mark.parametrize("raw", [
    None, "false-ish", "2", "nan", float("nan"), float("inf"),
    2, -1, 0.5, [], {},
])
def test_invalid_inner_door_flag_cannot_mutate_source_or_ui(raw):
    host, entry, events = _inner_door_host(raw)
    original = deepcopy(host.receiving_inner_doors)
    with pytest.raises(ValueError):
        GUI._commit_receiving_inner_door_checkbox(host, "0:0")
    assert host.receiving_inner_doors == original
    assert entry.states == []
    assert events == []


def test_missing_inner_door_checkbox_is_not_a_physical_disable():
    host, entry, events = _inner_door_host(None, checkbox=False)
    original = deepcopy(host.receiving_inner_doors)
    with pytest.raises(ValueError, match="選取控制不存在"):
        GUI._commit_receiving_inner_door_checkbox(host, "0:0")
    assert host.receiving_inner_doors == original
    assert entry.states == []
    assert events == []


@pytest.mark.parametrize("raw,expect_enabled", [
    (True, True), ("true", True), (1, True),
    (False, False), ("false", False), ("off", False), (0, False),
])
def test_indicator_box_physical_pair_matches_engine_flag(raw, expect_enabled):
    events = []
    host = SimpleNamespace(
        is_indicator_box_var=Var(raw),
        _disable_all_door_indicators=lambda: events.append(("disable_direct",)),
        _phase6_set_part_presence=lambda key, enabled: events.append(
            ("presence", key, enabled)
        ),
        _request_phase6_update=lambda reason: events.append(("update", reason)),
    )
    GUI.on_indicator_box_toggle(host)
    expected = ([("disable_direct",)] if expect_enabled else []) + [
        ("presence", "indicator_box", expect_enabled),
        ("presence", "indicator_door", expect_enabled),
        ("update", "geometry"),
    ]
    assert events == expected


@pytest.mark.parametrize("raw", ["maybe", "nan", 2, None, {}, float("inf")])
def test_bad_indicator_box_flag_does_not_change_any_physical_part(raw):
    events = []
    host = SimpleNamespace(
        is_indicator_box_var=Var(raw),
        _disable_all_door_indicators=lambda: events.append("disable"),
        _phase6_set_part_presence=lambda key, value: events.append(key),
        _request_phase6_update=lambda reason: events.append(reason),
    )
    with pytest.raises(ValueError):
        GUI.on_indicator_box_toggle(host)
    assert events == []


@pytest.mark.parametrize("raw,enabled", [
    ("false", False), ("off", False), (False, False),
    ("true", True), (True, True), (1, True),
])
def test_direct_door_indicator_is_not_enabled_by_false_string(raw, enabled):
    events = []
    host = SimpleNamespace(
        is_door_indicator_var=Var(raw),
        _disable_indicator_box_for_door_indicator=lambda: events.append("disable_box"),
        _request_phase6_update=lambda reason: events.append(reason),
    )
    GUI.on_door_indicator_toggle(host)
    assert events == (["disable_box"] if enabled else []) + ["geometry"]


@pytest.mark.parametrize("raw", [None, "maybe", "2", 2, float("nan")])
def test_bad_door_indicator_does_not_disable_box_or_schedule_geometry(raw):
    events = []
    host = SimpleNamespace(
        is_door_indicator_var=Var(raw),
        _disable_indicator_box_for_door_indicator=lambda: events.append("disable_box"),
        _request_phase6_update=lambda reason: events.append(reason),
    )
    with pytest.raises(ValueError):
        GUI.on_door_indicator_toggle(host)
    assert events == []


def test_real_tk_booleanvar_route_works_with_public_engine():
    import tkinter as tk
    root = tk.Tk()
    root.withdraw()
    try:
        var = tk.BooleanVar(master=root, value=True)
        host, entry, events = _inner_door_host(None)
        host.door_layout_inner_door_vars = {"0:0": var}
        assert GUI._commit_receiving_inner_door_checkbox(host, "0:0") is True
        assert host.receiving_inner_doors[0]["stable_id"] == "upper"
        var.set(False)
        assert GUI._commit_receiving_inner_door_checkbox(host, "0:0") is False
        assert host.receiving_inner_doors == []
        assert entry.states == [{"state": "normal"}, {"state": "disabled"}]
    finally:
        root.destroy()


def test_source_guards_no_gui_truthiness_for_physical_presence():
    inner = inspect.getsource(GUI._commit_receiving_inner_door_checkbox)
    box = inspect.getsource(GUI.on_indicator_box_toggle)
    door = inspect.getsource(GUI.on_door_indicator_toggle)
    for source in (inner, box, door):
        assert "manufacturing_api.normalize_operator_settings_boolean(" in source
        assert "bool(" not in source
    assert "if var is None:" in inner
    assert "else False" not in inner
