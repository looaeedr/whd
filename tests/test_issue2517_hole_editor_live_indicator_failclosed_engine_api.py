"""#2517 live Indicator controls: Engine must reject fabricated physical inputs."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api
from gui_modules.parts.panels.door import normalize_door_indicator_state
from gui_modules.editors.hole_editor_controls import HoleEditorIndicatorStateCollector
from gui_modules.editors.hole_editor import (
    HoleEditorIndicatorFitValidation, HoleEditorModalLifecycle,
)


class Var:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


def input_data(**changes):
    data = dict(mode="indicator_box", layers="2", groups=["3", "4", "5"],
                offset_x="-0.5", offset_y="11.25", is_box_dist=False)
    data.update(changes)
    return data


def collect(source, *, normalize=normalize_door_indicator_state):
    return HoleEditorIndicatorStateCollector(
        mode_var_provider=lambda: Var(source["mode"]),
        layers_var_provider=lambda: Var(source["layers"]),
        group_vars_provider=lambda: [Var(v) for v in source["groups"]],
        offset_x_var_provider=lambda: Var(source["offset_x"]),
        offset_y_var_provider=lambda: Var(source["offset_y"]),
        box_dist_var_provider=lambda: Var(source["is_box_dist"]),
        normalize_state=lambda raw: normalize(
            manufacturing_api.normalize_operator_hole_editor_indicator_state(raw)
        ),
    ).collect()


def test_valid_enabled_inputs_remain_exact_after_engine_and_saved_compatibility():
    assert collect(input_data()) == {
        "mode": "indicator_box", "enabled": False, "box_enabled": True,
        "layers": 2, "groups": [3, 4, 2, 2, 2, 2],
        "offset_x": -0.5, "offset_y": 11.25, "is_box_dist": False,
    }


@pytest.mark.parametrize("change,error", [
    (dict(layers="bad"), "層數／組數"),
    (dict(layers="0"), "層數／組數"),
    (dict(layers="2.5"), "層數／組數"),
    (dict(layers=True), "層數／組數"),
    (dict(layers="7"), "最多六層"),
    (dict(layers="3", groups=["3", "4"]), "缺少實際組數"),
    (dict(groups=["bad", "4"]), "層數／組數"),
    (dict(groups=[True, "4"]), "層數／組數"),
    (dict(groups=["0", "4"]), "層數／組數"),
    (dict(groups=["9", "4"]), "最多八組"),
    (dict(offset_x="nan"), "offset_x"),
    (dict(offset_x="inf"), "offset_x"),
    (dict(offset_x=""), "offset_x"),
    (dict(offset_x=True), "offset_x"),
    (dict(offset_y="-inf"), "offset_y"),
    (dict(offset_y=None), "offset_y"),
    (dict(is_box_dist="invalid"), "箱距"),
    (dict(mode="wrong"), "模式"),
])
def test_invalid_enabled_live_controls_are_never_repaired_to_physical_holes(change, error):
    called = []
    def compatibility(state):
        called.append(state)
        return normalize_door_indicator_state(state)
    with pytest.raises(ValueError, match=error):
        collect(input_data(**change), normalize=compatibility)
    assert not called


def test_disabled_indicator_does_not_parse_unrelated_invalid_fields():
    actual = collect(input_data(mode="none", layers="bad", groups=["wrong"],
                                offset_x="nan", offset_y="oops",
                                is_box_dist="invalid"))
    assert actual["mode"] == "none"
    assert actual["enabled"] is False
    assert actual["box_enabled"] is False


def test_fit_validation_disables_confirm_when_live_source_is_invalid():
    changes, errors = [], []
    def bad_live():
        raise ValueError("指示燈層數／組數無效")
    v = HoleEditorIndicatorFitValidation(
        door_indicator_state_provider=lambda: {"mode": "indicator"},
        door_indicator_context_provider=lambda: SimpleNamespace(
            finished_width=200., finished_height=200.,
        ),
        door_thickness_provider=lambda: 2.,
        fit_error=[None],
        confirm_button=SimpleNamespace(configure=lambda **kw: changes.append(kw)),
        collect_state=bad_live,
        validate_fit=lambda **kw: pytest.fail("invalid geometry must not be projected"),
        show_error=lambda *args: errors.append(args),
        normal_state="normal", disabled_state="disabled",
    )
    assert not v.validate(show_error=True)
    assert changes[-1]["state"] == "disabled"
    assert errors and "層數／組數" in errors[0][1]


def test_last_live_read_failure_cannot_finish_hole_edit_session(monkeypatch):
    from gui_modules.editors import hole_editor as module
    errors, finished = [], []
    monkeypatch.setattr(module.messagebox, "showerror",
                        lambda *args, **kwargs: errors.append((args, kwargs)))
    modal = HoleEditorModalLifecycle(
        hole_session=SimpleNamespace(finish=lambda **kw: finished.append(kw)),
        has_selected_feature=lambda: False, position_authority=[None],
        commit_active_edit=lambda **kw: None, sync_all=lambda: None,
        validate_current_indicator_fit=lambda **kw: True,
        door_indicator_state={"mode": "indicator"},
        collect_indicator_state=lambda: (_ for _ in ()).throw(ValueError("異常數值")),
        door_indicator_commit=lambda s: pytest.fail("must not commit"),
        editor_closed=[False], editor=SimpleNamespace(destroy=lambda: None),
        on_close=lambda: None, insert_mode=[False],
        set_insert_mode=lambda *args: None, cancel_active_edit=lambda: None,
    )
    modal.confirm_all()
    assert finished == []
    assert errors and errors[0][0][1] == "異常數值"


def test_gui_collects_raw_controls_and_uses_public_engine_validation():
    controls = Path("gui_modules/editors/hole_editor_controls.py").read_text(encoding="utf-8")
    segment = controls.split("class HoleEditorIndicatorStateCollector:", 1)[1].split(
        "class HoleEditorIndicatorGroupControls:", 1)[0]
    assert "groups.append(2)" not in segment
    assert "offset_x = 0.0" not in segment
    assert "max(1, min(6" not in segment
    wiring = Path("gui_modules/editors/hole_editor_composition.py").read_text(encoding="utf-8")
    assert "manufacturing_api.normalize_operator_hole_editor_indicator_state(raw)" in wiring
