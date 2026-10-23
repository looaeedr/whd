# -*- coding: utf-8 -*-
"""#1504 NFB-AC-25: a stale model never becomes an approved X/collision/bounds.

Approved nominal *relative* pitch is independent of selection state.  Draft
manual X (including explicit zero) is never a WORLD-X or manufacturing grant.
"""
from copy import deepcopy

import pytest

from ae_engine.receiving_nfb_model_identity import numeric_model_refs
from ae_engine.receiving_nfb_ui1a import (
    NEEDS_RESELECTION, PREVIEW_ONLY, new_nfb_ui1a_draft,
    reconcile_set_brand, nfb_ui1a_preview,
)
from ae_engine.receiving_nfb_ui1a_edits import (
    UNVERIFIED, editable_nfb_draft, set_nfb_manual_x,
    replace_nfb_slot_model,
)
from ae_engine.receiving_nfb_x_projection import nominal_nfb_x_group

NOT_VERIFIED = {
    "absolute_x": "UNVERIFIED",
    "collision": "UNVERIFIED",
    "bounds": "UNVERIFIED",
}


def _two_or_three(count):
    model = numeric_model_refs("士林")[0]
    alternative = numeric_model_refs("東元")[0]
    assert model != alternative
    return (new_nfb_ui1a_draft(
        set_brand="士林", model_layers=([model] * count, ""),
    ), model, alternative)


@pytest.mark.parametrize("width,count,pitch", [
    (600, 2, (180.0,)),
    (750, 2, (310.0,)),
    (800, 2, (360.0,)),
    (800, 3, (180.0, 180.0)),
])
def test_nfb_ac25_reselection_preserves_approved_relative_pitch_no_fake_x_checks(
    width, count, pitch,
):
    draft, original, alternate = _two_or_three(count)
    before = deepcopy(draft)
    stale = reconcile_set_brand(draft, "東元")
    snapshot = deepcopy(stale)
    preview = nfb_ui1a_preview(
        stale, bay_width_mm=width, upper_cell_height_mm=1100,
        catalog={"東元": (alternate, original)},
    )
    assert draft == before and stale == snapshot
    assert preview["status"] == PREVIEW_ONLY
    assert preview["has_absolute_x"] is False
    assert preview["can_manufacture"] is False
    layer = preview["layers"][0]
    assert layer["adjacent_x_mm"] == pitch
    assert nominal_nfb_x_group(width, count).adjacent_distances_mm == pitch
    assert layer["absolute_x_mm"] is None
    assert [u["status"] for u in layer["slots"]] == (
        [NEEDS_RESELECTION] * count
    )
    assert [u["filename"] for u in layer["slots"]] == [original] * count
    assert all(u["absolute_x_mm"] is None for u in layer["slots"])
    assert all(u["verification"] == NOT_VERIFIED for u in layer["slots"])
    assert "CUTTING" not in preview
    assert not any("manufacturing_ready" in unit for unit in layer["slots"])


def test_nfb_ac25_q16_explicit_zero_does_not_turn_old_x_datum_into_approval():
    draft, original, alternate = _two_or_three(2)
    state = editable_nfb_draft(draft)
    state = set_nfb_manual_x(state, 0, 0, 0, datum={"basis": "obsolete"})
    before = deepcopy(state)
    changed = reconcile_set_brand(state, "東元")
    # Reselection to valid current CSV model must preserve input identity and
    # manual zero, while discarding obsolete basis and confidence.
    changed = replace_nfb_slot_model(
        changed, 0, 0, alternate,
        catalog={"東元": (alternate,)},
    )
    assert state == before
    unit = changed["layers"][0]["slots"][0]
    assert unit["manual_x_mm"] == 0
    assert unit["manual_x_state"] == UNVERIFIED
    assert unit["datum_snapshot"] is None
    preview = nfb_ui1a_preview(changed, bay_width_mm=800,
                               upper_cell_height_mm=1100)
    assert preview["layers"][0]["adjacent_x_mm"] == (360.0,)
    assert [s["status"] for s in preview["layers"][0]["slots"]] == [
        "MODEL_SELECTED", NEEDS_RESELECTION,
    ]
    assert all(s["verification"] == NOT_VERIFIED
               and s["absolute_x_mm"] is None
               for s in preview["layers"][0]["slots"])
    assert preview["can_manufacture"] is False


@pytest.mark.parametrize("width,count", [(825, 2), (800, 4), (750, 3)])
def test_nfb_ac25_unknown_pitch_cannot_become_centered_or_verified(width, count):
    draft, _, _ = _two_or_three(count)
    stale = reconcile_set_brand(draft, "東元")
    preview = nfb_ui1a_preview(stale, bay_width_mm=width,
                               upper_cell_height_mm=1100)
    current = preview["layers"][0]
    assert current["adjacent_x_mm"] is None
    assert current["absolute_x_mm"] is None
    assert preview["can_manufacture"] is False
    assert all(s["status"] == NEEDS_RESELECTION and
               s["verification"] == NOT_VERIFIED and
               s["absolute_x_mm"] is None for s in current["slots"])
