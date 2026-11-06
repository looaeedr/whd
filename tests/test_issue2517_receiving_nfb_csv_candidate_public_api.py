# -*- coding: utf-8 -*-
"""#2517: public WHD NFB CSV Apply owns the complete source/Bay transaction.

The CADSplit source bridge must not implement its own Bay commit loop.  This
tests the shared Engine contract without making CSV candidate source a
certified CUTTING / world-X manufacturing result.
"""
from copy import deepcopy
from dataclasses import replace

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_layout import new_receiving_layout
from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from tests.test_issue1503_csv_committed_config import PART, _feature


def _layout():
    return manufacturing_api.resize_receiving_bays_with_family_defaults(
        new_receiving_layout(width=800, height=1600, depth=350),
        set_index=0, bay_count=2,
    )


def _source():
    ref = numeric_model_ref("士林", "2P400")
    return {
        "layers": 2,
        "models": [ref, ref],
        "layer_heights_mm": [300., 800.],
        "features": {PART: [_feature(0), _feature(1)]},
    }


def test_public_csv_apply_matches_existing_engine_ports_and_keeps_bays_distinct():
    original = _layout()
    untouched = deepcopy(original)
    source = _source()

    applied = manufacturing_api.apply_receiving_nfb_csv_candidate(
        original, set_index=0, bay_indices=(1, 0), source=source,
    )
    assert original == untouched
    assert applied is not original

    csv = manufacturing_api.candidate_committed_csv_nfb_config(source)
    manufacturing_api.validate_candidate_nfb_replacement(
        original, ((0, 1), (0, 0)), source, csv,
    )
    expected = manufacturing_api.replace_candidate_bay_nfb(
        original, 0, 1, csv,
    )
    expected = manufacturing_api.replace_candidate_bay_nfb(
        expected, 0, 0, csv,
    )
    assert applied == expected

    bays = applied["sets"][0]["bays"]
    ids = [
        {hole["physical_hole_id"] for hole in bay["nfb_config"]["holes"]}
        for bay in bays
    ]
    assert len(ids[0]) == len(ids[1]) == 2
    assert ids[0].isdisjoint(ids[1])
    assert all(bay["nfb_config_submitted"] is True for bay in bays)
    assert all(
        hole["manual_x_state"] == "UNVERIFIED_BASIS"
        and hole["manual_x_mm"] is None
        for bay in bays for hole in bay["nfb_config"]["holes"]
    )
    assert manufacturing_api.apply_receiving_nfb_csv_candidate(
        applied, set_index=0, bay_indices=(1, 0), source=source,
    ) == applied


@pytest.mark.parametrize("set_index,bays,reason", (
    (True, (0,), "RECEIVING_SET_SELECTION_INVALID"),
    (2, (0,), "RECEIVING_SET_SELECTION_INVALID"),
    (0, (), "RECEIVING_BAY_SELECTION_INVALID"),
    (0, (True,), "RECEIVING_BAY_SELECTION_INVALID"),
    (0, (0, 2), "RECEIVING_BAY_SELECTION_INVALID"),
    (0, (0, 0), "RECEIVING_BAY_SELECTION_DUPLICATE"),
    (0, None, "RECEIVING_BAY_SELECTION_INVALID"),
))
def test_public_csv_apply_rejects_invalid_bay_selection_without_partial_commit(
    set_index, bays, reason,
):
    original = _layout()
    before = deepcopy(original)
    with pytest.raises(ValueError, match=reason):
        manufacturing_api.apply_receiving_nfb_csv_candidate(
            original, set_index=set_index, bay_indices=bays,
            source=_source(),
        )
    assert original == before


def test_public_csv_apply_requires_real_csv_candidate_not_just_a_nfb_model():
    original = _layout()
    before = deepcopy(original)
    source = _source()
    source["features"] = {}
    with pytest.raises(ValueError, match="RECEIVING_NFB_CSV_SOURCE_REQUIRED"):
        manufacturing_api.apply_receiving_nfb_csv_candidate(
            original, set_index=0, bay_indices=(0,), source=source,
        )
    assert original == before


def test_public_csv_apply_rejects_incomplete_or_mixed_cutting_without_partial_commit():
    original = _layout()
    before = deepcopy(original)

    incomplete = _source()
    incomplete["features"] = {PART: [_feature(0)]}
    with pytest.raises(ValueError, match="NFB_CSV_COMMIT_MISSING_CONFIRMED_HOLE"):
        manufacturing_api.apply_receiving_nfb_csv_candidate(
            original, set_index=0, bay_indices=(0, 1), source=incomplete,
        )

    mixed = _source()
    mixed["features"] = {
        PART: [_feature(0), _feature(1), replace(_feature(0), source_type="MANUAL")],
    }
    with pytest.raises(ValueError, match="CUTTING"):
        manufacturing_api.apply_receiving_nfb_csv_candidate(
            original, set_index=0, bay_indices=(0, 1), source=mixed,
        )
    assert original == before

def test_package_public_api_reexports_same_atomic_csv_apply():
    """Both supported import paths must expose one real Engine transaction."""
    import ae_engine

    assert "apply_receiving_nfb_csv_candidate" in ae_engine.__all__
    public_apply = ae_engine.apply_receiving_nfb_csv_candidate
    assert public_apply is manufacturing_api.apply_receiving_nfb_csv_candidate

    layout = _layout()
    source = _source()
    expected = manufacturing_api.apply_receiving_nfb_csv_candidate(
        layout, set_index=0, bay_indices=(0, 1), source=source,
    )
    actual = public_apply(
        layout, set_index=0, bay_indices=(0, 1), source=source,
    )
    assert actual == expected
