# -*- coding: utf-8 -*-
"""#1502/#1503: prove actual manufactured/assembled inner-door skins own NFB Z."""
from copy import deepcopy
import pytest

from ae_engine.assembly_placement import (
    resolve_inner_door_panel_placement, resolve_base_plate_placement,
)
from ae_engine.receiving_nfb_world_skin_datums import (
    receiving_inner_door_real_world_skins,
    resolve_receiving_nfb_world_skin_datums,
)


def _cabinet(offset=80.0):
    return {
        "model":"受電箱", "w":800., "h":1600., "d":350., "t":2., "fw":29.,
        "door_gap_w":3.5,"door_gap_h":3.5, "multi_door_enabled":True,
        "door_layout_scope":"receiving-main",
        "door_layout_columns":[[800.,[1100.,500.]]],
        "inner_doors":[{
            "stable_id":"upper", "cell_key":"0:0",
            "included_frame_sides":["top","left","right"],
            "inward_offset_mm":offset,
        }],
    }


def test_true_folded_inner_door_core_has_t2_skins_not_placement_center():
    snapshot=_cabinet()
    outward, inward=receiving_inner_door_real_world_skins(snapshot,"upper")
    assert outward-inward == pytest.approx(2.0)
    center=resolve_inner_door_panel_placement(snapshot,"upper").world_offset[2]
    assert center == 95.0
    # The folded core sheet is not the complete four-flange bounds center.
    assert outward != pytest.approx(center)
    assert inward != pytest.approx(center)


def test_shihlin_107_72_net_z_measures_true_physical_skins_and_common_ear_contact():
    snap=_cabinet()
    chain=resolve_receiving_nfb_world_skin_datums(
        snap, inner_door_id="upper",
        reference_nfb_depth_mm=107.,
        secondary_nfb_depth_mm=72.,
    )
    assert chain.deep_nfb_net_clearance_mm == pytest.approx(107)
    assert (chain.inner_door_inner_skin_world_z_mm
            -chain.shallow_nfb_face_world_z_mm) == pytest.approx(72)
    assert chain.shallow_nfb_face_world_z_mm-chain.base_nfb_face_world_z_mm == pytest.approx(35)
    assert chain.shallow_base_back_skin_world_z_mm-chain.base_nfb_face_world_z_mm == pytest.approx(33)
    assert chain.base_nfb_face_world_z_mm-chain.base_back_skin_world_z_mm == pytest.approx(2)
    assert chain.fixing_plate_contact_skin_world_z_mm == chain.base_back_skin_world_z_mm
    assert (chain.fixing_plate_contact_skin_world_z_mm
            -chain.fixing_plate_back_skin_world_z_mm) == pytest.approx(3)
    # Old buggy rear-wall-placement remains measurably distinct; resolving
    # physical surfaces here cannot be replaced by -D/2+T+BEND/2.
    old=resolve_base_plate_placement(snap,"base_plate").world_offset[2]
    assert old != pytest.approx(chain.base_nfb_face_world_z_mm)


def test_adjusting_inner_door_offset_relocates_nfb_and_ear_targets_as_one_group():
    before=resolve_receiving_nfb_world_skin_datums(
        _cabinet(80),inner_door_id="upper",
        reference_nfb_depth_mm=107,secondary_nfb_depth_mm=72,
    )
    after=resolve_receiving_nfb_world_skin_datums(
        _cabinet(95),inner_door_id="upper",
        reference_nfb_depth_mm=107,secondary_nfb_depth_mm=72,
    )
    for attr in (
        "inner_door_outer_skin_world_z_mm",
        "inner_door_inner_skin_world_z_mm",
        "base_nfb_face_world_z_mm",
        "base_back_skin_world_z_mm",
        "fixing_plate_contact_skin_world_z_mm",
        "fixing_plate_back_skin_world_z_mm",
        "shallow_nfb_face_world_z_mm",
        "shallow_base_back_skin_world_z_mm",
    ):
        assert getattr(before,attr)-getattr(after,attr) == pytest.approx(15)
    assert before.deep_nfb_net_clearance_mm == after.deep_nfb_net_clearance_mm == pytest.approx(107)


def test_changing_brand_depth_moves_only_base_and_both_fixed_ears_not_inner_door():
    a=resolve_receiving_nfb_world_skin_datums(
        _cabinet(), inner_door_id="upper",
        reference_nfb_depth_mm=107,secondary_nfb_depth_mm=72,
    )
    b=resolve_receiving_nfb_world_skin_datums(
        _cabinet(), inner_door_id="upper",
        reference_nfb_depth_mm=103,secondary_nfb_depth_mm=68,
    )
    assert a.inner_door_inner_skin_world_z_mm == pytest.approx(b.inner_door_inner_skin_world_z_mm)
    assert a.base_nfb_face_world_z_mm-b.base_nfb_face_world_z_mm == pytest.approx(-4)
    assert a.fixing_plate_contact_skin_world_z_mm-b.fixing_plate_contact_skin_world_z_mm == pytest.approx(-4)
    assert b.deep_nfb_net_clearance_mm == pytest.approx(103)


def test_invalid_shallow_depth_or_unavailable_inner_door_does_not_invent_world_z():
    with pytest.raises(ValueError):
        resolve_receiving_nfb_world_skin_datums(
            _cabinet(),inner_door_id="upper",
            reference_nfb_depth_mm=107,secondary_nfb_depth_mm=106,
        )
    with pytest.raises(ValueError,match="one physical inner door"):
        receiving_inner_door_real_world_skins(_cabinet(),"wrong")
