# -*- coding: utf-8 -*-
"""#1502: assembled Receiving NFB base is placed by actual physical skins.

The test builds the SAME 2D FinalScene, folded mesh and true T2 skins as the
viewer; it never substitutes the old envelope centre or claimed 80-mm skin.
"""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from ae_engine.assembly_placement import resolve_assembly_placement
from ae_engine.receiving_base_plate_config import receiving_base_plate_values
from ae_engine.receiving_base_plate_real_skins import receiving_base_actual_local_nfb_skins
from ae_engine.receiving_nfb_world_skin_datums import resolve_receiving_nfb_world_skin_datums
from tests.test_receiving_committed_nfb_depth_base_part_flow import _snapshot as _nfb_snapshot
from tests.test_receiving_nfb_true_3d_world_skin_datums import _cabinet


def _assembled(shallow="125_90X155_72.dxf", offset=80.0):
    snap = _cabinet(offset)
    saved = _nfb_snapshot(shallow=shallow)
    snap.update({
        "receiving_base_plate":deepcopy(saved["receiving_base_plate"]),
        "receiving_layout":deepcopy(saved["receiving_layout"]),
        "_receiving_runtime_selection":deepcopy(saved["_receiving_runtime_selection"]),
        "nfb_config_submitted":True,
        "nfb_config":deepcopy(saved["nfb_config"]),
    })
    return snap


def test_original_source_33mm_bend_has_true_35mm_parallel_nfb_mounting_skins():
    snap=_assembled()
    physical=receiving_base_plate_values(snap)
    assert physical["receiving_nfb_depth_pair_mm"]==(107,72)
    deep,shallow=receiving_base_actual_local_nfb_skins(snap,physical)
    assert shallow-deep == pytest.approx(35)
    assert shallow-deep != pytest.approx(33)


def test_assembly_places_actual_deep_and_shallow_nfb_front_skins_to_inner_door_clearance():
    snap=_assembled()
    physical=receiving_base_plate_values(snap)
    local_deep,local_shallow=receiving_base_actual_local_nfb_skins(snap,physical)
    placement=resolve_assembly_placement(snap,"base_plate")
    world=resolve_receiving_nfb_world_skin_datums(
        snap,inner_door_id="upper",
        reference_nfb_depth_mm=107,secondary_nfb_depth_mm=72,
    )
    assert placement.relationship=="RECEIVING_NFB_SKIN_DEPTH"
    assert placement.anchor=="inner_door:source_nfb_physical_skin"
    # This is the SAME manufactured NFB upper-row centre, not the former
    # disconnected whole-cabinet plate Y=0.
    assert placement.world_offset[:2] == pytest.approx((0.0, 250.0))
    assert placement.world_offset[2]+local_deep == pytest.approx(world.base_nfb_face_world_z_mm)
    assert placement.world_offset[2]+local_shallow == pytest.approx(world.shallow_nfb_face_world_z_mm)
    assert (world.inner_door_inner_skin_world_z_mm -
            (placement.world_offset[2]+local_deep)) == pytest.approx(107)
    assert (world.inner_door_inner_skin_world_z_mm -
            (placement.world_offset[2]+local_shallow)) == pytest.approx(72)
    assert world.base_back_skin_world_z_mm == pytest.approx(world.fixing_plate_contact_skin_world_z_mm)


def test_selected_model_depth_change_repositions_plate_not_inner_door():
    first=_assembled()
    second=_assembled(shallow="100_75X130_68.dxf")
    a=resolve_assembly_placement(first,"base_plate")
    b=resolve_assembly_placement(second,"base_plate")
    f=receiving_base_plate_values(first)
    g=receiving_base_plate_values(second)
    d1,s1=receiving_base_actual_local_nfb_skins(first,f)
    d2,s2=receiving_base_actual_local_nfb_skins(second,g)
    assert s1-d1==pytest.approx(35)
    assert s2-d2==pytest.approx(39)
    assert a.world_offset[2]+d1 == pytest.approx(b.world_offset[2]+d2)
    assert (b.world_offset[2]+s2)-(a.world_offset[2]+s1) == pytest.approx(4)


def test_inner_door_inset_moves_source_mated_base_without_changing_clearance():
    a=_assembled(offset=80)
    b=_assembled(offset=95)
    p=resolve_assembly_placement(a,"base_plate")
    q=resolve_assembly_placement(b,"base_plate")
    assert p.world_offset[2]-q.world_offset[2] == pytest.approx(15)
    assert (resolve_assembly_placement(a,"inner_door:upper:panel").world_offset[2] -
            resolve_assembly_placement(b,"inner_door:upper:panel").world_offset[2]) == pytest.approx(15)


def test_legacy_unsubmitted_preview_keeps_original_rear_datum_without_fake_certification():
    snap=_cabinet()
    snap["receiving_base_plate"]={
        "pattern":"CENTER_DOUBLE_SIDE_FOLD","height":350.,
        "shrink_top":55.,"shrink_bottom":55.,"shrink_left":85.,"shrink_right":85.,
        "bend":20.,
    }
    old=resolve_assembly_placement(snap,"base_plate")
    assert old.relationship=="BASE_PLATE"
    assert old.anchor=="box_body:center:base_plate"
    assert old.world_offset[2] == pytest.approx(-163.)


def test_committed_pair_without_unique_inner_door_never_falls_back_to_wrong_rear_z():
    snap=_assembled()
    snap["inner_doors"]=[]
    with pytest.raises(ValueError,match="UNIQUE_UPPER_INNER_DOOR"):
        resolve_assembly_placement(snap,"base_plate")


def test_operator_layer_height_and_confirmed_X_move_actual_plate_xy_without_wrong_z():
    snap=_assembled()
    original=resolve_assembly_placement(snap,"base_plate")
    snap["receiving_inner_door_layer_heights_mm"]=[330,830]
    raised=resolve_assembly_placement(snap,"base_plate")
    assert original.world_offset[1]==pytest.approx(250)
    assert raised.world_offset[1]==pytest.approx(470)
    assert raised.world_offset[2]==pytest.approx(original.world_offset[2])

    for hole,x in zip(snap["nfb_config"]["holes"],(-130.,70.)):
        hole.update(manual_x_state="CONFIRMED",manual_x_mm=x,
                    datum_revision="SOURCE-X-REV1",datum_snapshot={"w":800,"t":2})
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(snap["nfb_config"])
    moved=resolve_assembly_placement(snap,"base_plate")
    assert moved.world_offset[:2]==pytest.approx((-30.,470.))
    assert moved.world_offset[2]==pytest.approx(original.world_offset[2])


def test_two_source_nfb_rows_fail_real_base_xyz_before_false_assembly():
    snap=_assembled()
    snap["nfb_config"]["holes"][1].update(layer_count=2,slot_index=1)
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(snap["nfb_config"])
    with pytest.raises(ValueError,match="DISTINCT_ROWS"):
        resolve_assembly_placement(snap,"base_plate")
