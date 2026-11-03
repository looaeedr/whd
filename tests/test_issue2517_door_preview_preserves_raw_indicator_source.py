"""#2517: drawing a door-layout preview must never rewrite manufacturing input."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from gui_modules.application import door_render_host_adapter as view
from gui_modules.parts.panels.door import normalize_door_indicator_state


def _var(value):
    return SimpleNamespace(get=lambda: value)


def _draw_preview(monkeypatch, saved_states, *, key="0:0"):
    calls = []
    features = ["existing-hole"]

    def project(result, source_features, indicator_state, **kwargs):
        calls.append((result, source_features, indicator_state, kwargs))
        return ("drawn",)

    monkeypatch.setattr(
        manufacturing_api, "project_operator_door_cell_features", project,
    )
    host = SimpleNamespace(
        door_layout_indicator_states=saved_states,
        door_layout_features={key: features},
        _normalize_door_indicator_state=normalize_door_indicator_state,
        _door_layout_indicator_state_for_key=lambda _:
            pytest.fail("preview must not invoke in-place display source repair"),
        _baseline_source_model=lambda: "受電箱",
        fw_z_var=_var("29"),
        t_var=_var("2"),
        door_gap_w_var=_var("3.5"),
        door_gap_h_var=_var("3.5"),
        door_fold_l_var=_var("15"),
        door_fold_b_var=_var("15"),
    )
    cell = SimpleNamespace(
        start_width=600.0, start_height=900.0, edges=object(),
    )
    result = object()
    assert view._door_layout_cell_resolved_features(
        host, cell, result, key,
    ) == ("drawn",)
    assert len(calls) == 1
    assert calls[0][0] is result
    assert calls[0][1] is features
    return calls[0][2]


@pytest.mark.parametrize("invalid", (
    {"layers": True},
    {"layers": 0},
    {"groups": [False, 2]},
    {"groups": [9, 2]},
    {"offset_x": "nan"},
    {"offset_y": True},
))
def test_preview_sends_raw_bad_source_to_engine_without_making_cutting_valid(
    monkeypatch, invalid,
):
    raw = {
        "mode": "indicator", "layers": 2, "groups": [3, 2, 2, 2, 2, 2],
        "offset_x": 1.25, "offset_y": -2.5, "is_box_dist": False,
    }
    raw.update(invalid)
    original = deepcopy(raw)
    source = {"0:0": raw}
    rendered = _draw_preview(monkeypatch, source)

    # The physical Engine must receive the exact source, including invalid
    # values. A distinct UI view may display repaired values but must never
    # promote them to a valid DoorPartSpec/CUTTING source.
    assert rendered is raw
    assert rendered == original
    display_only = normalize_door_indicator_state(original)
    assert display_only is not rendered
    assert source == {"0:0": original}
    assert source["0:0"] is raw
    with pytest.raises(ValueError):
        manufacturing_api.project_operator_door_cell_indicator_manufacturing_source(
            source["0:0"],
        )


def test_missing_door_cell_preview_does_not_create_manufacturing_source(monkeypatch):
    saved = {}
    shown = _draw_preview(monkeypatch, saved)
    assert shown is None
    assert saved == {}


def test_valid_preview_uses_detached_display_without_rewriting_json_source(monkeypatch):
    raw = {
        "mode": "indicator_box", "layers": "1", "groups": [2, 2],
        "offset_x": "-1.25", "offset_y": "3.5", "is_box_dist": False,
    }
    before = json.dumps(raw, sort_keys=True)
    shown = _draw_preview(monkeypatch, {"0:0": raw})
    assert shown is raw
    assert shown["layers"] == "1"
    assert shown["offset_x"] == "-1.25"
    # A separate presentation normalization may render numeric strings but
    # must not replace the raw object passed into Engine or persisted to disk.
    presentation = normalize_door_indicator_state(shown)
    assert presentation["mode"] == "indicator_box"
    assert presentation["layers"] == 1
    assert presentation["offset_x"] == -1.25
    assert presentation is not raw
    assert json.dumps(raw, sort_keys=True) == before


def test_preview_source_does_not_call_mutating_accessor():
    source = inspect.getsource(view._door_layout_cell_resolved_features)
    assert "_door_layout_indicator_state_for_key(" not in source
    assert "_normalize_door_indicator_state(" not in source
    assert "states.get(key)" in source
    assert "manufacturing_api.project_operator_door_cell_features(" in source
