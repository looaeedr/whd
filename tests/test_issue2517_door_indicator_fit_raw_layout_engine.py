"""#2517: public Door Indicator fit uses original Engine group/offset gates."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import manufacturing_door_indicator as owner
from gui_modules.editors.hole_editor import HoleEditorIndicatorFitValidation


def _fit(*, groups=(2,), offset=(0.0, 0.0), mode="indicator_box"):
    return api.validate_door_indicator_fit(
        mode=mode, groups=groups, finished_width=5000.0,
        finished_height=5000.0, thickness="2.125", offset=offset,
    )


@pytest.mark.parametrize("groups", [
    (True,), (False,), (2.5,), (float("nan"),),
    ("2.5",), ("nan",), (0,), (-1,), (),
])
@pytest.mark.parametrize("mode", ["indicator_box", "indicator"])
def test_headless_fit_rejects_lossy_original_groups_before_any_geometry(monkeypatch, groups, mode):
    monkeypatch.setattr(owner.ae, "get_indicator_box_data",
                        lambda *args, **kwargs: pytest.fail(
                            "invalid raw groups reached geometry"
                        ))
    original = repr(groups)
    with pytest.raises((TypeError, ValueError)):
        _fit(groups=groups, mode=mode)
    assert repr(groups) == original


@pytest.mark.parametrize("offset", [
    (True, 0), (False, 0), (float("nan"), 0),
    (float("inf"), 0), (0, float("-inf")),
    ("nan", "0"), ("bad", 0),
])
@pytest.mark.parametrize("mode", ["indicator_box", "indicator"])
def test_headless_fit_rejects_nonfinite_or_boolean_offsets(monkeypatch, offset, mode):
    monkeypatch.setattr(owner.ae, "get_indicator_box_data",
                        lambda *args, **kwargs: pytest.fail(
                            "invalid raw offset reached geometry"
                        ))
    original = repr(offset)
    with pytest.raises((TypeError, ValueError)):
        _fit(offset=offset, mode=mode)
    assert repr(offset) == original


class Button:
    def __init__(self):
        self.states = []

    def configure(self, **kw):
        self.states.append(kw["state"])


@pytest.mark.parametrize("groups,offset", [
    ((True,), (0, 0)), ((2.5,), (0, 0)),
    ((2,), (float("nan"), 0)), ((2,), (True, 0)),
])
def test_live_hole_editor_invalid_layout_disables_confirm_without_source_mutation(
    monkeypatch, groups, offset,
):
    monkeypatch.setattr(owner.ae, "get_indicator_box_data",
                        lambda *args, **kwargs: pytest.fail(
                            "unqualified source reached IndicatorBox geometry"
                        ))
    source = {
        "mode": "indicator_box", "layers": len(groups),
        "groups": list(groups), "offset_x": offset[0], "offset_y": offset[1],
    }
    before = deepcopy(source)
    button, errors, messages = Button(), [None], []
    editor = HoleEditorIndicatorFitValidation(
        door_indicator_state_provider=lambda: source,
        door_indicator_context_provider=lambda: SimpleNamespace(
            finished_width=5000.0, finished_height=5000.0,
        ),
        door_thickness_provider=lambda: "2.125",
        fit_error=errors, confirm_button=button,
        collect_state=lambda: source,
        validate_fit=api.validate_door_indicator_fit,
        show_error=lambda *args: messages.append(args),
        normal_state="normal", disabled_state="disabled",
    )
    assert editor.validate(show_error=True) is False
    assert button.states == ["disabled"]
    assert errors[0] and len(messages) == 1
    assert source == before


def test_json_fractional_negative_offsets_and_integer_groups_match_existing_engine_owners():
    source = json.loads(json.dumps({
        "groups": ["03", 2.0], "offset": ["-2.5", "1.375"],
    }))
    before = deepcopy(source)
    groups = api.normalize_fold_designer_indicator_groups(source["groups"])
    offsets = api.normalize_fold_designer_indicator_offsets(*source["offset"])
    assert groups == (3, 2)
    assert offsets == (-2.5, 1.375)
    raw = _fit(groups=source["groups"], offset=source["offset"])
    normalized = _fit(groups=groups, offset=offsets)
    assert raw == pytest.approx(normalized)
    assert raw[0] > 0 and raw[1] > 0
    assert source == before


def test_disabled_fit_does_not_manufacture_hidden_invalid_groups_or_offsets():
    assert _fit(mode="none", groups=(True,), offset=(float("nan"), 0)) == (0.0, 0.0)


def test_original_engine_source_not_int_or_float_guessing():
    source = inspect.getsource(owner.validate_door_indicator_fit)
    assert "normalize_fold_designer_indicator_groups(groups)" in source
    assert "normalize_fold_designer_indicator_offsets(offset[0], offset[1])" in source
    assert "tuple(int(v) for v in groups)" not in source
    assert "float(offset[0])" not in source
