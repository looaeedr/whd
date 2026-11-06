# -*- coding: utf-8 -*-
"""#2517: a committed V5 two-tier NFB cannot disappear when one tier is missing.

Uses the existing real Receiving upper-door/Set-Bay/two-plate geometry fixture,
not a mocked physical tier solver. Drafts and historical DXF sources retain
their established non-CSV routes; no manufacturing approval is inferred.
"""
from copy import deepcopy

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_nfb_committed_final_scene import _submitted_csv_holes
from tests.test_receiving_two_tier_physical_base_parts import _two_tier


MODEL = "nfbv5:士林:3P125SN"


def _committed_csv_two_tier(*, confirmed=False):
    snapshot = _two_tier()
    for index, row in enumerate(snapshot["nfb_config"]["holes"]):
        row.update(
            model_filename=MODEL,
            source_brand="士林",
            manual_x_state=("CONFIRMED" if confirmed else "UNVERIFIED_BASIS"),
            manual_x_mm=((-100.0, 100.0)[index] if confirmed else None),
            rotation_deg=0,
        )
        if confirmed:
            row.update(
                datum_revision="PHYSICAL-TWO-TIER-CURRENT",
                datum_snapshot={
                    "width": 800, "model_filename": MODEL, "rotation_deg": 0,
                },
            )
    snapshot["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snapshot["nfb_config"]
    )
    return snapshot


@pytest.mark.parametrize("missing_tier", (0, 1))
@pytest.mark.parametrize("confirmed", (False, True))
def test_submitted_v5_two_tier_missing_physical_owner_is_not_blank_cutting(
    missing_tier, confirmed,
):
    snapshot = _committed_csv_two_tier(confirmed=confirmed)
    snapshot["nfb_config"]["holes"] = [
        row for row in snapshot["nfb_config"]["holes"]
        if row["layer_index"] != missing_tier
    ]
    snapshot["receiving_layout"]["sets"][0]["bays"][0]["nfb_config"] = deepcopy(
        snapshot["nfb_config"]
    )
    original = deepcopy(snapshot)
    # Old code quietly returned None, dropping the remaining V5 tier;
    # even CONFIRMED X could disappear from canonical FinalScene selection.
    with pytest.raises(
        ValueError, match="NFB_COMMITTED_CSV_TWO_TIER_OWNER_INCOMPLETE",
    ):
        manufacturing_api.project_receiving_committed_csv_nfb_pair_layer_count(
            snapshot,
        )
    assert snapshot == original


def test_full_confirmed_two_tier_real_physical_source_still_resolves():
    snapshot = _committed_csv_two_tier(confirmed=True)
    original = deepcopy(snapshot)
    sourced = _submitted_csv_holes(snapshot)
    assert sourced
    door_id, holes = sourced
    assert door_id == "upper"
    assert {hole.slot_index for hole in holes} == {0, 1}
    assert {hole.physical_hole_id for hole in holes} == {
        "tier:0:switch", "tier:1:switch",
    }
    assert snapshot == original


def test_complete_unconfirmed_v5_two_tier_keeps_editable_blank():
    snapshot = _committed_csv_two_tier()
    assert _submitted_csv_holes(snapshot) == ()


def test_historical_two_tier_dxf_still_follows_legacy_route():
    snapshot = _two_tier()
    assert _submitted_csv_holes(snapshot) == ()


def test_unsubmitted_two_tier_draft_is_not_treated_as_manufacturing():
    snapshot = _committed_csv_two_tier()
    snapshot["nfb_config_submitted"] = False
    bay = snapshot["receiving_layout"]["sets"][0]["bays"][0]
    bay["nfb_config_submitted"] = False
    bay.pop("nfb_config", None)
    assert _submitted_csv_holes(snapshot) == ()
