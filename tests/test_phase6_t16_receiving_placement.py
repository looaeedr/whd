from __future__ import annotations

import pytest

from ae_engine.assembly_placement import resolve_assembly_placement


def _snapshot():
    return {
        "model": "受電箱",
        "w": 800.0,
        "h": 1600.0,
        "d": 350.0,
        "t": 2.0,
        "fw": 29.0,
        "multi_door_enabled": True,
        "door_layout_scope": "receiving-main",
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        "inner_doors": [{
            "stable_id": "upper",
            "cell_key": "0:0",
            "included_frame_sides": ["top", "left", "right"],
        }],
    }


def test_r06_outer_door_has_authoritative_placement_contract():
    placement = resolve_assembly_placement(_snapshot(), "door_c1_r1")
    assert placement.stable_id == "door_c1_r1"
    assert placement.parent_assembly_node == "box_body"
    assert placement.relationship == "OUTER_DOOR"
    assert placement.mate_target == "box_body:front_opening"
    assert placement.placement_kind == "receiving_outer_door"
    assert placement.anchor == "door_layout_cell:0:0"


def test_r06_top_left_right_inner_frames_have_authoritative_placement_contracts():
    expected = {
        "inner_door:upper:top_frame": "inner_door_frame_top",
        "inner_door:upper:left_frame": "inner_door_frame_left",
        "inner_door:upper:right_frame": "inner_door_frame_right",
    }
    for stable_id, kind in expected.items():
        placement = resolve_assembly_placement(_snapshot(), stable_id)
        assert placement.stable_id == stable_id
        assert placement.parent_assembly_node == "box_body:door_layout:inner_door"
        assert placement.relationship == "INNER_DOOR_FRAME"
        assert placement.placement_kind == kind
        assert placement.world_offset != (0.0, 0.0, 0.0)


def test_r06_divider_guard_stays_authoritative_and_repeatable():
    stable_id = "box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1"
    first = resolve_assembly_placement(_snapshot(), stable_id)
    second = resolve_assembly_placement(_snapshot(), stable_id)
    assert first == second
    assert first.relationship == "SHARED_STRUCTURAL_DIVIDER"
    assert first.placement_kind == "divider_horizontal"


def test_unknown_receiving_derived_part_must_fail_closed_not_origin_fallback():
    with pytest.raises(ValueError, match="no authoritative placement contract"):
        resolve_assembly_placement(_snapshot(), "inner_door:upper:unknown")
