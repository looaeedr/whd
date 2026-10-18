# -*- coding: utf-8 -*-
"""#1502: NFB opening-group CENTER mates to each NFB tier's own Base Plate.

"Outer Door lower compartment has no base plate" does not prevent NFB tier 2
inside the upper Outer Door from owning a second physical Base Plate.
"""
from copy import deepcopy
import pytest

from ae_engine.assembly_placement import resolve_assembly_placement
from ae_engine.receiving_nfb_base_assembly_xy import receiving_nfb_layer_centers
from tests.test_receiving_base_physical_3d_z_assembly import _assembled


def _two_tier():
    snapshot = _assembled()
    config = deepcopy(snapshot["nfb_config"])
    config["layer_count"] = 2
    config["holes"] = [
        {
            **config["holes"][0], "physical_hole_id": "tier:0:a",
            "layer_count": 2, "layer_index": 0, "slot_index": 0,
        },
        {
            **config["holes"][1], "physical_hole_id": "tier:1:a",
            "layer_count": 2, "layer_index": 1, "slot_index": 0,
        },
    ]
    snapshot["nfb_config"] = config
    snapshot["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(config)
    snapshot["receiving_inner_door_layer_heights_mm"] = [330, 830]
    return snapshot


def test_two_nfb_tiers_in_upper_outer_door_own_two_distinct_plate_centers():
    snap = _two_tier()
    rows = receiving_nfb_layer_centers(snap, "upper")
    assert len(rows) == 2
    assert [item.layer_index for item in rows] == [0, 1]
    assert [item.layer_part_id for item in rows] == [
        "base_plate:nfb_layer:0", "base_plate:nfb_layer:1",
    ]
    assert [item.world_y_mm for item in rows] == pytest.approx([470, -30])
    assert [item.source_hole_count for item in rows] == [1, 1]
    assert all(item.verified_world_x_mm is None for item in rows)
    assert rows[0].world_y_mm != rows[1].world_y_mm


def test_tier_centers_use_own_confirmed_opening_x_never_cross_tiers():
    snap = _two_tier()
    for hole, x in zip(snap["nfb_config"]["holes"], (-100., 175.)):
        hole.update(
            manual_x_state="CONFIRMED", manual_x_mm=x,
            datum_revision="NFB-SOURCE-1",
            datum_snapshot={"w": 800, "t": 2},
        )
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(snap["nfb_config"])
    rows = receiving_nfb_layer_centers(snap, "upper")
    assert [row.verified_world_x_mm for row in rows] == pytest.approx([-100, 175])
    # An unconfirmed X must not silently inherit the other tier's X.
    snap["nfb_config"]["holes"][1]["manual_x_state"] = "RECONFIRM_REQUIRED"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(snap["nfb_config"])
    rows = receiving_nfb_layer_centers(snap, "upper")
    assert rows[0].verified_world_x_mm == pytest.approx(-100)
    assert rows[1].verified_world_x_mm is None


def test_same_tier_two_openings_share_one_plate_at_group_centre():
    snap = _assembled()
    for hole, x in zip(snap["nfb_config"]["holes"], (-130., 70.)):
        hole.update(
            manual_x_state="CONFIRMED", manual_x_mm=x,
            datum_revision="NFB-SOURCE-1",
            datum_snapshot={"w": 800, "t": 2},
        )
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(snap["nfb_config"])
    centres = receiving_nfb_layer_centers(snap, "upper")
    assert len(centres) == 1
    assert centres[0].verified_world_x_mm == pytest.approx(-30)
    plate = resolve_assembly_placement(snap, "base_plate")
    # Even source-confirmed group X=-30 does not shift the fixed plate X0.
    assert plate.world_offset[:2] == pytest.approx((0, 250))


def test_changes_in_hole_height_change_plate_center_not_plate_dimensions():
    snap = _assembled()
    original = resolve_assembly_placement(snap, "base_plate")
    original_dimensions = dict(snap["receiving_base_plate"])
    snap["receiving_inner_door_layer_heights_mm"] = [330, 830]
    changed = resolve_assembly_placement(snap, "base_plate")
    assert changed.world_offset[1] - original.world_offset[1] == pytest.approx(220)
    assert snap["receiving_base_plate"] == original_dimensions
    assert changed.world_offset[2] == pytest.approx(original.world_offset[2])


def test_unsubmitted_or_wrong_bay_never_mates_unrelated_plate():
    snap = _two_tier()
    snap["nfb_config_submitted"] = False
    assert receiving_nfb_layer_centers(snap, "upper") == ()
    snap = _two_tier()
    snap["_receiving_runtime_selection"]["bay_id"] = "wrong"
    with pytest.raises(ValueError, match="BAY_IDENTITY_DRIFT"):
        receiving_nfb_layer_centers(snap, "upper")



def test_two_layer_horizontal_slot_number_must_not_invent_second_tier():
    snap = _two_tier()
    # Two physical slots in the first tier are still only ONE plate,
    # even though one horizontal slot_index is 1.
    snap["nfb_config"]["holes"][1]["layer_index"] = 0
    snap["nfb_config"]["holes"][1]["slot_index"] = 1
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(snap["nfb_config"])
    only_one = receiving_nfb_layer_centers(snap,"upper")
    assert len(only_one) == 1
    assert only_one[0].layer_index == 0
    assert only_one[0].source_hole_count == 2
    snap["nfb_config"]["holes"][1].pop("layer_index")
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(snap["nfb_config"])
    with pytest.raises(ValueError, match="LAYER_SLOT_OUTSIDE|SLOT_OUTSIDE"):
        receiving_nfb_layer_centers(snap,"upper")
