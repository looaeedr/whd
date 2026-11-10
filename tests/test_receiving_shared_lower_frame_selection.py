"""Receiving shared C lower frame must survive Door-only DXF selection."""
from __future__ import annotations

from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
from ae_engine.manufacturing_export_selection import (
    receiving_export_part_selected, select_resolved_export_geometry,
)


def _resolved():
    # Use physical IDs only. This Engine selection step must not manufacture
    # fallback geometry from these labels.
    return ResolvedManufacturingGeometry(parts=tuple(
        ResolvedManufacturingPart(key, object())
        for key in (
            "box_body",
            "box_body:divider:door-grid:HORIZONTAL:0:1",
            "inner_door:upper:top_frame",
            "inner_door:upper:left_frame",
            "inner_door:upper:right_frame",
            "door_c1_r1",
            "door_c1_r2",
            "head",
        )
    ))


def test_door_only_includes_real_fourth_shared_lower_c_but_not_shell():
    selected = select_resolved_export_geometry(
        _resolved(), {"door": True, "box_body": False},
    )
    keys = {part.part_key for part in selected.parts}
    assert keys == {
        "box_body:divider:door-grid:HORIZONTAL:0:1",
        "inner_door:upper:top_frame",
        "inner_door:upper:left_frame",
        "inner_door:upper:right_frame",
        "door_c1_r1",
        "door_c1_r2",
    }


def test_body_only_retains_shared_c_without_selecting_door_frame():
    selected = select_resolved_export_geometry(
        _resolved(), {"door": False, "box_body": True},
    )
    assert {part.part_key for part in selected.parts} == {
        "box_body", "box_body:divider:door-grid:HORIZONTAL:0:1",
    }


def test_unselected_lower_c_not_added_and_existing_scene_identity_kept():
    original = _resolved()
    none = select_resolved_export_geometry(original, {})
    assert none.parts == ()
    both = select_resolved_export_geometry(
        original, {"box_body": True, "door": True, "head": True},
    )
    assert both.parts == original.parts
    assert all(a.render_data is b.render_data for a, b
               in zip(both.parts, original.parts))
    assert receiving_export_part_selected("box_body:divider:door-grid:HORIZONTAL:0:1",
                                          {"door": True}) is True
    assert receiving_export_part_selected("box_body:left_side",
                                          {"door": True}) is False
