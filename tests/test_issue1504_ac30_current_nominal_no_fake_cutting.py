# -*- coding: utf-8 -*-
"""#1504 NFB-AC-30: source-independent NOMINAL spacing must never create fake CUTTING.

The original v1.4 AC's nominal model rule remains valid in current CSV V5.
This is a deterministic automated AC, NOT a factory release for unverified NFB.
"""
from copy import deepcopy

import pytest

from ae_engine.receiving_nfb_ui1a import (
    PREVIEW_ONLY, add_nfb_draft_slot, new_nfb_ui1a_draft, nfb_ui1a_preview,
)
from ae_engine.receiving_nfb_x_projection import nominal_nfb_x_group
from ae_engine.receiving_nfb_csv_editor_features import editor_nfb_features_from_csv
from phase6_receiving_modes import fresh_receiving_mode


@pytest.mark.parametrize("width,quantity,pitch", [
    (600, 2, (180.0,)),
    (750, 2, (310.0,)),
    (800, 2, (360.0,)),
    (800, 3, (180.0, 180.0)),
])
def test_nfb_ac30_nominal_spacing_survives_missing_model_without_fake_cutting(
    width, quantity, pitch,
):
    """A physical slot is not a committed aperture or a fabricated WORLD-X."""
    base = new_nfb_ui1a_draft(set_brand="士林")
    for _ in range(quantity):
        base = add_nfb_draft_slot(base, 0)
    before = deepcopy(base)
    selected = new_nfb_ui1a_draft(set_brand="士林")
    for _ in range(quantity):
        selected = add_nfb_draft_slot(
            selected, 0, filename="400_140X257_107.dxf",
        )
    # Mix selected / unselected / stale-brand models with identical physical
    # slot count. Source validity must not make up the already-approved pitch.
    stale = deepcopy(selected)
    stale["layers"][0]["slots"][0]["source_brand"] = "東元"
    for row in (base, selected, stale):
        result = nfb_ui1a_preview(
            row, bay_width_mm=width, upper_cell_height_mm=1100,
        )
        current = result["layers"][0]
        assert current["adjacent_x_mm"] == pitch
        assert nominal_nfb_x_group(width, quantity).adjacent_distances_mm == pitch
        assert result["status"] == PREVIEW_ONLY
        assert result["can_manufacture"] is False
        assert result["has_absolute_x"] is False
        assert current["absolute_x_mm"] is None
        assert all(unit["absolute_x_mm"] is None for unit in current["slots"])
        assert "CUTTING" not in result
        if row is base:
            assert all(unit["status"] == "EMPTY" for unit in current["slots"])
        elif row is stale:
            assert current["slots"][0]["status"] == "NEEDS_RESELECTION"
    assert base == before


def test_nfb_ac30_missing_numeric_csv_model_produces_no_physical_cutting():
    """The current original Hole Editor CSV source must not fabricate a hole."""
    physical = fresh_receiving_mode("quantity", {
        "w": 800, "h": 1600, "d": 350, "t": 2,
    })
    before = deepcopy(physical)
    absent = {
        "layers": 1,
        "layer_heights_mm": [550, 800],
        "models": ["", ""],
    }
    assert editor_nfb_features_from_csv(physical, absent) == ()
    assert physical == before

    # A structurally valid V5 identity absent from the current numeric CSV
    # is the relevant failure (not a malformed legacy DXF basename).
    invalid = dict(absent, models=["nfbv5:士林:不存在型號", ""])
    with pytest.raises(ValueError, match="NFB CSV 缺少主孔尺寸"):
        editor_nfb_features_from_csv(physical, invalid)
    assert physical == before


@pytest.mark.parametrize("width,quantity", (
    (600., 2), (750., 2), (800., 2), (800., 3),
))
def test_swt30_current_numeric_v5_four_nominal_groups_stay_preview_until_committed(
    width, quantity,
):
    """A current complete numeric source does not approve nominal X or CUTTING."""
    from ae_engine.receiving_nfb_model_identity import selected_numeric_spec
    assert selected_numeric_spec(
        "士林", "nfbv5:士林:2P400"
    ).dimensionally_complete
    draft = new_nfb_ui1a_draft(set_brand="士林")
    for _ in range(quantity):
        draft = add_nfb_draft_slot(
            draft, 0, filename="nfbv5:士林:2P400",
            source_brand="士林",
        )
    saved_before = deepcopy(draft)
    result = nfb_ui1a_preview(
        draft, bay_width_mm=width, upper_cell_height_mm=1100,
    )
    group = nominal_nfb_x_group(width, quantity)
    assert result["status"] == PREVIEW_ONLY
    assert result["can_manufacture"] is False
    assert result["has_absolute_x"] is False
    assert result["layers"][0]["absolute_x_mm"] is None
    assert result["layers"][0]["adjacent_x_mm"] == group.adjacent_distances_mm
    assert all(unit["absolute_x_mm"] is None
               for unit in result["layers"][0]["slots"])
    assert "CUTTING" not in result
    assert draft == saved_before
