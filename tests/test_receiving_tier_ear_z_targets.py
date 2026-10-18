# -*- coding: utf-8 -*-
"""#1503 installed ear Z target must never become fictitious formed weld proof."""
from copy import deepcopy
import pytest

from ae_engine.assembly_placement import resolve_base_plate_placement
from ae_engine.receiving_base_plate_config import receiving_base_plate_values
from ae_engine.receiving_base_plate_real_skins import receiving_base_actual_local_nfb_skins
from ae_engine.receiving_tier_ear_z_targets import resolve_receiving_tier_ear_contact_targets
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


def test_one_tier_source_base_back_skin_is_only_a_target_not_formed_ear():
    snap = _assembled()
    targets = resolve_receiving_tier_ear_contact_targets(snap)
    assert len(targets) == 2
    physical = receiving_base_plate_values(snap)
    front, _ = receiving_base_actual_local_nfb_skins(snap, physical)
    position = resolve_base_plate_placement(snap, "base_plate").world_offset
    target_z = position[2] + front - snap["t"]
    assert [x.ear_id for x in targets] == [
        "base_plate:fixing_plate:left", "base_plate:fixing_plate:right"
    ]
    assert [x.fixing_hole_world_x_mm for x in targets] == [-335.0, 335.0]
    assert [x.side_inside_weld_x_mm for x in targets] == [-398.0, 398.0]
    for row in targets:
        assert row.fixing_hole_world_y_mm == pytest.approx((180.,320.))
        assert row.base_back_skin_world_z_mm == pytest.approx(target_z)
        assert row.target_ear_contact_world_z_mm == pytest.approx(target_z)
        assert row.base_skin_z_source_verified
        assert not row.source_bend_verified
        assert not row.formed_weld_contact_verified
        assert not row.side_plate_marking_export_approved
        assert not row.manufacturing_ready


def test_source_skin_z_tracks_inner_door_inset_not_operator_switch_x():
    before = resolve_receiving_tier_ear_contact_targets(_assembled(offset=80))
    after = resolve_receiving_tier_ear_contact_targets(_assembled(offset=95))
    assert all(
        a.target_ear_contact_world_z_mm - b.target_ear_contact_world_z_mm
        == pytest.approx(15.)
        for a,b in zip(before,after)
    )
    changed = _assembled()
    for hole,x in zip(changed["nfb_config"]["holes"],(-150.,80.)):
        hole.update(
            manual_x_state="CONFIRMED", manual_x_mm=x,
            datum_revision="SOURCE-X-REV1", datum_snapshot={"w":800,"t":2},
        )
    changed["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        changed["nfb_config"]
    )
    assert resolve_receiving_tier_ear_contact_targets(changed) == before


def test_two_tiers_have_four_independent_ear_owners_but_no_certified_z():
    rows = resolve_receiving_tier_ear_contact_targets(_two_tier())
    assert len(rows) == 4
    assert [x.parent_base_id for x in rows] == [
        "base_plate:nfb_layer:0", "base_plate:nfb_layer:0",
        "base_plate:nfb_layer:1", "base_plate:nfb_layer:1",
    ]
    assert [x.ear_id for x in rows] == [
        "base_plate:fixing_plate:nfb_layer:0:left",
        "base_plate:fixing_plate:nfb_layer:0:right",
        "base_plate:fixing_plate:nfb_layer:1:left",
        "base_plate:fixing_plate:nfb_layer:1:right",
    ]
    assert [x.fixing_hole_world_x_mm for x in rows] == [-335,335,-335,335]
    assert [x.fixing_hole_world_y_mm for x in rows] == [
        (400.,540.),(400.,540.),(-100.,40.),(-100.,40.)
    ]
    assert all(x.base_back_skin_world_z_mm is None for x in rows)
    assert all(x.target_ear_contact_world_z_mm is None for x in rows)
    assert all(not x.base_skin_z_source_verified for x in rows)
    assert all(not x.source_bend_verified and not x.manufacturing_ready for x in rows)


def test_draft_or_stale_selection_never_creates_ear_contact():
    snap = _two_tier()
    snap["nfb_config_submitted"] = False
    assert resolve_receiving_tier_ear_contact_targets(snap) == ()
    snap = _two_tier()
    snap["_receiving_runtime_selection"]["bay_id"] = "stale"
    assert resolve_receiving_tier_ear_contact_targets(snap) == ()
