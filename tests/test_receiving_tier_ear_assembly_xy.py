# -*- coding: utf-8 -*-
"""#1503 read-only W800/T2 source side-weld XY and NFB-tier fixing group."""
from copy import deepcopy
import pytest

from ae_engine.receiving_tier_ear_assembly_xy import (
    STATUS, resolve_receiving_tier_ear_mating_xy,
)
from tests.test_receiving_two_tier_physical_base_parts import _two_tier
from tests.test_receiving_base_physical_3d_z_assembly import _assembled


def _certify_center_x(snapshot,x_values):
    for hole,x in zip(snapshot["nfb_config"]["holes"], x_values):
        hole.update(
            manual_x_state="CONFIRMED",manual_x_mm=x,
            datum_revision="NFB-SOURCE-X-REV1",
            datum_snapshot={"w":800,"t":2},
        )
    snapshot["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(
        snapshot["nfb_config"]
    )
    return snapshot


def test_two_nfb_tiers_eight_symmetric_source_ear_fixing_slot_centers():
    snap=_certify_center_x(_two_tier(),(0.,0.))
    rows=resolve_receiving_tier_ear_mating_xy(snap)
    assert len(rows)==4
    assert [r.layer_index for r in rows]==[0,0,1,1]
    assert [r.side for r in rows]==["left","right","left","right"]
    assert [r.parent_base_id for r in rows]==[
        "base_plate:nfb_layer:0","base_plate:nfb_layer:0",
        "base_plate:nfb_layer:1","base_plate:nfb_layer:1",
    ]
    assert [r.selected_slot_column_x_mm for r in rows]==pytest.approx(
        [-335.,335.,-335.,335.]
    )
    assert [r.side_inside_weld_x_mm for r in rows]==pytest.approx(
        [-398.,398.,-398.,398.]
    )
    for actual, expected in zip(
        (r.selected_slot_pair_world_y_mm for r in rows),
        ((400.,540.),(400.,540.),(-100.,40.),(-100.,40.)),
    ):
        assert actual == pytest.approx(expected)
    assert rows[0].all_source_slots_world_y_mm == pytest.approx((365,400,540,575))
    assert rows[2].all_source_slots_world_y_mm == pytest.approx((-135,-100,40,75))
    assert all(r.selected_fixing_pitch_y_mm==pytest.approx(140) for r in rows)
    assert all(r.nominal_fold_reference_mm==pytest.approx(23) for r in rows)
    assert all(r.manufacturing_status==STATUS and not r.manufacturing_ready for r in rows)


def test_one_nfb_tier_outer_210_slot_pair_follows_opening_group_y():
    snap=_certify_center_x(_assembled(),(-100.,100.))
    snap["receiving_base_plate"]["pattern"]="LEFT_FLAT_SIDE"
    rows=resolve_receiving_tier_ear_mating_xy(snap)
    assert len(rows)==2
    assert [r.ear_id for r in rows]==[
        "base_plate:fixing_plate:left","base_plate:fixing_plate:right",
    ]
    for actual in (r.selected_slot_pair_world_y_mm for r in rows):
        assert actual == pytest.approx((145.,355.))
    assert all(r.selected_fixing_pitch_y_mm==pytest.approx(210) for r in rows)


def test_unconfirmed_nfb_x_does_not_move_fixed_ears_or_release_marking():
    rows=resolve_receiving_tier_ear_mating_xy(_two_tier())
    assert len(rows)==4
    assert all(row.base_center_x_mm==0 for row in rows)
    assert [row.selected_slot_column_x_mm for row in rows]==pytest.approx(
        [-335,335,-335,335]
    )
    assert all(row.nfb_group_x_mm is None and not row.manufacturing_ready
               for row in rows)


def test_nfb_horizontal_shift_changes_only_screw_source_not_plate_or_ears():
    original=resolve_receiving_tier_ear_mating_xy(
        _certify_center_x(_two_tier(),(0.,0.))
    )
    shifted=resolve_receiving_tier_ear_mating_xy(
        _certify_center_x(_two_tier(),(10.,-25.))
    )
    assert len(original)==len(shifted)==4
    assert [x.base_center_x_mm for x in shifted]==[0.,0.,0.,0.]
    assert [x.nfb_group_x_mm for x in shifted]==[10.,10.,-25.,-25.]
    assert [x.selected_slot_column_x_mm for x in shifted]==pytest.approx(
        [x.selected_slot_column_x_mm for x in original]
    )
    assert [x.side_inside_weld_x_mm for x in shifted]==pytest.approx(
        [x.side_inside_weld_x_mm for x in original]
    )
    assert all(not x.manufacturing_ready for x in shifted)


def test_switching_or_draft_does_not_create_stale_tier_welds():
    snap=_certify_center_x(_two_tier(),(0.,0.))
    snap["_receiving_runtime_selection"]["bay_id"]="stale"
    assert resolve_receiving_tier_ear_mating_xy(snap)==()
    snap=_certify_center_x(_two_tier(),(0.,0.))
    snap["nfb_config_submitted"]=False
    assert resolve_receiving_tier_ear_mating_xy(snap)==()
