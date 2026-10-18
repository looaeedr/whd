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
    assert len({r.actual_base_back_skin_world_z_mm for r in receipts}) == 2
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
    """Current NFB source is per-brand CSV, NOT a legacy switch-brand DXF."""
    snap = _two_tier()
    snap["receiving_layout"]["sets"][0].pop("switch_brand", None)
    for row, (brand, model) in zip(
        snap["nfb_config"]["holes"],
        (("士林", "nfbv5:士林:2P400"), ("東元", "nfbv5:東元:3P125SN")),
    ):
        row.update(source_brand=brand, model_filename=model)
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snap["nfb_config"],
    )
    parts = expand_receiving_nfb_layer_parts(snap, (_source(snap),))
    receipts = validate_receiving_tier_fixing_contact_receipts(snap, parts)
    assert len(receipts) == 4
    assert [r.layer_index for r in receipts] == [0, 0, 1, 1]
    assert [r.fixing_hole_world_x_mm for r in receipts] == [
        -335., 335., -335., 335.,
    ]
    assert len({r.actual_base_back_skin_world_z_mm for r in receipts}) == 2
    assert all(not r.manufacturing_ready for r in receipts)


@pytest.mark.parametrize("contamination", (
    "open_cutting", "cutting_circle", "marking_line", "extra_bend",
))
def test_ear_receipt_rejects_extra_source_primitives_even_with_five_valid_cuts(
    monkeypatch, contamination,
):
    """The source witness must validate the whole scene, not only five closed cuts."""
    from ae_engine import receiving_base_fixing_plate_geometry as geometry
    from ae_engine.sheetmetal_drawing import DrawingScene

    original = geometry.build_fixing_plate_source_render_data

    def contaminated_source(*args, **kwargs):
        data = original(*args, **kwargs)
        scene = DrawingScene(list(data.scene.primitives))
        if contamination == "open_cutting":
            scene.add_line((0., 2.), (20., 2.), layer="CUTTING")
        elif contamination == "cutting_circle":
            scene.add_circle((12., 12.), 2., layer="CUTTING")
        elif contamination == "marking_line":
            scene.add_line((0., 5.), (20., 5.), layer="MARKING")
        else:
            scene.add_line((0., 24.), (256., 24.), layer="BEND", color=5)
        return replace(data, scene=scene)

    monkeypatch.setattr(geometry, "build_fixing_plate_source_render_data",
                        contaminated_source)
    snapshot, parts = _real_two_tier_parts()
    with pytest.raises(ValueError, match="EAR_RECEIPT_SOURCE_EAR_CUTTING_OR_BEND_DRIFT"):
        validate_receiving_tier_fixing_contact_receipts(snapshot, parts)
