# -*- coding: utf-8 -*-
"""#1502/#1503: NFB screw X edits must not move Base Plate or welded ear holes.

Source geometry test uses original native upper Color30 + lower four screws
in the *same* verified DXF / FinalScene, rather than a mocked placement.
"""
from dataclasses import replace

import pytest

from ae_engine.receiving_nfb_base_process_projection import (
    build_existing_receiving_base_with_verified_nfb,
)
from ae_engine.manufacturing_scene_orchestration import build_part_render_data
from ae_engine.sheetmetal_drawing import CirclePrimitive, PolylinePrimitive
from tests.test_issue1502_existing_base_nfb_assembly import (
    _snapshot, _upper_base, _native_original, _verified,
)


def test_nfb_horizontal_x_shifts_only_native_screw_cutting_not_670_ear_mount(tmp_path):
    source, profile, lower = _native_original(tmp_path)
    original = _verified(profile)
    shift = 35.0
    changed = replace(
        original,
        verified_hole_locations=tuple(
            (hole_id, x + shift, layers, slot, rotation)
            for hole_id, x, layers, slot, rotation
            in original.verified_hole_locations
        ),
    )
    plate = _upper_base("CENTER_DOUBLE_SIDE_FOLD")

    def make(proof):
        return build_existing_receiving_base_with_verified_nfb(
            snapshot=_snapshot(), inner_door_id="upper",
            base_spec=plate, verified_inner_door=proof,
            source_path=source, profile=profile,
            lower_reference_handle=lower,
        ).render_data

    before, after = make(original), make(changed)
    # The physically fixed 670-mm LEFT/RIGHT ear support is centered at X0,
    # even if *both* NFB opening centers are moved 35mm to the right.
    assert before.metadata["receiving_base_ear_mount_center_world_xy_mm"] == pytest.approx((0,250))
    assert after.metadata["receiving_base_ear_mount_center_world_xy_mm"] == pytest.approx((0,250))
    assert before.metadata["receiving_base_nfb_row_center_world_xy_mm"] == pytest.approx((0,250))
    assert after.metadata["receiving_base_nfb_row_center_world_xy_mm"] == pytest.approx((35,250))

    def screws(render):
        return {
            p.source_id: (float(p.center.x), float(p.center.y))
            for p in render.scene.primitives
            if isinstance(p, CirclePrimitive)
            and p.source_type == "NFB_LOWER_NATIVE_FIXING_CIRCLE"
        }

    source_holes, shifted_holes = screws(before), screws(after)
    assert len(source_holes) == len(shifted_holes) == 8
    assert set(source_holes) == set(shifted_holes)
    for key in source_holes:
        assert shifted_holes[key][0]-source_holes[key][0] == pytest.approx(shift)
        assert shifted_holes[key][1] == pytest.approx(source_holes[key][1])

    # Physical Base Plate's four native fixing slots are from the original
    # source PART and are unchanged, not re-positioned per NFB model.
    original_plate = build_part_render_data(plate)
    native = tuple(
        p for p in original_plate.scene.primitives
        if isinstance(p, PolylinePrimitive)
        and p.layer == "CUTTING" and p.closed
    )
    def loops(render):
        return tuple(
            tuple((float(x.x),float(x.y)) for x in p.points)
            for p in render.scene.primitives
            if isinstance(p, PolylinePrimitive)
            and p.layer == "CUTTING" and p.closed
        )
    for physical in native:
        pts=tuple((float(x),float(y)) for x,y in physical.points)
        assert pts in loops(before)
        assert pts in loops(after)
    assert len(native) == 5  # original envelope + four unchanged ear slots
    assert before.metadata["receiving_base_ear_weld_z_verified"] is False
    assert after.metadata["receiving_base_ear_weld_z_verified"] is False
