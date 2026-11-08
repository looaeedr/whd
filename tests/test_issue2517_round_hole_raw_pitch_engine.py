"""#2517: round Hole Editor pitch forwards raw source to Engine unchanged."""
from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.sheetmetal_feature_reference import generate_round_fill, generate_round_refill
from ae_engine.sheetmetal_features import (
    CircleFeature, FeatureAnchor, feature_surface_from_rect,
)
from ae_engine.sheetmetal_geometry import Vec2
from gui_modules.editors import hole_editor_round_settings as gui


class Field:
    def __init__(self, value):
        self.value = value
    def get(self):
        return self.value
    def set(self, value):
        self.value = value


def _source():
    hole = CircleFeature(
        diameter=10.0, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(20.0, 40.0),
    )
    return [hole], feature_surface_from_rect("door", Vec2(0, 0), Vec2(120, 80))


def _dialog(raw, driver):
    source, surface = _source()
    calls = []
    editor = gui._RoundHoleSettingsDialog.__new__(gui._RoundHoleSettingsDialog)
    editor.seed_snapshot = list(source)
    editor.idx = 0
    editor.surface = surface
    editor.width = 120.0
    editor.height = 80.0
    editor.round_direction = Field("向右")
    editor.direction_map = {"向右": "right"}
    editor.round_driver = Field(driver)
    editor.round_center = Field(raw)
    editor.round_gap = Field(raw)
    editor.round_alignment = Field("center")
    editor.neighbor_index = None
    editor.hole_session = SimpleNamespace(execute=lambda action: calls.append(action))
    editor._refresh_all = lambda: None
    editor.status_var = Field("未預覽")
    editor.dialog = None
    return editor, source, calls


@pytest.mark.parametrize("driver,bad", (
    ("center", True), ("gap", True), ("center", False), ("gap", False),
    ("center", None), ("gap", []), ("center", "nan"), ("gap", "inf"),
    ("center", "-1"), ("center", "0"), ("gap", "-0.125"),
    ("gap", -0.125), ("gap", "-9.5"), ("gap", "invalid"),
))
@pytest.mark.parametrize("refill", (False, True))
def test_invalid_raw_pitch_is_rejected_by_public_engine_before_any_hole_preview(
    driver, bad, refill, monkeypatch,
):
    editor, source, calls = _dialog(bad, driver)
    original = deepcopy(source)
    shown = []
    monkeypatch.setattr(
        gui.messagebox, "showerror",
        lambda title, message, **kwargs: shown.append((title, message)),
    )
    assert editor._driver_value() is bad
    editor._apply_pattern(refill=refill)
    assert calls == []
    assert source == original
    assert editor.status_var.get() == "未預覽"
    assert len(shown) == 1
    with pytest.raises(ValueError):
        api.plan_operator_round_hole_preview(
            source, 0, editor.surface,
            width=editor.width, height=editor.height,
            direction="right", driver=driver, value=bad, refill=refill,
        )


@pytest.mark.parametrize("driver,raw", (
    ("center", "25"), ("center", "25.625"), ("gap", "0"), ("gap", "2.125"),
))
@pytest.mark.parametrize("refill", (False, True))
def test_gui_raw_pitch_parity_and_json_reload(driver, raw, refill, monkeypatch):
    editor, source, calls = _dialog(raw, driver)
    args_seen = []
    old = api.plan_operator_round_hole_preview
    def spy(*args, **kwargs):
        args_seen.append(kwargs)
        return old(*args, **kwargs)
    monkeypatch.setattr(api, "plan_operator_round_hole_preview", spy)
    restored = json.loads(json.dumps({"driver": driver, "value": raw}))
    assert restored == {"driver": driver, "value": raw}
    editor._apply_pattern(refill=refill)
    assert len(calls) == 1
    assert args_seen[0]["value"] == raw
    assert args_seen[0]["driver"] == driver
    assert args_seen[0]["refill"] is refill
    expected = old(source, 0, editor.surface,
        width=120.0, height=80.0, direction="right",
        driver=driver, value=restored["value"], refill=refill,
    )
    assert calls[0].features == expected.features
    assert source == _source()[0]


@pytest.mark.parametrize("generator", (generate_round_fill, generate_round_refill))
def test_engine_generator_itself_rejects_negative_gap_without_source_mutation(generator):
    source, surface = _source()
    before = deepcopy(source)
    for bad in (-0.125, "-0.5"):
        with pytest.raises(ValueError, match="間距"):
            generator(
                source[0], surface, width=120.0, height=80.0,
                direction="right", driver="gap", value=bad,
            )
        assert source == before


def test_gui_does_not_erase_original_physical_pitch_source_before_public_engine():
    source = inspect.getsource(gui._RoundHoleSettingsDialog._driver_value)
    apply = inspect.getsource(gui._RoundHoleSettingsDialog._apply_pattern)
    assert "float(" not in source
    assert "isfinite" not in source
    assert "manufacturing_api.plan_operator_round_hole_preview(" in apply
