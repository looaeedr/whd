# -*- coding: utf-8 -*-
"""#1503 real V5 CSV 2P400 source is sufficient for 2 physical NFB-tier bases.

This test uses REAL source FinalScene and UV/contact solvers. It does not
certify the native GUI projection (tested separately and currently RED).
"""
from copy import deepcopy

from ae_engine.receiving_nfb_layer_physical_parts import expand_receiving_nfb_layer_parts
from ae_engine.receiving_tier_ear_assembly_xy import resolve_receiving_tier_ear_mating_xy
from ae_engine.receiving_fixed_plate_formed_skins import build_receiving_formed_fixing_plate_skins
from ae_engine.receiving_joint_marking import resolve_receiving_joint_markings
from ae_engine.receiving_ear_side_manufacturing_marking import with_verified_receiving_ear_side_markings
from ae_engine.manufacturing_scene_access import owner_render_data
from tests.test_issue1050_receiving_mother_plate_marking import (
    _snapshot as _full_box_snapshot, _full_receiving_geometry,
)
from tests.test_receiving_two_tier_physical_base_parts import _two_tier, _source


def _actual_csv_world():
    current = _two_tier()
    for hole in current["nfb_config"]["holes"]:
        hole["model_filename"] = "nfbv5:士林:2P400"
        hole["source_brand"] = "士林"
    current["receiving_layout"]["sets"][0]["switch_brand"] = "士林"
    current["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        current["nfb_config"]
    )
    return current


def test_real_same_csv_model_in_both_tiers_folds_2_base_and_4_fixed_plates():
    s = _actual_csv_world()
    parts = expand_receiving_nfb_layer_parts(s, (_source(s),))
    assert tuple(p.part_key for p in parts) == (
        "base_plate:nfb_layer:0", "base_plate:nfb_layer:1"
    )
    assert [round(float(p.offset[1]), 5) for p in parts] == [470., -30.]
    assert all(p.render_data.material.area > 0
               and p.render_data.metadata.get("manufacturing_ready") is False
               for p in parts)
    owners = resolve_receiving_tier_ear_mating_xy(s)
    assert len(owners) == 4
    assert len({p.ear_id for p in owners}) == 4
    for owner in owners:
        formed = build_receiving_formed_fixing_plate_skins(s, owner.ear_id)
        assert formed.base_part_id == owner.parent_base_id
        assert len(formed.mapped_world_skins) > 0
        assert not formed.manufacturing_ready


def test_real_same_csv_source_produces_side_markings_8_each_not_fake_lines():
    s = _full_box_snapshot()
    s.update(deepcopy(_actual_csv_world()))
    geometry = _full_receiving_geometry(s)
    joints = resolve_receiving_joint_markings(
        s, geometry, dimensions=(s["w"], s["h"], s["d"]),
        sheet_thickness=s["t"], cabinet_family="受電箱",
    )
    resolved = with_verified_receiving_ear_side_markings(
        s, joints.geometry, dimensions=(s["w"], s["h"], s["d"]),
        sheet_thickness=s["t"],
    )
    for side in ("box_body:left_side", "box_body:right_side"):
        physical = owner_render_data(resolved, side)
        assert physical is not None
        assert physical.metadata["receiving_ear_side_marking_segment_count"] == 8
        assert physical.metadata["manufacturing_ready"] is False
