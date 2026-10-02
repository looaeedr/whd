# -*- coding: utf-8 -*-
from ae_engine.assembly_placement import (
    AssemblyPlacement,
    resolve_assembly_placement,
)


def _snapshot():
    return {
        "w": 500,
        "h": 600,
        "d": 200,
        "t": 2,
        "door_layout_scope": "main",
        "door_layout_columns": [
            [250, [300, 300]],
            [250, [300, 300]],
        ],
        "multi_door_enabled": True,
    }


def test_vertical_divider_has_formal_parent_anchor_and_world_offset():
    placement = resolve_assembly_placement(
        _snapshot(),
        "box_body:divider:main:VERTICAL:C0|C1",
    )

    assert isinstance(placement, AssemblyPlacement)
    assert placement.stable_id == "box_body:divider:main:VERTICAL:C0|C1"
    assert placement.parent_assembly_node == "box_body"
    assert placement.anchor == "door_layout_boundary:C0|C1"
    assert placement.mate_target == "box_body:door_layout"
    assert placement.relationship == "SHARED_STRUCTURAL_DIVIDER"
    assert placement.placement_kind == "divider_vertical"
    assert placement.world_offset == (0.0, 0.0, 0.0)
    assert placement.rotation == (0.0, 0.0, 0.0)


def test_horizontal_divider_resolves_from_authoritative_door_boundary():
    placement = resolve_assembly_placement(
        _snapshot(),
        "box_body:divider:main:HORIZONTAL:C0_R0|R1",
    )

    assert placement.stable_id.endswith(":HORIZONTAL:C0_R0|R1")
    assert placement.parent_assembly_node == "box_body"
    assert placement.anchor == "door_layout_boundary:C0_R0|R1"
    assert placement.placement_kind == "divider_horizontal"
    # The boundary between the two 300-high cells is at the authoritative
    # Door layout Y coordinate; it must not be a GUI/default-origin fallback.
    assert placement.semantic_position == (-125.0, 0.0, 0.0)


def test_unknown_part_does_not_receive_silent_origin_fallback():
    try:
        resolve_assembly_placement(_snapshot(), "box_body:divider:main:VERTICAL:unknown")
    except ValueError as exc:
        assert "authoritative divider topology" in str(exc)
    else:
        raise AssertionError("unknown divider topology must fail closed")
