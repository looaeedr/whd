"""#2517: Door Indicator fit must validate original physical T through Engine."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from ae_engine import manufacturing_door_indicator as owner
from gui_modules.editors.hole_editor import HoleEditorIndicatorFitValidation


def _fit(*, thickness, mode="indicator_box"):
    return manufacturing_api.validate_door_indicator_fit(
        mode=mode, groups=(2,), finished_width=5000.0,
        finished_height=5000.0, thickness=thickness, offset=(0.0, 0.0),
    )


@pytest.mark.parametrize("raw", (
    True, False, 0, "0", -1, "-1", None, "",
    float("nan"), float("inf"), float("-inf"),
    "nan", "inf", "-inf", "bad-t", [], {},
))
@pytest.mark.parametrize("mode", ("indicator_box", "indicator"))
def test_active_public_fit_rejects_invalid_original_t_before_geometry(monkeypatch, mode, raw):
    monkeypatch.setattr(owner.ae, "get_indicator_box_data",
                        lambda *args, **kwargs: pytest.fail(
                            "invalid physical T reached IndicatorBox geometry"
                        ))
    before = repr(raw)
    with pytest.raises((ValueError, TypeError)):
        _fit(thickness=raw, mode=mode)
    assert repr(raw) == before


class _Button:
    def __init__(self):
        self.states = []

    def configure(self, **kwargs):
        self.states.append(kwargs["state"])


def _gui_fit(raw, *, show_error=False):
    button = _Button()
    errors, messages = [None], []
    original = {"mode": "indicator_box", "layers": 1,
                "groups": [2], "offset_x": 0, "offset_y": 0}
    before = deepcopy(original)
    validator = HoleEditorIndicatorFitValidation(
        door_indicator_state_provider=lambda: original,
        door_indicator_context_provider=lambda: SimpleNamespace(
            finished_width=5000.0, finished_height=5000.0,
        ),
        door_thickness_provider=lambda: raw,
        fit_error=errors, confirm_button=button,
        collect_state=lambda: original,
        validate_fit=manufacturing_api.validate_door_indicator_fit,
        show_error=lambda *args: messages.append(args),
        normal_state="normal", disabled_state="disabled",
    )
    accepted = validator.validate(show_error=show_error)
    assert original == before
    return accepted, button.states, errors[0], messages


@pytest.mark.parametrize("raw", (True, False, 0, "-2", "nan", float("inf"), None, "bad"))
def test_live_hole_editor_rejects_invalid_t_without_enabling_confirm(monkeypatch, raw):
    monkeypatch.setattr(owner.ae, "get_indicator_box_data",
                        lambda *args, **kwargs: pytest.fail(
                            "GUI sent invalid physical T into geometry"
                        ))
    accepted, states, error, messages = _gui_fit(raw, show_error=True)
    assert accepted is False
    assert states == ["disabled"]
    assert error
    assert len(messages) == 1 and messages[0][0] == "指示燈配置無法套用"


@pytest.mark.parametrize("raw,expected", (
    ("2", 2.0), ("2.125", 2.125), (2.125, 2.125),
))
def test_valid_fractional_json_t_has_same_headless_and_gui_fit(raw, expected):
    source = json.loads(json.dumps({"thickness": raw}))
    saved = deepcopy(source)
    assert manufacturing_api.normalize_operator_source_dimension(
        source["thickness"], field="t",
    ) == expected
    direct = _fit(thickness=source["thickness"])
    accepted, states, error, messages = _gui_fit(source["thickness"])
    assert direct[0] > 0 and direct[1] > 0
    assert accepted is True and states == ["normal"]
    assert error is None and not messages
    assert source == saved


def test_disabled_mode_keeps_original_no_manufacturing_fit_behavior():
    assert _fit(mode="none", thickness=0) == (0.0, 0.0)


def test_gui_forwards_raw_t_and_engine_owns_original_source_gate():
    gui_source = inspect.getsource(HoleEditorIndicatorFitValidation.validate)
    engine_source = inspect.getsource(owner.validate_door_indicator_fit)
    assert "thickness=self.door_thickness_provider()," in gui_source
    assert "float(self.door_thickness_provider()" not in gui_source
    assert "normalize_operator_source_dimension(thickness, field=\"t\")" in engine_source
