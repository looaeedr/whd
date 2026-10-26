# -*- coding: utf-8 -*-
"""#1503 actual-assembly-vs-EAR physical contact checks, without fake weld BEND."""
from copy import deepcopy
from dataclasses import replace

import pytest

from ae_engine.receiving_nfb_layer_physical_parts import (
    expand_receiving_nfb_layer_parts,
)
from ae_engine.receiving_tier_fixing_contact_receipt import (
    validate_receiving_tier_fixing_contact_receipts,
)
from tests.test_receiving_base_physical_3d_z_assembly import _assembled
from tests.test_receiving_two_tier_physical_base_parts import _two_tier, _source


def _real_two_tier_parts():
    snapshot = _two_tier()
    return snapshot, expand_receiving_nfb_layer_parts(
        snapshot, (_source(snapshot),),
    )


def test_four_real_ear_sources_mate_two_distinct_assembled_base_back_skins():
    snapshot, actual = _real_two_tier_parts()
    receipts = validate_receiving_tier_fixing_contact_receipts(snapshot, actual)
    assert len(receipts) == 4
    assert [r.ear_part_id for r in receipts] == [
        "base_plate:fixing_plate:nfb_layer:0:left",
        "base_plate:fixing_plate:nfb_layer:0:right",
        "base_plate:fixing_plate:nfb_layer:1:left",
        "base_plate:fixing_plate:nfb_layer:1:right",
    ]
    assert [r.base_part_id for r in receipts] == [
        "base_plate:nfb_layer:0", "base_plate:nfb_layer:0",
        "base_plate:nfb_layer:1", "base_plate:nfb_layer:1",
    ]
    assert [r.fixing_hole_world_x_mm for r in receipts] == [
        -335., 335., -335., 335.,
    ]
    assert [r.side_skin_world_x_mm for r in receipts] == [
        -398., 398., -398., 398.,
    ]
    assert [r.fixing_hole_world_y_mm for r in receipts] == [
        (400., 540.), (400., 540.),
        (-100., 40.), (-100., 40.),
    ]
    # All physical ears share the brand-wide maximum depth Z, while preserving
    # distinct layer parts, Y and X placement and real contact proof.
    assert len({r.actual_base_back_skin_world_z_mm for r in receipts}) == 1
    assert len({r.expected_ear_contact_world_z_mm for r in receipts}) == 1
    assert all(
        r.actual_base_back_skin_world_z_mm ==
        pytest.approx(r.expected_ear_contact_world_z_mm)
        for r in receipts
    )
    assert all(r.source_outline_verified and r.base_assembly_xyz_verified
               for r in receipts)
    assert all(not r.formed_ear_verified
               and not r.side_marking_export_approved
               and not r.manufacturing_ready for r in receipts)

def test_single_tier_uses_the_same_real_base_skin_and_ear_contact_rule():
    from ae_engine.assembly_placement import resolve_base_plate_placement
    snapshot = _assembled()
    original = _source(snapshot)
    offset = resolve_base_plate_placement(snapshot, "base_plate").world_offset
    part = replace(original, offset=tuple(offset))
    receipts = validate_receiving_tier_fixing_contact_receipts(
        snapshot, (part,),
    )
    assert len(receipts) == 2
    assert {r.base_part_id for r in receipts} == {"base_plate"}
    assert [r.fixing_hole_world_x_mm for r in receipts] == [-335., 335.]
    assert all(r.actual_base_back_skin_world_z_mm ==
               pytest.approx(r.expected_ear_contact_world_z_mm) for r in receipts)


def test_real_primary_base_plate_placement_kind_is_validated_not_mistaken_for_detached():
    """Original Phase6 scene uses 'base_plate', not fixture's 'offset' kind."""
    from ae_engine.assembly_placement import resolve_base_plate_placement

    snapshot = _assembled()
    contract = resolve_base_plate_placement(snapshot, "base_plate")
    assert contract.placement_kind == "base_plate"
    installed = replace(
        _source(snapshot), placement=contract.placement_kind,
        offset=contract.world_offset,
    )
    receipt = validate_receiving_tier_fixing_contact_receipts(snapshot, (installed,))
    assert len(receipt) == 2
    assert {row.base_part_id for row in receipt} == {"base_plate"}
    shifted = replace(installed, offset=(
        contract.world_offset[0], contract.world_offset[1],
        contract.world_offset[2] + 2.0,
    ))
    with pytest.raises(ValueError, match="ACTUAL_BASE_XYZ_DRIFT"):
        validate_receiving_tier_fixing_contact_receipts(snapshot, (shifted,))
    with pytest.raises(ValueError, match="BASE_NOT_OFFSET_PLACED"):
        validate_receiving_tier_fixing_contact_receipts(
            snapshot, (replace(installed, placement="standalone"),)
        )


