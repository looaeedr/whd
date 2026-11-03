"""#2517: Fold Designer saved Indicator offsets are the Engine Hole Editor offsets."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
import inspect
import json
import math

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import fold_designer_snapshot_dimensions as owner
from gui_modules.application import fold_designer_snapshot_projection as gui


def _snapshot(model="金庫型"):
    return {
        "model": model, "w": 800., "h": 1600., "d": 350.,
        "t": 2., "fw": 29., "door_gap_w": 3.5, "door_gap_h": 3.5,
        "base_plate_shrink_left": 55., "base_plate_shrink_right": 55.,
        "base_plate_shrink_top": 55., "base_plate_shrink_bottom": 55.,
        "indicator_box_fold": 49., "indicator_door_fold": 19.,
    }


def _controls(x=0., y=0., *, enabled=True):
    def var(value):
        return SimpleNamespace(get=lambda: value)
    return SimpleNamespace(
        indicator_l_var=var(1),
        indicator_layer_g_vars=[var(2)],
        is_door_indicator_var=var(enabled),
        door_indicator_l_var=var(1),
        door_indicator_layer_g_vars=[var(2)],
        is_indicator_box_var=var(True),
        door_indicator_offset_x=x, door_indicator_offset_y=y,
    )


@pytest.mark.parametrize("model", ["金庫型", "受電箱"])
@pytest.mark.parametrize("x,y", [
    (0, 0), ("-12.375", "27.25"), (55.5, -9.875), (-0.25, 0.0),
])
def test_gui_save_reload_matches_headless_hole_editor_for_finite_offsets(
    model, x, y,
):
    source = _snapshot(model)
    before = deepcopy(source)
    validated = api.normalize_fold_designer_indicator_offsets(x, y)
    assert owner.normalize_fold_designer_indicator_offsets(x, y) == validated
    hole_source = api.normalize_operator_hole_editor_indicator_state({
        "mode": "indicator", "layers": 1, "groups": [2],
        "offset_x": x, "offset_y": y, "is_box_dist": False,
    })
    assert (hole_source["offset_x"], hole_source["offset_y"]) == validated
    assert gui._snapshot_part_dimensions(_controls(x, y), source) is source
    assert source["door_indicator_offset"] == validated
    assert json.loads(json.dumps(source))["door_indicator_offset"] == list(validated)
    assert all(math.isfinite(v) for v in validated)
    assert before.keys() <= source.keys()


@pytest.mark.parametrize("axis", ["x", "y"])
@pytest.mark.parametrize("invalid", [
    True, False, "nan", "-inf", "Infinity", float("nan"),
    float("inf"), float("-inf"), "garbage", None,
])
def test_invalid_live_offset_rejected_before_any_project_snapshot_update(axis, invalid):
    source = _snapshot("受電箱")
    original = deepcopy(source)
    x, y = (invalid, 0) if axis == "x" else (0, invalid)
    with pytest.raises(ValueError, match="指示燈.*偏移"):
        api.normalize_fold_designer_indicator_offsets(x, y)
    with pytest.raises(ValueError, match="指示燈.*偏移"):
        gui._snapshot_part_dimensions(_controls(x, y), source)
    assert source == original
    with pytest.raises(ValueError, match="指示燈.*偏移"):
        api.normalize_operator_hole_editor_indicator_state({
            "mode": "indicator", "layers": 1, "groups": [2],
            "offset_x": x, "offset_y": y, "is_box_dist": False,
        })


def test_disabled_controls_preserve_existing_snapshot_semantics():
    result = _snapshot()
    assert gui._snapshot_part_dimensions(
        _controls("-3.125", "1.5", enabled=False), result,
    )["door_indicator_offset"] == (-3.125, 1.5)
    assert result["door_indicator_groups"] == []


def test_gui_only_calls_engine_not_second_offset_conversion(monkeypatch):
    calls = []
    original = api.normalize_fold_designer_indicator_offsets

    def spy(x, y):
        calls.append((x, y))
        return original(x, y)

    monkeypatch.setattr(api, "normalize_fold_designer_indicator_offsets", spy)
    gui._snapshot_part_dimensions(_controls("12.125", "-1.25"), _snapshot())
    assert calls == [("12.125", "-1.25")]
    code = inspect.getsource(gui._snapshot_part_dimensions)
    assert "manufacturing_api.normalize_fold_designer_indicator_offsets(" in code
    assert "float(self.door_indicator_offset_x)" not in code
    assert "float(self.door_indicator_offset_y)" not in code
    assert "from gui_modules" not in inspect.getsource(owner)
