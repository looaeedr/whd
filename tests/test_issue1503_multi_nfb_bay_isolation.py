# -*- coding: utf-8 -*-
"""#1503: a CSV candidate is inert until each connected Bay explicitly applies it."""
import pytest

from ae_engine.receiving_inner_door_candidates import create_inner_candidate, inner_config
from ae_engine.receiving_layout import new_receiving_layout
from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
from tests.test_issue1503_csv_committed_config import _feature, PART


def test_multi_candidate_applies_source_owned_two_tier_nfb_to_only_selected_bays():
    adapter = ReceivingSetBayAdapter(
        new_receiving_layout(width=800, height=1600, depth=350)
    )
    adapter.set_bay_count(2)
    ref = numeric_model_ref("士林", "2P400")
    saved, version_id = create_inner_candidate(
        None, {"layers": 2, "models": [ref, ref],
               "layer_heights_mm": [300, 800],
               "features": {PART: [_feature(0), _feature(1)]}},
    )
    original = adapter.layout
    assert all(b.get("nfb_config_submitted") is not True
               for b in original["sets"][0]["bays"])
    config = inner_config(saved, version_id)
    assert adapter.apply_inner_door_candidate_to_bays(
        config, 0, (0,), version_id=version_id
    ) == (0,)
    bays = adapter.layout["sets"][0]["bays"]
    assert bays[0]["nfb_config_submitted"] is True
    assert bays[1].get("nfb_config_submitted") is not True
    assert [h["layer_index"] for h in bays[0]["nfb_config"]["holes"]] == [0, 1]
    first_holes = {
        h["physical_hole_id"] for h in bays[0]["nfb_config"]["holes"]
    }
    assert all(h["manual_x_state"] == "UNVERIFIED_BASIS"
               for h in bays[0]["nfb_config"]["holes"])

    assert adapter.apply_inner_door_candidate_to_bays(
        config, 0, (1,), version_id=version_id
    ) == (1,)
    bays = adapter.layout["sets"][0]["bays"]
    second_holes = {
        h["physical_hole_id"] for h in bays[1]["nfb_config"]["holes"]
    }
    assert len(first_holes) == len(second_holes) == 2
    assert first_holes.isdisjoint(second_holes), (
        "Two physical Bays may share source candidate but not hole identity"
    )
    assert bays[0]["nfb_config"]["holes"][0]["physical_hole_id"] in first_holes
    # An EXPLICIT re-Apply is now a source-owned, atomic replacement. It
    # must be idempotent, not a second physical CUTTING owner; mixed/manual
    # double CUTTING is independently rejected by the replacement validator.
    original = adapter.layout
    assert adapter.apply_inner_door_candidate_to_bays(
        config, 0, (0,), version_id=version_id
    ) == (0,)
    assert adapter.layout == original
