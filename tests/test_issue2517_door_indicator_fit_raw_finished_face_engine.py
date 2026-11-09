"""#2517: Door Indicator public fit validates original finished-face W/H source."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import manufacturing_door_indicator as owner
from gui_modules.editors.hole_editor import HoleEditorIndicatorFitValidation


def _fit(w, h, *, mode="indicator_box"):
    return api.validate_door_indicator_fit(
        mode=mode, groups=(2,), finished_width=w, finished_height=h,
        thickness=2.125, offset=(0, 0),
    )


@pytest.mark.parametrize("raw", (
    True, False, 0, "0", -1, "-1", None, "",
    "bad", "nan", "inf", float("nan"), float("inf"), float("-inf"),
))
@pytest.mark.parametrize("axis", ("w", "h"))
@pytest.mark.parametrize("mode", ("indicator_box", "indicator"))
def test_public_fit_rejects_bad_finished_face_axis_before_any_geometry(
    monkeypatch, axis, mode, raw,
):
    monkeypatch.setattr(owner.ae, "get_indicator_box_data",
                        lambda *args, **kwargs: pytest.fail(
                            "invalid face dimension reached IndicatorBox geometry"
                        ))
    monkeypatch.setattr(owner, "resolve_door_indicator_layout",
                        lambda *args, **kwargs: pytest.fail(
                            "invalid face dimension reached Indicator layout"
                        ))
    source = {"w": 5000, "h": 5000}
    source[axis] = raw
    before = repr(source)
    with pytest.raises((ValueError, TypeError)):
        _fit(source["w"], source["h"], mode=mode)
    assert repr(source) == before


class _Button:
    def __init__(self):
        self.states = []

    def configure(self, **kwargs):
        self.states.append(kwargs["state"])


@pytest.mark.parametrize("axis,bad", (
    ("w", True), ("h", False), ("w", float("nan")),
    ("h", float("inf")), ("w", "bad"),
))
def test_gui_forwards_raw_face_source_and_disables_confirm_on_failure(
    monkeypatch, axis, bad,
):
    monkeypatch.setattr(owner.ae, "get_indicator_box_data",
                        lambda *args, **kwargs: pytest.fail(
                            "unverified finished-face source reached geometry"
                        ))
    button, errors, messages = _Button(), [None], []
    source = {"mode": "indicator_box", "layers": 1,
              "groups": [2], "offset_x": 0.0, "offset_y": 0.0}
    before = deepcopy(source)
    dims = {"w": 5000, "h": 5000}
    dims[axis] = bad
    context = SimpleNamespace(finished_width=dims["w"], finished_height=dims["h"])
    editor = HoleEditorIndicatorFitValidation(
        door_indicator_state_provider=lambda: source,
        door_indicator_context_provider=lambda: context,
        door_thickness_provider=lambda: "2.125",
        fit_error=errors, confirm_button=button,
        collect_state=lambda: source,
        validate_fit=api.validate_door_indicator_fit,
        show_error=lambda *args: messages.append(args),
        normal_state="normal", disabled_state="disabled",
    )
    assert editor.validate(show_error=True) is False
    assert button.states == ["disabled"] and errors[0]
    assert len(messages) == 1
    assert source == before
    assert (context.finished_width, context.finished_height) == (
        dims["w"], dims["h"],
    )


def test_json_fractional_face_matches_same_canonical_engine_fit():
    source = json.loads(json.dumps({"w": "5000.125", "h": "4500.375"}))
    before = deepcopy(source)
    normalized = (
        api.normalize_operator_source_dimension(source["w"], field="w"),
        api.normalize_operator_source_dimension(source["h"], field="h"),
    )
    direct = _fit(source["w"], source["h"])
    parsed = _fit(*normalized)
    assert direct == pytest.approx(parsed)
    assert direct[0] > 0 and direct[1] > 0
    assert source == before


def test_disabled_mode_keeps_original_no_geometry_face_check():
    assert _fit(float("nan"), 5000.0, mode="none") == (0.0, 0.0)


def test_real_gui_does_not_precoerce_finished_face_and_engine_owns_gate():
    gui_source = inspect.getsource(HoleEditorIndicatorFitValidation.validate)
    engine_source = inspect.getsource(owner.validate_door_indicator_fit)
    assert "finished_width=context.finished_width," in gui_source
    assert "finished_height=context.finished_height," in gui_source
    assert "finished_width=float(context.finished_width)" not in gui_source
    assert "normalize_operator_source_dimension(finished_width, field=\"w\")" in engine_source
    assert "normalize_operator_source_dimension(finished_height, field=\"h\")" in engine_source
