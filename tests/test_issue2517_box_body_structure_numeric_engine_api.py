"""#2517: BoxBody split numeric writes are public Engine API operations."""
from __future__ import annotations

from copy import deepcopy
import inspect
import json

import pytest

from ae_engine import manufacturing_api as api, apply_box_body_structure_numeric
from ae_engine import box_body_structure_state as owner
from ae_engine.box_body_structure_state import BoxBodyStructureType
from phase6_settings_transitions import apply_box_structure_numeric as gui_commit


def test_public_api_is_existing_engine_owner_and_gui_is_port_only():
    assert apply_box_body_structure_numeric is api.apply_box_body_structure_numeric
    assert apply_box_body_structure_numeric is owner.apply_box_body_structure_numeric
    code = inspect.getsource(gui_commit)
    assert "manufacturing_api.apply_box_body_structure_numeric(" in code
    assert "set_two_piece_width(" not in code
    assert "set_three_piece_width(" not in code
    assert "set_side_back_geometry(" not in code


def test_two_and_three_piece_manual_width_and_joint_reopen_headlessly():
    state = api.default_box_body_structure_state()
    original = deepcopy(state)
    two = BoxBodyStructureType.TWO_PIECE_W_SPLIT
    edited = api.apply_box_body_structure_numeric(state, two, "left", 300, total_w=800)
    assert state == original
    assert edited["configs"][two.value]["left_w"] == 300
    assert edited["configs"][two.value]["right_w"] == 500
    assert gui_commit(state, two, "left", 300, total_w=800) == edited
    seam = api.apply_box_body_structure_numeric(edited, two, "seam_bend", 16, total_w=800)
    three = BoxBodyStructureType.THREE_PIECE_W_SPLIT
    result = api.apply_box_body_structure_numeric(seam, three, "middle", 400, total_w=800)
    assert result["configs"][three.value]["left_w"] == 200
    assert result["configs"][three.value]["middle_w"] == 400
    assert result["configs"][three.value]["right_w"] == 200
    stored = json.loads(json.dumps(result))
    assert owner.normalize_box_body_structure_state(stored) == result


def test_side_back_outside_space_and_compensation_preserve_existing_engine_semantics():
    state = api.default_box_body_structure_state()
    kind = BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT
    first = api.apply_box_body_structure_numeric(
        state, kind, "side_rear_bend", 18, total_w=800, outside_family=True,
    )
    assert first["configs"][kind.value]["side_rear_bend"] == 18
    assert first["configs"][kind.value]["side_rear_bend_dimension_space"] == "OUTSIDE"
    second = api.apply_box_body_structure_numeric(first, kind, "back_width_comp_t", 2.5, total_w=800)
    assert second["configs"][kind.value]["back_width_comp_t"] == 2.5
    assert gui_commit(state, kind, "side_rear_bend", 18, total_w=800, outside_family=True) == first
    assert state["configs"][kind.value] != second["configs"][kind.value]


@pytest.mark.parametrize("field,value", [
    ("endcap_extra_relief", -1),
    ("endcap_single_side_meat_t", -0.1),
    ("baseplate_relief_length", -0.25),
    ("baseplate_single_side_meat_t", -1),
])
def test_negative_relief_fails_closed_without_mutating_state(field, value):
    state = api.default_box_body_structure_state()
    source = deepcopy(state)
    with pytest.raises(ValueError, match="不得小於 0"):
        api.apply_box_body_structure_numeric(
            state, BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT,
            field, value, total_w=800,
        )
    assert state == source
