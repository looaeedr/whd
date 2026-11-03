"""#2517 single-door live Indicator source uses the existing strict Engine API."""
from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from gui_modules.application import manufacturing_adapter
from gui_modules.parts.panels.door import normalize_door_indicator_state
from gui_modules.project import export_actions


def _var(value):
    return SimpleNamespace(get=lambda: value)


def _host(*, mode="indicator", layers="2", groups=None, x="-1.25", y="2.75", box_dist=False):
    if groups is None:
        groups = ["3", "2", "2", "2", "2", "2"]
    return SimpleNamespace(
        is_indicator_box_var=_var(mode == "indicator_box"),
        is_door_indicator_var=_var(mode == "indicator"),
        indicator_l_var=_var(layers),
        door_indicator_l_var=_var(layers),
        indicator_layer_g_vars=[_var(v) for v in groups],
        door_indicator_layer_g_vars=[_var(v) for v in groups],
        door_indicator_offset_x=x,
        door_indicator_offset_y=y,
        is_box_dist_var=_var(box_dist),
        _normalize_door_indicator_state=lambda state:
            pytest.fail("enabled physical source must not use GUI display repair"),
    )


@pytest.mark.parametrize("mode", ["indicator", "indicator_box"])
def test_live_single_door_snapshot_is_exact_engine_hole_editor_source(mode):
    host = _host(mode=mode)
    snapshot = export_actions._single_door_indicator_state_snapshot(host)
    expected = manufacturing_api.normalize_operator_hole_editor_indicator_state({
        "mode": mode, "layers": "2", "groups": ["3", "2"] + ["2"] * 4,
        "offset_x": "-1.25", "offset_y": "2.75", "is_box_dist": False,
    })
    for key, value in expected.items():
        assert snapshot[key] == value
    assert snapshot["enabled"] == (mode == "indicator")
    assert snapshot["box_enabled"] == (mode == "indicator_box")


@pytest.mark.parametrize("bad", (
    {"layers": True}, {"layers": 0}, {"layers": 1.5},
    {"layers": "7"}, {"groups": [False, 2, 2, 2, 2, 2]},
    {"groups": [0, 2, 2, 2, 2, 2]},
    {"groups": ["9", "2", "2", "2", "2", "2"]},
    {"groups": ["garbage", "2", "2", "2", "2", "2"]},
    {"x": True}, {"x": "nan"}, {"y": float("inf")},
    {"box_dist": "garbage"},
))
def test_invalid_live_single_door_holes_fail_closed_before_repair(bad):
    for mode in ("indicator", "indicator_box"):
        host = _host(mode=mode, **bad)
        with pytest.raises(ValueError):
            export_actions._single_door_indicator_state_snapshot(host)


def test_disabled_single_door_retains_legacy_display_compatibility():
    host = _host(mode="none", layers="9", groups=["bad"] * 6)
    host._normalize_door_indicator_state = normalize_door_indicator_state
    state = export_actions._single_door_indicator_state_snapshot(host)
    assert state["mode"] == "none"
    assert state["groups"] == [2] * 6
    assert state["layers"] == 6


def test_fit_uses_strict_engine_gate_not_gui_sanitizing(monkeypatch):
    calls = []

    def validate(**params):
        calls.append(params)
        return (55.0, 75.0)

    monkeypatch.setattr(manufacturing_api, "validate_door_indicator_fit", validate)
    host = SimpleNamespace(
        _normalize_door_indicator_state=lambda _:
            pytest.fail("GUI display normalization must not authorize hole geometry"),
    )
    valid = {
        "mode": "indicator", "layers": "2", "groups": ["3", "2"],
        "offset_x": "-1.25", "offset_y": 2.75, "is_box_dist": False,
    }
    assert manufacturing_adapter._validate_indicator_state_fit(
        host, valid, finished_width=400.0, finished_height=600.0, thickness=2.0,
    ) == (55.0, 75.0)
    assert calls == [{
        "mode": "indicator", "groups": (3, 2),
        "finished_width": 400.0, "finished_height": 600.0,
        "thickness": 2.0, "offset": (-1.25, 2.75),
    }]
    with pytest.raises(ValueError):
        manufacturing_adapter._validate_indicator_state_fit(
            host, {**valid, "groups": [True, 2]},
            finished_width=400.0, finished_height=600.0, thickness=2.0,
        )
    assert len(calls) == 1


def test_disabled_fit_has_no_holes_even_with_stale_hidden_controls():
    host = SimpleNamespace(_normalize_door_indicator_state=lambda _:
        pytest.fail("no GUI display repair"))
    assert manufacturing_adapter._validate_indicator_state_fit(
        host, {"mode": "none", "layers": "bogus"},
        finished_width=400.0, finished_height=600.0, thickness=2.0,
    ) == (0.0, 0.0)


def test_source_has_no_gui_live_integer_clamp_or_default():
    single = inspect.getsource(export_actions._single_door_indicator_state_snapshot)
    live = single[:single.index('if mode != "none":') + 15]
    assert "normalize_operator_hole_editor_indicator_state(" in single
    fit = inspect.getsource(manufacturing_adapter._validate_indicator_state_fit)
    assert "project_operator_door_cell_indicator_manufacturing_source(" in fit
    assert "_normalize_door_indicator_state(" not in fit
    assert "max(1, min(6, int(" not in fit
