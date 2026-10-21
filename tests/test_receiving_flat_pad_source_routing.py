# -*- coding: utf-8 -*-
"""A real submitted LEFT flat base consumes common PAD geometry, not magic depths."""
from copy import deepcopy
import pytest

from ae_engine.receiving_base_plate_config import receiving_base_plate_values
from ae_engine.receiving_nfb_depth_surface_policy import committed_receiving_flat_nfb_depth_mm
from ae_engine.assembly_placement import resolve_assembly_placement
from ae_engine.receiving_nfb_numeric_catalog import model_spec
from ae_engine.receiving_nfb_pad_generator import (
    generate_nfb_pad_patterns,read_pad_tooling_rule,
)
from tests.test_receiving_flat_base_single_nfb_true_z import _flat


def _mixed():
    snap=_flat()
    first=snap["nfb_config"]["holes"][0]
    first["model_filename"]="nfbv5:士林:3P400SN"
    first["source_brand"]="士林"
    second=deepcopy(first)
    second["physical_hole_id"]="nfb:pad:100HN"
    second["model_filename"]="nfbv5:士林:100HN-s"
    second["slot_index"]=0  # same physical NFB tier (not a second tier)
    snap["nfb_config"]["holes"].append(second)
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(snap["nfb_config"])
    return snap


def test_submitted_flat_two_different_depths_reach_real_left_base_with_one_pad():
    snap=_mixed()
    assert committed_receiving_flat_nfb_depth_mm(snap)==pytest.approx(107.)
    values=receiving_base_plate_values(snap)
    assert values["receiving_bend_pattern"]=="LEFT_FLAT_SIDE"
    assert values["receiving_nfb_reference_depth_mm"]==pytest.approx(107.)
    assert values["receiving_nfb_depth_pair_mm"] is None
    pads=generate_nfb_pad_patterns(
        (model_spec("士林","3P400SN"), model_spec("士林","100HN-s")),
        plate_thickness_mm=2,tooling=read_pad_tooling_rule())
    assert len(pads)==1
    assert (pads[0].switch_index,pads[0].rise_mm,pads[0].blank_width_mm)==(1,39.,145.)
    # Correct shallow-side installation MUST NOT translate the common Base.
    placed=resolve_assembly_placement(snap,"base_plate")
    assert placed.relationship=="RECEIVING_NFB_SKIN_DEPTH"
    assert placed.world_offset[0]==pytest.approx(0.)


def test_existing_center_variant_keeps_its_double_fold_instead_of_double_pad():
    snap=_mixed()
    snap["receiving_base_plate"]["pattern"]="CENTER_DOUBLE_SIDE_FOLD"
    values=receiving_base_plate_values(snap)
    assert values["receiving_bend_pattern"]=="CENTER_DOUBLE_SIDE_FOLD"
    assert values["receiving_nfb_depth_pair_mm"]==(107.,68.)


def test_pad_missing_numeric_source_does_not_borrow_older_model_dimensions():
    snap=_mixed()
    snap["nfb_config"]["holes"][1]["model_filename"]="nfbv5:士林:NOT_A_MODEL"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(snap["nfb_config"])
    with pytest.raises(ValueError):
        receiving_base_plate_values(snap)


def test_same_tier_different_depths_auto_selects_common_pad_not_center():
    """The real GUI has no manual base at first: do not hide a valid PAD."""
    snap = _mixed()
    snap.pop("receiving_base_plate", None)
    resolved = receiving_base_plate_values(snap)
    assert resolved["receiving_bend_pattern"] == "LEFT_FLAT_SIDE"
    assert resolved["receiving_nfb_reference_depth_mm"] == pytest.approx(107.)
    assert resolved["receiving_nfb_depth_pair_mm"] is None


def test_stored_explicit_center_remains_supported_for_existing_projects():
    """Do not delete or reinterpret old operator-selected CENTER geometry."""
    snap = _mixed()
    assert snap["receiving_base_plate"]["pattern"] == "LEFT_FLAT_SIDE"
    snap["receiving_base_plate"]["pattern"] = "CENTER_DOUBLE_SIDE_FOLD"
    result = receiving_base_plate_values(snap)
    assert result["receiving_bend_pattern"] == "CENTER_DOUBLE_SIDE_FOLD"
    assert result["receiving_nfb_depth_pair_mm"] == (107., 68.)
