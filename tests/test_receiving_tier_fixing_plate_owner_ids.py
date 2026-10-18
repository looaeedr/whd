# -*- coding: utf-8 -*-
"""#1503: 2 NFB tiers => 2 independently mounted bases + 4 ear source previews."""
from copy import deepcopy
import pytest

from ae_engine.receiving_base_fixing_plate import (
    MANUFACTURING_STATUS,
    receiving_base_fixing_plate_previews,
)
from tests.test_receiving_two_tier_physical_base_parts import _two_tier
from tests.test_receiving_base_physical_3d_z_assembly import _assembled


def test_two_tiers_have_four_distinct_child_ear_ids_in_their_own_base():
    snap=_two_tier()
    ears=receiving_base_fixing_plate_previews(snap,available_parts=("base_plate",))
    assert len(ears)==4
    assert [e.part_id for e in ears]==[
        "base_plate:fixing_plate:nfb_layer:0:left",
        "base_plate:fixing_plate:nfb_layer:0:right",
        "base_plate:fixing_plate:nfb_layer:1:left",
        "base_plate:fixing_plate:nfb_layer:1:right",
    ]
    assert [e.parent_part_id for e in ears]==[
        "base_plate:nfb_layer:0","base_plate:nfb_layer:0",
        "base_plate:nfb_layer:1","base_plate:nfb_layer:1",
    ]
    assert [e.side for e in ears]==["left","right","left","right"]
    assert all(e.stock_thickness_mm==3 for e in ears)
    assert all(e.nominal_source_outline_mm==(256.,105.) for e in ears)
    assert all(e.applicable_slot_pair_indexes==(1,2) for e in ears)
    assert len({e.part_id for e in ears})==4
    assert all(e.manufacturing_status==MANUFACTURING_STATUS
               and not e.manufacturing_ready for e in ears)
    # No certification/false 3D BEND or side-wall MARKING.
    assert ears[0].nominal_fold_from_weld_edge_mm==pytest.approx(23)


def test_legacy_one_tier_still_returns_one_pair_of_original_child_ids():
    snap=_assembled()
    ears=receiving_base_fixing_plate_previews(snap,available_parts=("base_plate",))
    assert [e.part_id for e in ears]==[
        "base_plate:fixing_plate:left","base_plate:fixing_plate:right",
    ]
    assert [e.parent_part_id for e in ears]==["base_plate","base_plate"]


def test_invalid_or_unsubmitted_nfb_layer_owner_never_creates_four_false_ears():
    snap=_two_tier()
    snap["_receiving_runtime_selection"]["set_id"]="stale"
    assert receiving_base_fixing_plate_previews(
        snap,available_parts=("base_plate",))==()
    snap=_two_tier()
    snap["nfb_config_submitted"]=False
    result=receiving_base_fixing_plate_previews(
        snap,available_parts=("base_plate",))
    assert len(result)==2
    assert all(e.parent_part_id=="base_plate" for e in result)


def test_two_tier_source_children_visible_with_real_layer_part_keys():
    snap=_two_tier()
    ears=receiving_base_fixing_plate_previews(
        snap,available_parts=(
            "base_plate:nfb_layer:0","base_plate:nfb_layer:1",
        ))
    assert len(ears)==4
