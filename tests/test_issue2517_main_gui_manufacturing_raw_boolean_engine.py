"""#2517: main-GUI manufacturing STOCK and single Door distance source parity."""
from __future__ import annotations

import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ManufacturingContext, DoorPartSpec
from gui_modules.application import manufacturing_adapter as gui


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


@pytest.mark.parametrize(("raw", "expected"), [
    (False, False), (True, True), ("false", False), ("off", False),
    ("no", False), ("0", False), ("true", True), ("on", True),
    ("yes", True), ("1", True), (0, False), (1, True),
    (0.0, False), (1.0, True),
])
def test_gui_manufacturing_context_matches_headless_engine_stock(raw, expected):
    actual = gui._manufacturing_context(SimpleNamespace(), draw_stock=raw)
    headless = ManufacturingContext(
        draw_stock=api.normalize_operator_settings_boolean(raw), overwrite=True,
    )
    assert actual == headless
    assert actual.draw_stock is expected
    assert type(actual.draw_stock) is bool


@pytest.mark.parametrize("raw", [None, "invalid", -1, 2, 0.5, float("nan"), float("inf"), object()])
def test_stock_invalid_source_rejected_before_manufacturing(raw):
    with pytest.raises(ValueError, match="布林"):
        gui._manufacturing_context(SimpleNamespace(), draw_stock=raw)


def _values():
    return {
        "w": 500.0, "h": 600.0, "t": 2.0, "fw": 25.0,
        "door_gap_w": 3.5, "door_gap_h": 3.5,
        "door_fold_l": 19.0, "door_fold_r": 19.0,
        "door_fold_t": 19.0, "door_fold_b": 19.0,
    }


def _gui_host(raw):
    calls = []
    def forward(values, **kwargs):
        calls.append((dict(values), dict(kwargs)))
        return api.build_door_operator_part_spec(values, **kwargs)
    host = SimpleNamespace(
        _door_part_spec_from_values=forward,
        _baseline_source_model=lambda: "金庫型",
        surface_features={"door": []},
        door_indicator_offset_x=0.0,
        door_indicator_offset_y=0.0,
        is_box_dist_var=Var(raw),
        _manual_corner_policy=lambda *_: None,
        _door_material_frame_width=lambda fw, t: fw,
    )
    return host, calls


@pytest.mark.parametrize(("raw", "expected"), [
    (False, False), (True, True), ("false", False), ("off", False),
    ("0", False), ("true", True), ("on", True), ("1", True),
])
def test_active_single_door_distance_gui_matches_headless_engine(raw, expected):
    host, calls = _gui_host(raw)
    actual = gui._single_door_part_spec(host, _values(), door_indicator=(2,))
    headless = api.build_door_operator_part_spec(
        _values(), model_name="金庫型", features=(),
        door_indicator=(2,), door_indicator_offset=(0.0, 0.0),
        use_box_distance=raw, corner_policy=None,
    )
    assert isinstance(actual, DoorPartSpec)
    assert actual == headless
    assert actual.use_box_distance is expected
    assert calls[0][1]["use_box_distance"] == raw


@pytest.mark.parametrize("raw", ["invalid", 2, None, float("nan"), float("inf")])
def test_active_door_distance_invalid_source_fails_without_physical_spec(raw):
    host, calls = _gui_host(raw)
    with pytest.raises(ValueError, match="布林"):
        gui._single_door_part_spec(host, _values(), door_indicator=(2,))
    assert calls[0][1]["use_box_distance"] is raw


def test_disabled_door_indicator_keeps_existing_engine_legacy_compatibility():
    host, calls = _gui_host("invalid-legacy-disabled")
    actual = gui._single_door_part_spec(host, _values())
    expected = api.build_door_operator_part_spec(
        _values(), model_name="金庫型", features=(),
        use_box_distance="invalid-legacy-disabled",
    )
    assert actual == expected
    assert actual.use_box_distance is False
    assert calls[0][1]["use_box_distance"] == "invalid-legacy-disabled"


def test_serialized_false_stock_and_door_sources_survive_save_reload():
    saved = json.loads(json.dumps({
        "draw_stock": "false", "use_box_distance": "false",
    }))
    context = gui._manufacturing_context(SimpleNamespace(), draw_stock=saved["draw_stock"])
    host, _calls = _gui_host(saved["use_box_distance"])
    spec = gui._single_door_part_spec(host, _values(), door_indicator=(2,))
    assert context.draw_stock is False and spec.use_box_distance is False
    assert saved == {"draw_stock": "false", "use_box_distance": "false"}
    transition = api.commit_operator_settings_state(
        {"draw_stock": True}, {}, {}, {"draw_stock": saved["draw_stock"]},
    )
    assert transition.committed["draw_stock"] is context.draw_stock


def test_no_gui_truthiness_coercion_on_manufacturing_boolean_sources():
    stock = inspect.getsource(gui._manufacturing_context)
    single = inspect.getsource(gui._single_door_part_spec)
    assert "draw_stock=bool(draw_stock)" not in stock
    assert "manufacturing_api.normalize_operator_settings_boolean(draw_stock)" in stock
    assert "use_box_distance=bool(self.is_box_dist_var.get())" not in single
    assert "use_box_distance=self.is_box_dist_var.get()" in single
