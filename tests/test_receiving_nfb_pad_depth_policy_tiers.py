# -*- coding: utf-8 -*-
"""#1503: PAD draft depth preview must agree with universal per-tier generator."""
from copy import deepcopy

import pytest

from ae_engine.receiving_nfb_ui1a import new_nfb_ui1a_draft, add_nfb_draft_slot
from ae_engine.receiving_nfb_pad_depth_policy import (
    DIFFERENT_DEPTH, NEEDS_SOURCE, NO_PAD_NEEDED, NOT_APPLICABLE,
    preview_nfb_pad_depth,
)


def _draft(*layers):
    draft=new_nfb_ui1a_draft(set_brand="士林",layer_count=len(layers))
    for layer_index,names in enumerate(layers):
        for model in names:
            draft=add_nfb_draft_slot(
                draft,layer_index,filename=f"nfbv5:士林:{model}",
                source_brand="士林",
            )
    return draft


def test_readonly_depth_review_pair_has_one_non_mfg_pad():
    p=preview_nfb_pad_depth(_draft(("3P400SN","100HN-s")))
    assert p.status==DIFFERENT_DEPTH
    assert p.depth_mm==(107.,68.)
    assert p.candidate_delta_mm==39.
    assert p.required_pad_count==1
    assert p.tier_pad_counts==(1,)
    assert (p.shallower_unit_index,p.deeper_unit_index)==(1,0)
    assert p.manufacturing_ready is False


def test_three_same_tier_switches_produce_two_source_derived_pad_requirements():
    p=preview_nfb_pad_depth(_draft(("3P400SN","100HN-s","2P125SN")))
    assert p.status==DIFFERENT_DEPTH
    assert p.required_pad_count==2
    assert p.tier_pad_counts==(2,)
    assert (p.shallower_unit_index,p.deeper_unit_index)==(None,None)
    assert p.manufacturing_ready is False


def test_two_layers_must_not_compare_depths_across_physical_tiers():
    p=preview_nfb_pad_depth(_draft(("3P400SN",),("100HN-s",)))
    assert p.status==NO_PAD_NEEDED
    assert p.required_pad_count==0
    assert p.tier_pad_counts==(0,0)
    assert p.manufacturing_ready is False


def test_two_tiers_have_separate_nfb_pad_counts():
    p=preview_nfb_pad_depth(_draft(
        ("3P400SN","100HN-s"),("3P400SN","100HN-s","2P125SN"),
    ))
    assert p.status==DIFFERENT_DEPTH
    assert p.unit_count==5
    assert p.required_pad_count==3
    assert p.tier_pad_counts==(1,2)
    assert p.candidate_delta_mm==39.
    assert p.manufacturing_ready is False


def test_source_unknown_rejects_invented_count_even_on_one_known_tier():
    d=_draft(("3P400SN","100HN-s"),("3P400SN","100HN-s"))
    d=deepcopy(d)
    d["layers"][1]["slots"][1]["source_brand"]="東元"
    p=preview_nfb_pad_depth(d)
    assert p.status==NEEDS_SOURCE
    assert p.required_pad_count==0
    assert p.tier_pad_counts==(0,0)
    assert p.depth_mm[-1] is None


def test_single_model_does_not_create_pad_or_guess_reference_depth():
    p=preview_nfb_pad_depth(_draft(("100HN-s",)))
    assert p.status==NOT_APPLICABLE
    assert p.required_pad_count==0
    assert p.manufacturing_ready is False


def test_hidden_populated_layer_is_not_silently_dropped():
    d=_draft(("3P400SN",),("100HN-s",))
    d["layer_count"]=1
    with pytest.raises(ValueError,match="hidden"):
        preview_nfb_pad_depth(d)


def test_existing_numeric_v5_model_without_depth_is_unknown_not_exception():
    # 1PBH is a *real selectable model* in current 士林 V5 CSV but does
    # not have NFB深_mm. No sibling/filename is permitted to supply it.
    draft=_draft(("3P400SN", "1PBH"))
    p=preview_nfb_pad_depth(draft)
    assert p.status==NEEDS_SOURCE
    assert p.depth_mm==(107.,None)
    assert p.required_pad_count==0
    assert p.tier_pad_counts==(0,)
    assert p.candidate_delta_mm is None
    assert p.manufacturing_ready is False


def test_extra_empty_layer_does_not_cancel_existing_physical_tier_pad():
    draft=_draft(("3P400SN", "100HN-s"), ())
    p=preview_nfb_pad_depth(draft)
    assert p.status==DIFFERENT_DEPTH
    assert p.layer_count==2
    assert p.tier_pad_counts==(1,0)
    assert p.required_pad_count==1
    assert p.manufacturing_ready is False
