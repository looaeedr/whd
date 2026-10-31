"""#2517: raw EndCap CornerType + box assembly selection owned by Engine."""
from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

from ae_engine import (
    apply_endcap_box_assembly_type_to_raw_state,
    endcap_corner_selection_from_raw,
    endcap_corner_selection_to_raw,
    manufacturing_api,
)
from ae_engine import endcap_factory_fold as owner
from ae_engine.sheetmetal_geometry import CornerTypeId, CornerTypeSelection, CrossCornerMode, CornerDirection
import phase6_endcap_semantics as gui


def _state():
    bottom = {
        "type_id": "CROSS", "rotation_quadrants": 0,
        "cross_mode": "EXTRA_CUT", "direction": "BOTH", "amount_t": 2.25,
    }
    return {
        "head": {"bottom_left": deepcopy(bottom)},
        "tail": {"bottom_right": deepcopy(bottom)},
    }


def test_public_corner_serializer_is_exact_engine_owner_and_backward_compatible():
    assert endcap_corner_selection_to_raw is manufacturing_api.endcap_corner_selection_to_raw
    assert endcap_corner_selection_to_raw is owner.selection_to_raw
    selection = CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode.EXTRA_CUT,
        direction=CornerDirection.WIDTH,
        amount_t=1.5,
    )
    raw = endcap_corner_selection_to_raw(selection)
    assert raw == gui.selection_to_raw(selection)
    assert raw["type_id"] == "CROSS"
    assert raw["amount_t"] == 1.5
    assert endcap_corner_selection_to_raw(endcap_corner_selection_from_raw(raw)) == raw


def test_explicit_assembly_type_updates_top_corners_and_preserves_manual_bottom():
    raw = _state()
    manual = deepcopy(raw)
    pairs = {}
    assert apply_endcap_box_assembly_type_to_raw_state is owner.apply_box_assembly_type_to_raw_state
    chosen = apply_endcap_box_assembly_type_to_raw_state(
        raw, pairs, CornerTypeId.OVERLAY,
    )
    assert chosen is CornerTypeId.OVERLAY
    assert raw["head"]["bottom_left"] == manual["head"]["bottom_left"]
    assert raw["tail"]["bottom_right"] == manual["tail"]["bottom_right"]
    for part in ("head", "tail"):
        assert raw[part]["top_left"]["type_id"] == "OVERLAY"
        assert raw[part]["top_right"]["type_id"] == "OVERLAY"
        assert pairs[part] == {"top": True, "bottom": True}


def test_operator_explicit_bottom_reset_matches_current_engine_policy():
    raw = _state()
    pairs = {}
    assert gui.apply_box_assembly_type_to_raw_state(
        raw, pairs, CornerTypeId.OVERLAY, reset_bottom_defaults=True,
    ) is CornerTypeId.OVERLAY
    for part in ("head", "tail"):
        for corner in ("bottom_left", "bottom_right"):
            assert raw[part][corner]["cross_mode"] == "EXTRA_CUT"
            assert raw[part][corner]["direction"] == "WIDTH"
            assert raw[part][corner]["amount_t"] == pytest.approx(1.5)


def test_illegal_assembly_input_cannot_mutate_or_fabricate_manufacturing_state():
    raw = _state()
    saved = deepcopy(raw)
    pairs = {}
    with pytest.raises(ValueError):
        apply_endcap_box_assembly_type_to_raw_state(raw, pairs, "FORGED")
    assert raw == saved
    assert pairs == {}


def test_phase6_is_port_only_not_a_second_corner_policy_or_raw_geometry_converter():
    src = inspect.getsource(gui.selection_to_raw)
    asm = inspect.getsource(gui.apply_box_assembly_type_to_raw_state)
    assert "manufacturing_api.endcap_corner_selection_to_raw(" in src
    assert "manufacturing_api.apply_endcap_box_assembly_type_to_raw_state(" in asm
    assert "apply_box_assembly_type(" not in asm
    assert "from phase6_" not in inspect.getsource(owner)
