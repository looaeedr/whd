# -*- coding: utf-8 -*-
"""#1502: actual door + base pairing remains partial-only and source bound."""
from dataclasses import replace
import copy

import pytest

from ae_engine.receiving_nfb_base_process_projection import (
    build_existing_receiving_base_with_verified_nfb,
)
from ae_engine.receiving_nfb_cutting_manufacturing import (
    read_nfb_runtime_source_profiles_csv,
)
from ae_engine.receiving_nfb_pair_acceptance import validate_nfb_door_base_pair
from gui_modules.application.receiving_nfb_base_partial_export_action import (
    export_verified_receiving_nfb_base_plate,
)
from tests.test_issue1502_live_nfb_base_partial_export import _live


def _pair(tmp_path, pattern="CENTER_DOUBLE_SIDE_FOLD"):
    fixture = _live(tmp_path, pattern)
    profile, = read_nfb_runtime_source_profiles_csv(fixture.profile)
    composed = build_existing_receiving_base_with_verified_nfb(
        snapshot=fixture.snapshot,
        inner_door_id="upper",
        base_spec=fixture.plate,
        verified_inner_door=fixture.bundle.verified_door,
        source_path=fixture.original,
        profile=profile,
        lower_reference_handle=fixture.lower,
    )
    return fixture, composed


@pytest.mark.parametrize("pattern", (
    "LEFT_FLAT_SIDE", "CENTER_DOUBLE_SIDE_FOLD", "RIGHT_FLAT_SIDE",
))
def test_source_verified_real_door_and_real_base_have_same_NFB_and_Q(tmp_path, pattern):
    fixture, composed = _pair(tmp_path, pattern)
    receipt = validate_nfb_door_base_pair(
        snapshot=fixture.snapshot, inner_door_id="upper",
        verified_door=fixture.bundle.verified_door, composed_base=composed,
    )
    assert receipt.inner_door_part_id == "inner_door:upper:panel"
    assert receipt.base_plate_part_id == "base_plate"
    assert receipt.physical_part_count == 2
    assert receipt.nfb_instance_count == 2
    assert receipt.native_screw_cut_count == 8
    assert receipt.nfb_owner_ids == ("nfb:upper:1", "nfb:upper:2")
    assert receipt.source_sha256 == fixture.bundle.source_inventory.source_sha256
    assert receipt.approval_scope == "PAIR_PART_ONLY_EVIDENCE_NOT_WHOLE_MFG2"
    assert composed.render_data.metadata["receiving_base_ear_weld_z_verified"] is False


@pytest.mark.parametrize("mutation,reason", (
    ("sha", "ORIGINAL_SOURCE"),
    ("owner", "OWNER_OR_COUNT"),
    ("same_centroid_changed_x", "OWNER_OR_COUNT"),
    ("rotation", "OWNER_OR_COUNT"),
    ("datum", "SOURCE_INSTALLATION_DATUM_MISMATCH"),
    ("ear_datum", "MATING_XY_UNVERIFIED"),
    ("pattern", "BEND_PATTERN"),
))
def test_pair_fails_closed_on_mismatched_physical_evidence(tmp_path, mutation, reason):
    fixture, composed = _pair(tmp_path)
    door = fixture.bundle.verified_door
    if mutation == "sha":
        door = replace(door, source_sha256="0"*64)
    elif mutation == "owner":
        door = replace(door, physical_hole_ids=("nfb:upper:2", "nfb:upper:1"))
    elif mutation == "same_centroid_changed_x":
        witnessed = list(door.verified_hole_locations)
        witnessed[0] = (witnessed[0][0], -110., *witnessed[0][2:])
        witnessed[1] = (witnessed[1][0], 110., *witnessed[1][2:])
        door = replace(door, verified_hole_locations=tuple(witnessed))
    elif mutation == "rotation":
        witnessed = list(door.verified_hole_locations)
        row = witnessed[0]
        witnessed[0] = (*row[:4], 180)
        door = replace(door, verified_hole_locations=tuple(witnessed))
    elif mutation == "datum":
        metadata = dict(composed.render_data.metadata)
        metadata["receiving_base_nfb_row_center_world_xy_mm"] = (99., 250.)
        composed = replace(composed, render_data=replace(composed.render_data, metadata=metadata))
    elif mutation == "ear_datum":
        # NFB X may legitimately differ from the fixed plate X, but
        # changing the actual ear mounting X away from cabinet center
        # must remain a HARD fabrication/assembly rejection.
        metadata = dict(composed.render_data.metadata)
        metadata["receiving_base_ear_mount_center_world_xy_mm"] = (5., 250.)
        composed = replace(composed, render_data=replace(composed.render_data, metadata=metadata))
    elif mutation == "pattern":
        metadata = dict(composed.render_data.metadata)
        metadata["receiving_bend_pattern"] = "UNCONFIGURED"
        composed = replace(composed, render_data=replace(composed.render_data, metadata=metadata))
    with pytest.raises(ValueError, match=reason):
        validate_nfb_door_base_pair(
            snapshot=fixture.snapshot, inner_door_id="upper",
            verified_door=door, composed_base=composed,
        )


@pytest.mark.parametrize("field,value", (
    ("manual_x_mm", 110.),
    ("rotation_deg", 180),
    ("slot_index", 1),
))
def test_base_export_rejects_saved_config_without_matching_manufactured_door(
    tmp_path, field, value,
):
    fixture = _live(tmp_path)
    new_config = copy.deepcopy(fixture.bundle.config)
    new_config["holes"][1][field] = value
    from ae_engine.receiving_nfb_ui1b_bridge import _nfb_config_proof_sha256
    altered_bundle = replace(
        fixture.bundle, config=new_config,
        config_sha256_at_verification=_nfb_config_proof_sha256(new_config),
    )
    fixture.layout["sets"][0]["bays"][0]["nfb_config"] = new_config
    target = tmp_path / "no-false-green"
    target.mkdir()
    with pytest.raises(ValueError, match="CUTTING|slot|layer|rotation"):
        export_verified_receiving_nfb_base_plate(
            altered_bundle, layout=fixture.layout,
            current_snapshot=fixture.snapshot, base_spec=fixture.plate,
            output_directory=target, index_path=fixture.index,
            profile_path=fixture.profile,
        )
    assert list(target.iterdir()) == []
