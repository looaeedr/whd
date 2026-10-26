# -*- coding: utf-8 -*-
"""Two identical 125SN must use variable-width CENTER, with unmoving ear Z."""
from copy import deepcopy

import pytest

from ae_engine.assembly_placement import resolve_base_plate_placement
from ae_engine.receiving_base_plate_config import (
    receiving_base_plate_blank_dimensions, receiving_base_plate_values,
)
from ae_engine.receiving_base_plate_real_skins import receiving_base_actual_local_nfb_skins
from ae_engine.receiving_nfb_world_skin_datums import resolve_receiving_nfb_world_skin_datums
from ae_engine.receiving_tier_ear_z_targets import resolve_receiving_tier_ear_contact_targets
from tests.test_receiving_base_physical_3d_z_assembly import _assembled


def _two_125sn(model):
    snap = _assembled()
    assert len(snap["nfb_config"]["holes"]) == 2
    for hole in snap["nfb_config"]["holes"]:
        hole["source_brand"] = "士林"
        hole["model_filename"] = f"nfbv5:士林:{model}"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(snap["nfb_config"])
    return snap


@pytest.mark.parametrize("model,depth,second,blank", [
    ("2P125SN", 68., 37., 780.),
    ("3P125SN", 72., 33., 772.),
])
def test_brand_max_center_selection_and_dynamic_blank(model, depth, second, blank):
    snap = _two_125sn(model)
    values = receiving_base_plate_values(snap)
    assert values["receiving_bend_pattern"] == "CENTER_DOUBLE_SIDE_FOLD"
    assert values["receiving_center_brand_anchor_inverted"] is True
    assert values["receiving_nfb_depth_pair_mm"] == (107., depth)
    assert values["receiving_nfb_reference_depth_mm"] == depth
    assert receiving_base_plate_blank_dimensions(snap) == pytest.approx((blank, 240.))
    assert 107. - depth - snap["t"] == pytest.approx(second)


@pytest.mark.parametrize("model,depth", [
    ("2P125SN", 68.), ("3P125SN", 72.),
])
def test_equal_shallow_model_center_web_and_both_ear_support_wings_have_real_z(model, depth):
    snap = _two_125sn(model)
    values = receiving_base_plate_values(snap)
    web, wings = receiving_base_actual_local_nfb_skins(snap, values)
    assert wings - web == pytest.approx(-(107. - depth))
    actual = resolve_base_plate_placement(snap, "base_plate")
    selected = resolve_receiving_nfb_world_skin_datums(
        snap, inner_door_id="upper", reference_nfb_depth_mm=depth,
    )
    fixed = resolve_receiving_nfb_world_skin_datums(
        snap, inner_door_id="upper", reference_nfb_depth_mm=107.,
        fixing_plate_thickness_mm=2.,
    )
    assert actual.world_offset[2] + web == pytest.approx(selected.base_nfb_face_world_z_mm)
    assert actual.world_offset[2] + wings - snap["t"] == pytest.approx(
        fixed.fixing_plate_contact_skin_world_z_mm
    )
    contacts = resolve_receiving_tier_ear_contact_targets(snap)
    assert len(contacts) == 2
    assert all(row.base_skin_z_source_verified for row in contacts)
    assert all(row.target_ear_contact_world_z_mm ==
               pytest.approx(fixed.fixing_plate_contact_skin_world_z_mm)
               for row in contacts)
    assert all(not row.manufacturing_ready for row in contacts)


def test_changing_125sn_poles_alters_blank_but_not_brand_ear_z():
    a = _two_125sn("2P125SN")
    b = _two_125sn("3P125SN")
    assert receiving_base_plate_blank_dimensions(a)[0] == 780.
    assert receiving_base_plate_blank_dimensions(b)[0] == 772.
    before = resolve_receiving_tier_ear_contact_targets(a)
    after = resolve_receiving_tier_ear_contact_targets(b)
    assert [x.target_ear_contact_world_z_mm for x in before] == pytest.approx(
        [x.target_ear_contact_world_z_mm for x in after]
    )
