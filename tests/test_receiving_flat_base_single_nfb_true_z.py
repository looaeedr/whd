# -*- coding: utf-8 -*-
"""#1502: actual LEFT/RIGHT flat receiving plate uses single model CSV depth."""
from copy import deepcopy
import pytest
from ae_engine.assembly_placement import resolve_assembly_placement
from ae_engine.receiving_base_plate_config import receiving_base_plate_values
from ae_engine.receiving_base_plate_real_skins import receiving_base_actual_local_nfb_skins
from ae_engine.receiving_nfb_world_skin_datums import resolve_receiving_nfb_world_skin_datums
from tests.test_receiving_base_physical_3d_z_assembly import _assembled


def _flat(pattern="LEFT_FLAT_SIDE",model="400_140X257_107.dxf"):
    snap=_assembled()
    snap["receiving_base_plate"]={
        "pattern":pattern,
        "height":340. if pattern=="LEFT_FLAT_SIDE" else 360.,
        "shrink_top":20., "shrink_bottom":20.,
        "shrink_left":45., "shrink_right":45.,"bend":20.,
    }
    snap["nfb_config"]["holes"]=snap["nfb_config"]["holes"][:1]
    snap["nfb_config"]["holes"][0]["model_filename"]=model
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(snap["nfb_config"])
    return snap


@pytest.mark.parametrize("pattern",["LEFT_FLAT_SIDE","RIGHT_FLAT_SIDE"])
def test_actual_flat_base_single_400_depth_matches_inner_door_true_skin_world_z(pattern):
    snap=_flat(pattern)
    source=receiving_base_plate_values(snap)
    assert source["receiving_nfb_depth_pair_mm"] is None
    assert source["receiving_nfb_reference_depth_mm"] == pytest.approx(107)
    local,shallow=receiving_base_actual_local_nfb_skins(snap,source)
    assert shallow is None
    p=resolve_assembly_placement(snap,"base_plate")
    assert p.relationship=="RECEIVING_NFB_SKIN_DEPTH"
    assert p.world_offset[1]==pytest.approx(250)
    world=resolve_receiving_nfb_world_skin_datums(
        snap,inner_door_id="upper",reference_nfb_depth_mm=107,
    )
    assert p.world_offset[2]+local == pytest.approx(world.base_nfb_face_world_z_mm)
    assert world.inner_door_inner_skin_world_z_mm-(p.world_offset[2]+local)==pytest.approx(107)
    assert world.base_back_skin_world_z_mm==pytest.approx(world.fixing_plate_contact_skin_world_z_mm)


def test_single_flat_model_change_uses_actual_csv_68_not_107_magic():
    original=_flat()
    alternate=_flat(model="100_75X130_68.dxf")
    p=resolve_assembly_placement(original,"base_plate")
    q=resolve_assembly_placement(alternate,"base_plate")
    assert receiving_base_plate_values(alternate)["receiving_nfb_reference_depth_mm"] == pytest.approx(68)
    assert q.world_offset[2]-p.world_offset[2] == pytest.approx(39)
    assert q.world_offset[1]==pytest.approx(p.world_offset[1])


def test_submitted_flat_mixed_nfb_models_require_distinct_plates_or_pad():
    snap=_flat()
    second=deepcopy(snap["nfb_config"]["holes"][0])
    second["physical_hole_id"]="nfb:2"
    second["model_filename"]="125_90X155_72.dxf"
    snap["nfb_config"]["holes"].append(second)
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(snap["nfb_config"])
    with pytest.raises(ValueError,match="NEED_PAD_OR_CENTER"):
        resolve_assembly_placement(snap,"base_plate")


def test_flat_unknown_source_brand_or_model_fails_instead_of_guessing_depth():
    snap=_flat()
    snap["nfb_config"]["holes"][0]["source_brand"]="東元"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(snap["nfb_config"])
    with pytest.raises(ValueError,match="SOURCE_BRAND_DRIFT"):
        resolve_assembly_placement(snap,"base_plate")
    snap=_flat(model="NOT_INDEXED.dxf")
    with pytest.raises(ValueError,match="CSV_DEPTH_MISSING"):
        resolve_assembly_placement(snap,"base_plate")


def test_flat_preview_without_submitted_nfb_never_claims_real_source_z():
    snap=_flat()
    snap["nfb_config_submitted"]=False
    p=resolve_assembly_placement(snap,"base_plate")
    assert p.relationship=="BASE_PLATE"
    assert p.world_offset[2]==pytest.approx(-163)
