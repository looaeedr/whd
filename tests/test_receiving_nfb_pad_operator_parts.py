# -*- coding: utf-8 -*-
"""Common PAD 2D operator PartReadOnlyData follows same committed V5 source."""
from copy import deepcopy
import pytest
from ae_engine.receiving_nfb_pad_operator_parts import committed_nfb_pad_draft_parts
from tests.test_receiving_flat_pad_source_routing import _mixed


def test_current_one_tier_csv_selection_generates_single_real_pad_2d_sheet():
    snap=_mixed()
    snap.pop("receiving_base_plate",None)
    parts=committed_nfb_pad_draft_parts(snap)
    assert len(parts)==1
    pad=parts[0]
    assert pad.parent_base_id=="base_plate"
    assert pad.pattern.rise_mm==pytest.approx(39.)
    assert pad.render_data.unfolded_topology.width==pytest.approx(149.)
    assert pad.render_data.unfolded_topology.height==pytest.approx(130.)
    assert pad.part_id.startswith("nfb_pad:")
    assert pad.part_id.endswith(snap["nfb_config"]["holes"][1]["physical_hole_id"])
    assert pad.manufacturing_ready is False
    assert pad.render_data.metadata["manufacturing_ready"] is False
    assert pad.render_data.metadata["nfb_deferred_manufacturing_role"]=="PAD"
    assert len(pad.render_data.fold_guides)==2


def test_existing_explicit_center_has_no_spurious_pad_navigation_or_double_compensation():
    snap=_mixed()
    snap["receiving_base_plate"]["pattern"]="CENTER_DOUBLE_SIDE_FOLD"
    assert committed_nfb_pad_draft_parts(snap)==()


def test_uncommitted_and_no_source_bay_may_not_fabricate_pad_entries():
    snap=_mixed()
    snap["nfb_config_submitted"]=False
    assert committed_nfb_pad_draft_parts(snap)==()
    snap["nfb_config_submitted"]=True
    snap["nfb_config"]["holes"][1]["model_filename"]="nfbv5:士林:UNKNOWN"
    snap["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"]=deepcopy(snap["nfb_config"])
    with pytest.raises(ValueError):
        committed_nfb_pad_draft_parts(snap)
