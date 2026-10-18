# -*- coding: utf-8 -*-
"""#1502 one Base Plate per NFB layer, opening-group centre-to-centre."""
from copy import deepcopy

import pytest

from ae_engine.receiving_nfb_base_assembly_xy import receiving_source_nfb_base_assembly_xy
from tests.test_receiving_committed_nfb_depth_base_part_flow import _snapshot as _nfb
from tests.test_receiving_nfb_true_3d_world_skin_datums import _cabinet


def _state():
    cabinet=_cabinet()
    saved=_nfb()
    cabinet.update({
        "nfb_config_submitted":True,"nfb_config":deepcopy(saved["nfb_config"]),
        "receiving_layout":deepcopy(saved["receiving_layout"]),
        "_receiving_runtime_selection":deepcopy(saved["_receiving_runtime_selection"]),
    })
    return cabinet


def test_two_selected_nfb_opening_group_and_plate_share_y250():
    owner=receiving_source_nfb_base_assembly_xy(_state(),"upper")
    assert owner.world_y_mm == pytest.approx(250)
    assert owner.verified_world_x_mm is None
    assert owner.source_hole_count==2
    from ae_engine.assembly_placement import resolve_assembly_placement
    assert resolve_assembly_placement(_state(), "base_plate").world_offset[:2] == pytest.approx((0.,250.))


def test_confirmed_nfb_opening_group_x_is_plate_center_x():
    snap=_state()
    for row,x in zip(snap["nfb_config"]["holes"],(-100.,100.)):
        row.update(manual_x_state="CONFIRMED", manual_x_mm=x,
                   datum_revision="NFB-SOURCE-1",datum_snapshot={"w":800,"t":2})
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(snap["nfb_config"])
    owner=receiving_source_nfb_base_assembly_xy(snap,"upper")
    assert owner.verified_world_x_mm == pytest.approx(0)
    snap["nfb_config"]["holes"][1]["manual_x_state"]="RECONFIRM_REQUIRED"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(snap["nfb_config"])
    assert receiving_source_nfb_base_assembly_xy(snap,"upper").verified_world_x_mm is None


def test_operator_updated_hole_height_moves_this_tier_plate_center():
    snap=_state()
    snap["receiving_inner_door_layer_heights_mm"]=[330,830]
    selected=receiving_source_nfb_base_assembly_xy(snap,"upper")
    assert selected.world_y_mm == pytest.approx(470)
    from ae_engine.assembly_placement import resolve_assembly_placement
    assert resolve_assembly_placement(snap,"base_plate").world_offset[1] == pytest.approx(470)


def test_single_row_projection_rejects_mixed_nfb_layers_without_rejecting_cabinet():
    snap=_state()
    snap["nfb_config"]["holes"][1].update(layer_count=2,layer_index=1,slot_index=0)
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(snap["nfb_config"])
    # This helper resolves ONE NFB hole row; reject mixing row coords.
    # It is NOT a whole-cabinet rule forbidding two NFB layers/plates.
    with pytest.raises(ValueError,match="DISTINCT_ROWS"):
        receiving_source_nfb_base_assembly_xy(snap,"upper")


def test_unsubmitted_is_not_current_manufacturing_bay():
    snap=_state()
    snap["nfb_config_submitted"]=False
    assert receiving_source_nfb_base_assembly_xy(snap,"upper") is None