@pytest.mark.parametrize("axis,shift", [(0, 0.5), (1, 5.), (2, -1.)])
def test_real_base_assembly_must_not_drift_from_ear_source_target(axis, shift):
    snap, physical = _real_two_tier_parts()
    first = physical[0]
    changed = list(first.offset)
    changed[axis] += shift
    damaged = (replace(first, offset=tuple(changed)), physical[1])
    with pytest.raises(ValueError, match="ACTUAL_BASE_XYZ_DRIFT"):
        validate_receiving_tier_fixing_contact_receipts(snap, damaged)


def test_second_tier_swapped_or_missing_actual_base_fails_closed():
    snap, physical = _real_two_tier_parts()
    with pytest.raises(ValueError, match="ACTUAL_BASE_PART_MISSING_OR_DUPLICATED"):
        validate_receiving_tier_fixing_contact_receipts(snap, (physical[0],))
    with pytest.raises(ValueError, match="ACTUAL_BASE_PART_MISSING_OR_DUPLICATED"):
        validate_receiving_tier_fixing_contact_receipts(
            snap, (physical[0], physical[0]),
        )
    broken_render = replace(
        physical[1].render_data,
        unfolded_topology=replace(
            physical[1].render_data.unfolded_topology,
            piece_id="base_plate:nfb_layer:0",
        ),
    )
    swapped = (physical[0], replace(physical[1], render_data=broken_render))
    with pytest.raises(ValueError, match="ACTUAL_BASE_SOURCE_MISSING"):
        validate_receiving_tier_fixing_contact_receipts(snap, swapped)


def test_ear_source_does_not_release_forming_marking_or_manufacture():
    snap, physical = _real_two_tier_parts()
    marked = replace(physical[0], render_data=replace(
        physical[0].render_data, metadata={
            **physical[0].render_data.metadata,
            "manufacturing_ready": True,
        },
    ))
    with pytest.raises(ValueError, match="PREMATURE_MFG_RELEASE"):
        validate_receiving_tier_fixing_contact_receipts(
            snap, (marked, physical[1]),
        )


def test_stale_set_bay_does_not_borrow_other_cabinet_contact_receipt():
    snap, physical = _real_two_tier_parts()
    snap["_receiving_runtime_selection"]["bay_id"] = "stale"
    with pytest.raises(ValueError, match="INCOMPLETE_PHYSICAL_OWNERS"):
        validate_receiving_tier_fixing_contact_receipts(snap, physical)


def test_horizontal_switch_x_moves_only_screws_not_ear_contacts():
    snap, physical = _real_two_tier_parts()
    before = validate_receiving_tier_fixing_contact_receipts(snap, physical)
    for hole, x in zip(snap["nfb_config"]["holes"], (-145., 100.)):
        hole.update(manual_x_state="CONFIRMED", manual_x_mm=x,
                    datum_revision="SOURCE-X-REV1",
                    datum_snapshot={"w": 800, "t": 2})
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"],
    )
    after = validate_receiving_tier_fixing_contact_receipts(snap, physical)
    assert after == before


def test_current_csv_two_tier_brands_keep_own_real_skin_and_four_ear_receipts():
    """Different brand catalogs cannot certify one shared physical ear Z."""
    snap = _two_tier()
    snap["receiving_layout"]["sets"][0].pop("switch_brand", None)
    for row, (brand, model) in zip(
        snap["nfb_config"]["holes"],
        (("士林", "nfbv5:士林:2P400"), ("東元", "nfbv5:東元:3P125SN")),
    ):
        row.update(source_brand=brand, model_filename=model)
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(snap["nfb_config"])
    parts = expand_receiving_nfb_layer_parts(snap, (_source(snap),))
    assert len(parts) == 2
    # Per-tier preview material may exist, but mixed-brand physical contact
    # must never be certified or considered ready for manufacturing.
    with pytest.raises(ValueError, match="EAR_Z_MIXED_BRANDS_REQUIRE_APPROVED_RULE"):
        validate_receiving_tier_fixing_contact_receipts(snap, parts)
