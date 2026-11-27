"""#2517: GUI passes original Indicator state to one headless Engine fit API."""
from copy import deepcopy
import inspect
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from gui_modules.application import manufacturing_adapter as adapter


def state(mode="indicator_box"):
    return {
        "mode": mode, "layers": "2", "groups": ["3", "2", "unused"],
        "offset_x": "-1.25", "offset_y": "2.75", "is_box_dist": "false",
    }


@pytest.mark.parametrize("mode", ("indicator", "indicator_box"))
def test_headless_raw_state_fit_matches_existing_canonical_engine_fit(mode):
    raw = state(mode)
    original = deepcopy(raw)
    projected = api.project_operator_door_cell_indicator_manufacturing_source(raw)
    expected = api.validate_door_indicator_fit(
        mode=mode, groups=tuple(projected["groups"][:projected["layers"]]),
        finished_width=5000.125, finished_height=4800.375,
        thickness="2.125", offset=(projected["offset_x"], projected["offset_y"]),
    )
    direct = api.validate_operator_indicator_state_fit(
        raw, finished_width=5000.125, finished_height=4800.375,
        thickness="2.125",
    )
    assert direct == pytest.approx(expected)
    assert direct[0] > 0 and direct[1] > 0
    assert raw == original


@pytest.mark.parametrize("invalid", (
    {"layers": True}, {"layers": "7"}, {"groups": [False, 2]},
    {"groups": ["0", 2]}, {"offset_x": float("nan")},
    {"offset_y": True}, {"is_box_dist": "bogus"}, {"mode": "wrong"},
))
def test_headless_raw_state_fit_fails_closed_without_mutating_source(invalid):
    raw = state()
    raw.update(invalid)
    before = deepcopy(raw)
    with pytest.raises(ValueError):
        api.validate_operator_indicator_state_fit(
            raw, finished_width=5000, finished_height=5000,
            thickness=2.0,
        )
    assert raw == before


@pytest.mark.parametrize("bad_field,bad", (
    ("finished_width", True), ("finished_height", float("nan")),
    ("thickness", False),
))
def test_headless_raw_state_fit_rejects_bad_active_dimensions(bad_field, bad):
    kwargs = dict(finished_width=5000, finished_height=5000, thickness=2)
    kwargs[bad_field] = bad
    with pytest.raises((ValueError, TypeError)):
        api.validate_operator_indicator_state_fit(state(), **kwargs)


def test_disabled_legacy_indicator_source_does_not_create_physical_fit():
    raw = {"mode": "none", "layers": "broken", "groups": [True],
           "offset_x": float("nan")}
    before = deepcopy(raw)
    assert api.validate_operator_indicator_state_fit(
        raw, finished_width=float("nan"), finished_height=False,
        thickness=0,
    ) == (0.0, 0.0)
    assert raw == before


def test_gui_forwards_original_indicator_source_without_group_or_mode_solver(monkeypatch):
    raw = state("indicator")
    forwarded = []
    sentinel = (17.0, 29.0)
    def public_api(source, **kwargs):
        forwarded.append((source, kwargs))
        return sentinel
    monkeypatch.setattr(api, "validate_operator_indicator_state_fit", public_api)
    result = adapter._validate_indicator_state_fit(
        SimpleNamespace(), raw, finished_width=450, finished_height=650, thickness=2,
    )
    assert result is sentinel
    assert forwarded == [(raw, {
        "finished_width": 450, "finished_height": 650, "thickness": 2,
    })]
    assert forwarded[0][0] is raw
    source = inspect.getsource(adapter._validate_indicator_state_fit)
    assert "validate_operator_indicator_state_fit(" in source
    assert '["groups"][:' not in source
    assert '["mode"]' not in source
