# -*- coding: utf-8 -*-
"""#1502 physical NFB group Y must match already-certified manufactured Y."""
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


def test_two_selected_nfb_on_single_physical_row_own_y250_not_old_base_y0():
    owner=receiving_source_nfb_base_assembly_xy(_state(),"upper")
    assert owner.world_y_mm == pytest.approx(250)
    assert owner.verified_world_x_mm is None
    assert owner.source_hole_count==2


def test_validated_manual_x_rows_can_position_same_base_without_new_x_datum():
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


def test_operator_updated_real_inner_door_height_moves_base_y_source():
    snap=_state()
    snap["receiving_inner_door_layer_heights_mm"]=[330,830]
    selected=receiving_source_nfb_base_assembly_xy(snap,"upper")
    assert selected.world_y_mm == pytest.approx(470)


def test_two_distinct_y_layers_must_never_silently_share_one_bolt_plate():
    snap=_state()
    snap["nfb_config"]["holes"][1].update(layer_count=2,slot_index=1)
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(snap["nfb_config"])
    with pytest.raises(ValueError,match="DISTINCT_ROWS"):
        receiving_source_nfb_base_assembly_xy(snap,"upper")


def test_unsubmitted_is_not_current_manufacturing_bay():
    snap=_state()
    snap["nfb_config_submitted"]=False
    assert receiving_source_nfb_base_assembly_xy(snap,"upper") is None
