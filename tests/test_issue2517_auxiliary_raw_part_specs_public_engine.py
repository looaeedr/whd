"""#2517: GUI preview and headless auxiliary physical sources share strict Engine gates."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.operator_auxiliary_part_specs import (
    resolve_fold_designer_base_plate_source,
)
from gui_modules.application.render_snapshots import (
    base_plate_render_snapshot,
    single_door_render_snapshot,
)


def _base_values():
    return {
        "model": "金庫型", "w": "800.625", "h": 1600, "t": "2.125",
        "fw": 25, "base_plate_shrink_top": "5.125",
        "base_plate_shrink_bottom": 6, "base_plate_shrink_left": "-0.25",
        "base_plate_shrink_right": 8, "base_plate_bend": "-15.375",
    }


def _var(value):
    return SimpleNamespace(get=lambda: value)


def test_headless_legacy_baseplate_preserves_valid_source_and_reload():
    source = _base_values()
    old = deepcopy(source)
    spec = api.build_base_plate_operator_part_spec(source, features=())
    assert (spec.width, spec.height, spec.thickness) == (800.625, 1600.0, 2.125)
    assert (spec.shrink_top, spec.shrink_left, spec.bend) == (5.125, -0.25, -15.375)
    assert api.build_base_plate_operator_part_spec(
        json.loads(json.dumps(source)), features=(),
    ) == spec
    assert source == old


@pytest.mark.parametrize(("key", "bad"), (
    ("w", True), ("h", 0), ("t", float("nan")),
    ("base_plate_shrink_top", True),
    ("base_plate_shrink_bottom", "nan"),
    ("base_plate_shrink_left", float("inf")),
    ("base_plate_shrink_right", object()),
    ("base_plate_bend", False),
))
def test_headless_auxiliary_part_spec_rejects_original_invalid_source(key, bad):
    values = _base_values()
    values[key] = bad
    original = deepcopy(values)
    with pytest.raises((ValueError, TypeError, OverflowError)):
        api.build_base_plate_operator_part_spec(values, features=())
    assert values == original


@pytest.mark.parametrize("bad", (True, False, "nan", "inf", 0, -1, None))
def test_indicatorbox_part_spec_t_is_physical_engine_dimension(bad):
    with pytest.raises((ValueError, TypeError, OverflowError)):
        api.build_indicator_box_operator_part_spec({"t": bad}, ("2",), features=())
    good = api.build_indicator_box_operator_part_spec(
        {"t": "2.125"}, ("2",), features=(),
    )
    assert good.thickness == 2.125


@pytest.mark.parametrize(("key", "bad"), (
    ("width", True), ("height", 0), ("thickness", False),
    ("frame_width", float("nan")), ("base_plate_bend", True),
    ("base_plate_shrink_top", float("inf")),
))
def test_fold_designer_engine_source_rejects_early_float_alias(key, bad):
    fields = dict(width=800, height=1600, thickness=2.0, frame_width=25.0)
    snapshot = {"base_plate_bend": 15.0, "base_plate_shrink_top": 5.0}
    if key in fields:
        fields[key] = bad
    else:
        snapshot[key] = bad
    with pytest.raises(ValueError):
        resolve_fold_designer_base_plate_source(
            "base_plate", snapshot, model_name="金庫型", **fields,
        )


@pytest.mark.parametrize(("bad_field", "bad_value"), (
    ("base_plate_shrink_left", True),
    ("base_plate_bend", float("nan")),
))
def test_legacy_2d_baseplate_forwards_raw_to_engine_before_render(bad_field, bad_value):
    values = _base_values()
    calls = []
    host = SimpleNamespace(fold_designer_app=None)
    for field in (
        "base_plate_shrink_top", "base_plate_shrink_bottom",
        "base_plate_shrink_left", "base_plate_shrink_right", "base_plate_bend",
    ):
        setattr(host, field + "_var", _var(bad_value if field == bad_field else values[field]))

    def build(raw):
        calls.append(raw.copy())
        return api.build_base_plate_operator_part_spec(raw, features=())

    host._base_plate_part_spec = build
    host._manufacturing_context = lambda **kwargs: pytest.fail("bad source was rendered")
    host._authoritative_render_data = lambda *args: pytest.fail("bad source was rendered")
    with pytest.raises(ValueError):
        base_plate_render_snapshot(host, values)
    assert len(calls) == 1
    assert calls[0][bad_field] is bad_value
    assert values == _base_values()


def test_single_door_2d_preserves_raw_fold_until_existing_door_engine_validation():
    from ae_engine.manufacturing_api import build_door_operator_part_spec

    seen = []
    source = {
        "w": "800", "h": "1600", "t": "2", "fw": "25",
        "door_gap_w": "3.5", "door_gap_h": "3.5",
        "door_fold_l": True, "door_fold_r": "19",
        "door_fold_t": "15", "door_fold_b": "15",
    }
    host = SimpleNamespace(
        w_var=_var(source["w"]), h_var=_var(source["h"]),
        t_var=_var(source["t"]), fw_z_var=_var(source["fw"]),
        is_indicator_box_var=_var(False), is_door_indicator_var=_var(False),
    )
    for field in (
        "door_gap_w", "door_gap_h", "door_fold_l", "door_fold_r",
        "door_fold_t", "door_fold_b",
    ):
        setattr(host, field + "_var", _var(source[field]))

    def build(raw, **kwargs):
        seen.append(dict(raw))
        return build_door_operator_part_spec(raw, model_name="金庫型")

    host._single_door_part_spec = build
    host._manufacturing_context = lambda **kwargs: pytest.fail("bad Door was rendered")
    with pytest.raises(ValueError, match="DOOR_OPERATOR_SOURCE_INVALID"):
        single_door_render_snapshot(host)
    assert seen[0]["door_fold_l"] is True

    gui_source = inspect.getsource(single_door_render_snapshot)
    assert "float(host.door_fold_l_var.get())" not in gui_source
    assert "float(host.door_gap_w_var.get())" not in gui_source
