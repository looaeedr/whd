# -*- coding: utf-8 -*-
"""#1502 actual distinct FinalScene Base Plate parts for both NFB upper tiers."""
from copy import deepcopy

import pytest

from ae_engine.contracts import BasePlatePartSpec
from ae_engine.manufacturing_scene_orchestration import build_part_render_data
from ae_engine.receiving_base_plate_3d_profiles import receiving_base_plate_3d_profiles
from ae_engine.receiving_base_plate_config import receiving_base_plate_values
from ae_engine.receiving_nfb_layer_physical_parts import (
    PREVIEW_STATUS, expand_receiving_nfb_layer_parts,
)
from phase6_final_scene_contracts import AssemblyScenePart
from tests.test_receiving_base_physical_3d_z_assembly import _assembled


def _two_tier():
    snap = _assembled()
    saved = deepcopy(snap["nfb_config"])
    saved["layer_count"] = 2
    for i, hole in enumerate(saved["holes"]):
        hole.update(
            layer_count=2, layer_index=i, slot_index=0,
            physical_hole_id=f"tier:{i}:switch",
        )
    snap["nfb_config"] = saved
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(saved)
    snap["receiving_inner_door_layer_heights_mm"] = [330, 830]
    return snap


def _source(snapshot):
    physical=receiving_base_plate_values(snapshot)
    cfg=BasePlatePartSpec(
        width=float(snapshot["w"]), height=float(physical["h"]),
        thickness=float(snapshot["t"]),
        shrink_top=float(physical["base_plate_shrink_top"]),
        shrink_bottom=float(physical["base_plate_shrink_bottom"]),
        shrink_left=float(physical["base_plate_shrink_left"]),
        shrink_right=float(physical["base_plate_shrink_right"]),
        bend=float(physical["base_plate_bend"]),
        model_name="受電箱",
        receiving_bend_pattern=physical["receiving_bend_pattern"],
        receiving_nfb_depth_pair_mm=physical["receiving_nfb_depth_pair_mm"],
        physical_id="base_plate",
    )
    rd=build_part_render_data(cfg)
    profiles=receiving_base_plate_3d_profiles(snapshot,physical)
    return AssemblyScenePart(
        part_key="base_plate",render_data=rd,
        x_profile=tuple(profiles["X"]),y_profile=tuple(profiles["Y"]),
        placement="offset",offset=(0.,0.,-163.),
    )


def test_two_source_nfb_layers_produce_two_distinct_real_blank_finalscenes():
    snapshot=_two_tier()
    source=_source(snapshot)
    physical=expand_receiving_nfb_layer_parts(snapshot,(source,))
    assert len(physical)==2
    assert tuple(p.part_key for p in physical)==(
        "base_plate:nfb_layer:0","base_plate:nfb_layer:1"
    )
    # One Z formula per tier: source model depths differ, hence two true
    # independently installed Base Plate offsets (not copied root -163).
    from ae_engine.receiving_tier_ear_z_targets import (
        resolve_receiving_tier_base_z_targets,
    )
    targets = resolve_receiving_tier_base_z_targets(snapshot)
    assert [p.offset[0] for p in physical] == pytest.approx([0.,0.])
    assert [p.offset[1] for p in physical] == pytest.approx([470.,-30.])
    assert [p.offset[2] for p in physical] == pytest.approx([
        x.world_offset_z_mm for x in targets
    ])
    assert len({p.offset[2] for p in physical}) == 2
    assert all(x.physical_skin_z_resolved for x in targets)
    assert physical[0].render_data is not source.render_data
    assert physical[1].render_data is not physical[0].render_data
    assert [p.render_data.unfolded_topology.piece_id for p in physical]==[
        "base_plate:nfb_layer:0","base_plate:nfb_layer:1"
    ]
    assert physical[0].render_data.material.area==pytest.approx(
        physical[1].render_data.material.area
    )
    assert physical[0].render_data.metadata["manufacturing_ready"] is False
    assert physical[1].render_data.metadata["nfb_layer_manufacturing_status"]==PREVIEW_STATUS
    assert len(physical[0].x_profile)==5
    # DO NOT claim verified screw holes or left/right ear manufacture.


def test_horizontal_nfb_screw_x_cannot_move_either_tier_physical_base():
    snapshot=_two_tier()
    for row,x in zip(snapshot["nfb_config"]["holes"],(-120.,180.)):
        row.update(
            manual_x_state="CONFIRMED",manual_x_mm=x,
            datum_revision="source-X",datum_snapshot={"w":800,"t":2},
        )
    snapshot["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(
        snapshot["nfb_config"]
    )
    result=expand_receiving_nfb_layer_parts(snapshot,(_source(snapshot),))
    # The two NFB screw groups have independent X adjustments, but BOTH
    # physical plates stay centered in cabinet X for their fixed ear mounts.
    assert [p.offset[0] for p in result]==pytest.approx([0.,0.])
    assert [p.offset[1] for p in result]==pytest.approx([470.,-30.])


def test_one_tier_keeps_the_existing_independently_verified_real_z_part():
    snapshot=_assembled()
    p=_source(snapshot)
    assert expand_receiving_nfb_layer_parts(snapshot,(p,))==(p,)


def test_unsubmitted_two_tier_is_not_auto_made_into_certified_parts():
    snapshot=_two_tier()
    snapshot["nfb_config_submitted"]=False
    original=_source(snapshot)
    assert expand_receiving_nfb_layer_parts(snapshot,(original,))==(original,)


def test_two_tier_missing_original_base_part_fails_instead_of_one_plate_illusion():
    with pytest.raises(ValueError,match="SOURCE_BASE_PLATE_MISSING"):
        expand_receiving_nfb_layer_parts(_two_tier(),())



def test_real_mode_switch_stale_selection_does_not_break_one_tier_or_draft():
    snap=_assembled()
    snap["_receiving_runtime_selection"]["set_id"]="obsolete-view"
    p=_source(snap)
    assert expand_receiving_nfb_layer_parts(snap,(p,))==(p,)
    snap=_two_tier()
    snap["_receiving_runtime_selection"]["set_id"]="obsolete-view"
    p=_source(snap)
    assert expand_receiving_nfb_layer_parts(snap,(p,))==(p,)
    snap=_two_tier()
    snap["nfb_config_submitted"]=False
    p=_source(snap)
    assert expand_receiving_nfb_layer_parts(snap,(p,))==(p,)
