# -*- coding: utf-8 -*-
"""#2517 BoxBody physical structure numeric sources are Engine-owned and atomic."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.box_body_structure_state import BoxBodyStructureType
from gui_modules.application import fold_designer_composition_settings as gui_display
import fold_designer_bridge as bridge


RELIEF_FIELDS = (
    "endcap_extra_relief", "endcap_single_side_meat_t",
    "baseplate_relief_length", "baseplate_single_side_meat_t",
)
SIDE_BACK = BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT


class Field:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


@pytest.mark.parametrize("field", RELIEF_FIELDS)
@pytest.mark.parametrize("bad", [True, False, "nan", float("nan"), "inf", float("inf"), float("-inf")])
def test_engine_rejects_corrupt_authored_relief_without_changing_saved_box_state(field, bad):
    state = api.default_box_body_structure_state()
    original = deepcopy(state)
    with pytest.raises(ValueError, match="有限"):
        api.apply_box_body_structure_numeric(state, SIDE_BACK, field, bad, total_w=800)
    assert state == original


@pytest.mark.parametrize("bad", [True, False, "nan", float("nan"), "inf", float("inf"), -1, 0])
def test_public_engine_rejects_bad_total_w_on_every_box_structure_edit(bad):
    state = api.default_box_body_structure_state()
    original = deepcopy(state)
    with pytest.raises(ValueError):
        api.apply_box_body_structure_numeric(
            state, SIDE_BACK, "endcap_extra_relief", "5",
            total_w=bad,
        )
    assert state == original


def test_serialized_false_family_flag_cannot_change_rear_plate_dimension_space():
    state = api.default_box_body_structure_state()
    direct = api.apply_box_body_structure_numeric(
        state, SIDE_BACK, "side_rear_bend", "18",
        total_w="800", outside_family=False,
    )
    serialized = api.apply_box_body_structure_numeric(
        state, SIDE_BACK, "side_rear_bend", "18",
        total_w="800", outside_family="false",
    )
    outside = api.apply_box_body_structure_numeric(
        state, SIDE_BACK, "side_rear_bend", "18",
        total_w="800", outside_family="true",
    )
    assert serialized == direct
    assert outside["configs"][SIDE_BACK.value]["side_rear_bend_dimension_space"] == "OUTSIDE"
    assert state == api.default_box_body_structure_state()
    assert json.loads(json.dumps(serialized, allow_nan=False)) == serialized


@pytest.mark.parametrize("bad", ["maybe", "invalid", None, [], {}, 2, float("nan")])
def test_invalid_family_flag_cannot_commit_side_back_source(bad):
    state = api.default_box_body_structure_state()
    before = deepcopy(state)
    with pytest.raises(ValueError):
        api.apply_box_body_structure_numeric(
            state, SIDE_BACK, "side_rear_bend", 18,
            total_w=800, outside_family=bad,
        )
    assert state == before


@pytest.mark.parametrize("bad", [True, False, "nan", float("nan"), "inf"])
def test_actual_bridge_box_total_width_does_not_erase_original_source_type(bad):
    host = SimpleNamespace(
        _phase6_box_whd={"w": bad}, _settings_values={},
        state=SimpleNamespace(w=800),
    )
    with pytest.raises(ValueError):
        bridge._phase6_box_structure_w(host)


def test_gui_numeric_editor_forwards_raw_user_text_to_original_public_engine(monkeypatch):
    state = api.default_box_body_structure_state()
    host = SimpleNamespace(
        _phase6_box_whd={"w": "800"},
        _settings_values={},
        _phase6_input_snapshot={"model": "受電箱"},
        state=SimpleNamespace(w=800),
    )
    calls = []
    committed = []
    errors = []
    class Controller:
        def apply_box_structure_numeric(self, state_arg, type_id, field, value,
                                        *, total_w, outside_family):
            calls.append((value, total_w, outside_family))
            return api.apply_box_body_structure_numeric(
                state_arg, type_id, field, value,
                total_w=total_w, outside_family=outside_family,
            )
    monkeypatch.setattr(bridge, "_phase6_box_structure_state", lambda app: state)
    monkeypatch.setattr(bridge, "_phase6_settings_transactions", lambda app: Controller())
    monkeypatch.setattr(bridge, "_phase6_after_box_structure_commit",
                        lambda app, result, **kw: committed.append(result))
    monkeypatch.setattr(bridge, "_phase6_box_structure_error",
                        lambda app, exc: errors.append(str(exc)))
    monkeypatch.setattr(api, "operator_box_body_profile_uses_outside_dimensions",
                        lambda snapshot: False)
    bridge._phase6_apply_box_structure_numeric(
        host, SIDE_BACK, "endcap_extra_relief", Field("5.25"),
    )
    assert calls == [("5.25", 800.0, False)]
    assert committed[0]["configs"][SIDE_BACK.value]["endcap_extra_relief"] == 5.25
    assert state == api.default_box_body_structure_state()
    assert not errors
    bridge._phase6_apply_box_structure_numeric(
        host, SIDE_BACK, "endcap_extra_relief", Field(True),
    )
    assert calls[-1][0] is True
    assert len(committed) == 1 and errors
    assert state == api.default_box_body_structure_state()
