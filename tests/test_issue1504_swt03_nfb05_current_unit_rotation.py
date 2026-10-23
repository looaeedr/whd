# -*- coding: utf-8 -*-
"""#1504 CURRENT SWT-AC-03 and NFB-AC-05 V5 NFB UI-1A edit acceptance.

Exercise the real immutable edit ports and source-owned nominal pitch. These
are editor/preview proofs, not physical NFB X positioning or factory release.
"""
from copy import deepcopy

import pytest

from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from ae_engine.receiving_nfb_ui1a import (
    INHERIT, OVERRIDE, new_nfb_ui1a_draft, nfb_ui1a_preview,
)
from ae_engine.receiving_nfb_ui1a_edits import (
    NONE, UNVERIFIED, editable_nfb_draft, insert_nfb_slot, delete_nfb_slot,
    move_nfb_slot, replace_nfb_slot_model, set_nfb_manual_x,
    set_nfb_layer_rotation, set_nfb_slot_rotation, effective_nfb_rotation,
)
from ae_engine.receiving_nfb_x_projection import (
    PREVIEW_ONLY as NOMINAL_PREVIEW_ONLY, nominal_nfb_x_group,
)


def _models():
    # Source-backed model refs; do not invent a DXF filename or NFB dimensions.
    return numeric_model_ref("士林", "2P400"), numeric_model_ref("士林", "3P125SN")


def _draft():
    first, second = _models()
    return editable_nfb_draft(new_nfb_ui1a_draft(
        set_brand="士林", layer_count=2,
        model_layers=([first, second], [first]),
    ))


def test_swt_ac03_current_csv_units_keep_independent_identity_model_x_and_rotation():
    start = _draft()
    original = deepcopy(start)
    ids = [slot["unit_id"] for tier in start["layers"]
           for slot in tier["slots"]]
    assert len(ids) == len(set(ids)) == 3
    assert start["layers"][0]["slots"][0]["filename"] != (
        start["layers"][0]["slots"][1]["filename"]
    )
    state = set_nfb_manual_x(start, 0, 0, 0, datum={"source": "OPEN-X"})
    state = set_nfb_manual_x(state, 0, 1, 12, datum={"source": "OPEN-X"})
    state = set_nfb_manual_x(state, 1, 0, -7, datum={"source": "OPEN-X"})
    state = set_nfb_slot_rotation(state, 0, 0, mode=OVERRIDE, value=90)
    state = set_nfb_slot_rotation(state, 0, 1, mode=OVERRIDE, value=180)
    state = set_nfb_slot_rotation(state, 1, 0, mode=OVERRIDE, value=270)
    assert start == original
    assert [r["unit_id"] for tier in state["layers"] for r in tier["slots"]] == ids
    assert [[r["manual_x_mm"] for r in tier["slots"]]
            for tier in state["layers"]] == [[0, 12], [-7]]
    assert all(row["manual_x_state"] == UNVERIFIED
               for tier in state["layers"] for row in tier["slots"])
    assert [effective_nfb_rotation(state,0,i) for i in (0,1)] == [90,180]
    assert effective_nfb_rotation(state,1,0) == 270
    nominal = nominal_nfb_x_group(800,2)
    assert nominal.adjacent_distances_mm == (360.,)
    assert nominal.absolute_centers_mm is None
    assert nominal.manufacturing_ready is False
    preview = nfb_ui1a_preview(
        state, bay_width_mm=800, upper_cell_height_mm=1100,
    )
    assert preview["can_manufacture"] is False
    assert preview["has_absolute_x"] is False
    assert all("manufacturing_ready" not in slot
               for tier in state["layers"] for slot in tier["slots"])


