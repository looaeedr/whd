# -*- coding: utf-8 -*-
"""#1502 one assembly contract: ear mounts base; verified inner door owns NFB.

No new plate geometry or source coordinates are created here. This regression
ensures current EAR installation rules and NFB door-hole authority do NOT get
confused when no real NFB middle plate has been manufactured.
"""
from types import SimpleNamespace

import pytest

from ae_engine.receiving_weld_ear_policy import resolve_receiving_large_weld_ear_fit
from ae_engine.receiving_nfb_manufacturing_release import (
    NfbConfiguredInnerDoorHole, NfbValidatedInnerDoorRender, VALIDATED,
)
from ae_engine.receiving_nfb_dxf_source import NfbSourceInventory
from ae_engine.receiving_nfb_part_readiness import (
    BLOCKED, READY, NfbPhysicalScope, derive_nfb_part_readiness,
)

_SHA = "9" * 64


def _verified_door():
    return NfbValidatedInnerDoorRender(
        render_data=SimpleNamespace(metadata={
            "nfb_trial_status": VALIDATED, "nfb_trial_export_approved": True,
        }),
        part_id="inner_door:upper:panel",
        indexed_model_key=("士林", "400_140X257_107.dxf"),
        source_sha256=_SHA,
        physical_hole_ids=("nfb:A", "nfb:B"),
        verified_hole_locations=(
            ("nfb:A", -90.0, 1, 0, 0),
            ("nfb:B", 90.0, 1, 0, 90),
        ),
    )


def _nfb_source():
    return NfbSourceInventory(
        source_path="400_140X257_107.dxf",
        source_sha256=_SHA, source_id="NFB-DXF:" + _SHA,
        status="SOURCE_OBSERVED_UNCERTIFIED",
        entities=(), diagnostics=(),
        process_aci_entity_counts=((30, 8), (150, 1), (212, 4)),
        unresolved_color_entities=0,
        grouped_entity_counts=(("modelspace", 1),),
    )


@pytest.mark.parametrize("ear_y_pitch,slot_pair", [
    (210.0, (0, 3)), (140.0, (1, 2)),
])
def test_ear_mounting_does_not_invent_base_or_change_verified_inner_NFB(
    ear_y_pitch, slot_pair,
):
    door = _verified_door()
    # Existing factory contract, not a substitute for the actual base part.
    ear = resolve_receiving_large_weld_ear_fit(
        box_outer_width_mm=800.0,
        box_side_thickness_mm=2.0,
        fixing_hole_pitch_x_mm=670.0,
        fixing_hole_pitch_y_mm=ear_y_pitch,
    )
    assert ear.slot_pair_indexes == slot_pair
    assert ear.fixing_center_from_inside_skin_mm == pytest.approx(63.0)
    assert ear.ear_thickness_mm == pytest.approx(2.0)
    assert ear.nominal_fold_from_weld_edge_mm == pytest.approx(23.0)

    scope = NfbPhysicalScope(
        set_id="set", bay_id="bay", version_id="v1", submitted=True,
        inner_door_part_id=door.part_id,
        base_plate_part_ids=(), middle_plate_part_ids=(),
    )
    readiness = derive_nfb_part_readiness(
        scope, source_inventory=_nfb_source(), verified_inner_door=door,
    )
    assert readiness.for_part(door.part_id).status == READY
    assert "BASE_PLATE_PHYSICAL_ID_UNRESOLVED" in readiness.scope_reasons
    assert "MIDDLE_PLATE_PHYSICAL_ID_UNRESOLVED" not in readiness.scope_reasons
    assert readiness.decisions == (readiness.for_part(door.part_id),)
    assert not readiness.filter_export_part_ids(
        ("side_panel:left",), partial=True,
    )[1]
    with pytest.raises(ValueError, match="physical dependencies unresolved"):
        readiness.filter_export_part_ids((door.part_id,), partial=False)

    # NFB location stays under the already verified DOOR owner, regardless
    # of whether the factory ear mounts the base with 210 or 140 Y pitch.
    assert door.verified_hole_locations == (
        ("nfb:A", -90.0, 1, 0, 0), ("nfb:B", 90.0, 1, 0, 90)
    )


def test_source_color150_does_not_create_a_nonexistent_middle_plate():
    scope = NfbPhysicalScope(
        "set", "bay", "v1", True, "inner_door:upper:panel",
        base_plate_part_ids=(),
        middle_plate_part_ids=(),
    )
    got = derive_nfb_part_readiness(
        scope, source_inventory=_nfb_source(),
        verified_inner_door=_verified_door(),
    )
    assert len(got.decisions) == 1
    assert got.can_submit
    assert got.for_part("inner_door:upper:panel").status == READY
    assert got.for_part("unseen_nonexistent_middle").status != BLOCKED
    assert got.scope_reasons == ("BASE_PLATE_PHYSICAL_ID_UNRESOLVED",)


def test_factory_ear_must_not_be_approved_at_wrong_box_width():
    with pytest.raises(ValueError, match="W=800"):
        resolve_receiving_large_weld_ear_fit(
            box_outer_width_mm=750.0, box_side_thickness_mm=2.0,
            fixing_hole_pitch_x_mm=670.0, fixing_hole_pitch_y_mm=210.0,
        )