def test_swt_ac03_reorder_insert_delete_reset_only_touched_tier_and_keep_true_pitch():
    start = _draft()
    current = set_nfb_manual_x(start,0,0,0)
    current = set_nfb_manual_x(current,0,1,15)
    current = set_nfb_manual_x(current,1,0,-8)
    current = set_nfb_slot_rotation(current,0,0,mode=OVERRIDE,value=90)
    current = set_nfb_slot_rotation(current,0,1,mode=OVERRIDE,value=180)
    other_tier = deepcopy(current["layers"][1])
    source_ids = [s["unit_id"] for s in current["layers"][0]["slots"]]
    reordered = move_nfb_slot(current,0,0,1)
    assert [s["unit_id"] for s in reordered["layers"][0]["slots"]] == source_ids[::-1]
    assert [s["rotation"]["value"] for s in reordered["layers"][0]["slots"]] == [180,90]
    assert all(s["manual_x_mm"] is None and s["manual_x_state"] == NONE
               for s in reordered["layers"][0]["slots"])
    assert reordered["layers"][1] == other_tier
    extended = insert_nfb_slot(current,0,1,filename=_models()[0],brand="士林")
    assert len({s["unit_id"] for tier in extended["layers"]
                for s in tier["slots"]}) == 4
    assert len(extended["layers"][0]["slots"]) == 3
    assert extended["layers"][1] == other_tier
    assert all(s["manual_x_state"] == NONE for s in extended["layers"][0]["slots"])
    triple = nominal_nfb_x_group(800,3)
    assert triple.adjacent_distances_mm == (180.,180.)
    assert triple.absolute_centers_mm is None
    removed = delete_nfb_slot(current,0,0)
    assert [s["unit_id"] for s in removed["layers"][0]["slots"]] == source_ids[1:]
    assert removed["layers"][1] == other_tier
    assert all(s["manual_x_state"] == NONE for s in removed["layers"][0]["slots"])
    with pytest.raises(ValueError,match="unsupported combination"):
        nominal_nfb_x_group(750,3)
    assert nominal_nfb_x_group(800,1).status == NOMINAL_PREVIEW_ONLY
    assert current["layers"][0]["slots"][0]["manual_x_mm"] == 0
    assert current["layers"][0]["slots"][1]["manual_x_mm"] == 15


def test_nfb_ac05_layer_inheritance_override_model_reselection_and_all_quarter_turns():
    a,b = _models()
    state = _draft()
    original = deepcopy(state)
    for angle in (0,90,180,270):
        rotated = set_nfb_layer_rotation(state,0,angle)
        assert [effective_nfb_rotation(rotated,0,i) for i in (0,1)] == [angle,angle]
        assert effective_nfb_rotation(rotated,1,0) == 0
        assert rotated["layers"][0]["slots"][0]["filename"] == a
        assert rotated["layers"][0]["slots"][1]["filename"] == b
    state = set_nfb_layer_rotation(state,0,90)
    state = set_nfb_slot_rotation(state,0,0,mode=OVERRIDE,value=90)
    assert state["layers"][0]["slots"][0]["rotation"] == {"mode":OVERRIDE,"value":90}
    state = set_nfb_layer_rotation(state,0,180)
    assert effective_nfb_rotation(state,0,0) == 90  # even same-value explicit override persists
    assert effective_nfb_rotation(state,0,1) == 180
    x = set_nfb_manual_x(state,0,0,0)
    replaced = replace_nfb_slot_model(x,0,0,b,catalog={"士林":(a,b)})
    changed = replaced["layers"][0]["slots"][0]
    assert changed["unit_id"] == x["layers"][0]["slots"][0]["unit_id"]
    assert changed["filename"] == b
    assert changed["rotation"] == {"mode":OVERRIDE,"value":90}
    assert effective_nfb_rotation(replaced,0,0) == 90
    assert changed["manual_x_mm"] == 0 and changed["manual_x_state"] == UNVERIFIED
    assert changed["datum_snapshot"] is None
    inherited = set_nfb_slot_rotation(replaced,0,0,mode=INHERIT)
    assert effective_nfb_rotation(inherited,0,0) == 180
    assert state["layers"][0]["slots"][0]["filename"] == a
    assert _draft() == original


def test_nfb_ac05_mirror_non_quarter_angle_and_unindexed_source_all_rejected():
    start = _draft()
    before = deepcopy(start)
    for bad in (-90,45,360,True,90.0):
        with pytest.raises(ValueError):
            set_nfb_layer_rotation(start,0,bad)
        with pytest.raises(ValueError):
            set_nfb_slot_rotation(start,0,0,mode=OVERRIDE,value=bad)
    a,b = _models()
    with pytest.raises(ValueError,match="current brand CSV"):
        replace_nfb_slot_model(start,0,0,"nfbv5:東元:2P400",
                               catalog={"士林":(a,b)})
    assert start == before
    assert nfb_ui1a_preview(
        start,bay_width_mm=800,upper_cell_height_mm=1100,
    )["can_manufacture"] is False
