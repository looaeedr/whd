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


def test_ac23_rotation_changes_invalidate_only_effectively_rotated_x_and_undo():
    """Quarter-turn changes require fresh X datum; unaffected owners survive."""
    from ae_engine.receiving_nfb_ui1a_edits import (
        NfbUi1aEditSession, RECONFIRM,
    )

    original = _draft()
    original = set_nfb_manual_x(original, 0, 0, 0,
                                datum={"width": 800, "rotation_deg": 0})
    original = set_nfb_manual_x(original, 0, 1, 17.5,
                                datum={"width": 800, "rotation_deg": 0})
    original = set_nfb_manual_x(original, 1, 0, -8.25,
                                datum={"width": 800, "rotation_deg": 0})
    # Explicit override whose actual angle will NOT change with the tier.
    original = set_nfb_slot_rotation(original, 0, 1, mode=OVERRIDE, value=90)
    for layer in original["layers"]:
        for slot in layer["slots"]:
            slot["manual_x_state"] = "CONFIRMED"
            slot["datum_revision"] = "prior-authorized-source"
    untouched = deepcopy(original)
    session = NfbUi1aEditSession(original)
    assert session.apply("ROTATE_TIER", set_nfb_layer_rotation, 0, 180)
    first, second = session.current["layers"][0]["slots"]
    assert first["manual_x_mm"] == 0
    assert first["manual_x_state"] == RECONFIRM
    assert first["datum_snapshot"] is None
    assert "datum_revision" not in first
    assert second == untouched["layers"][0]["slots"][1]
    assert session.current["layers"][1] == untouched["layers"][1]
    assert not nfb_ui1a_preview(
        session.current, bay_width_mm=800, upper_cell_height_mm=1100,
    )["can_manufacture"]
    assert session.undo().action == "ROTATE_TIER"
    assert session.current == untouched and not session.dirty
    assert original == untouched


def test_ac23_effective_rotation_noop_keeps_basis_changed_slot_invalidates():
    from ae_engine.receiving_nfb_ui1a_edits import RECONFIRM

    original = _draft()
    original = set_nfb_manual_x(original, 0, 0, 12.5,
                                datum={"width": 800, "rotation_deg": 0})
    original["layers"][0]["slots"][0]["manual_x_state"] = "CONFIRMED"
    original["layers"][0]["slots"][0]["datum_revision"] = "prior-revision"
    frozen = deepcopy(original)
    assert set_nfb_layer_rotation(original, 0, 0) == original
    assert set_nfb_slot_rotation(
        original, 0, 0, mode=OVERRIDE, value=0,
    )["layers"][0]["slots"][0]["datum_revision"] == "prior-revision"
    rotated = set_nfb_slot_rotation(original, 0, 0, mode=OVERRIDE, value=270)
    slot = rotated["layers"][0]["slots"][0]
    assert slot["manual_x_mm"] == 12.5
    assert slot["manual_x_state"] == RECONFIRM
    assert slot["datum_snapshot"] is None and "datum_revision" not in slot
    assert rotated["layers"][0]["slots"][1] == frozen["layers"][0]["slots"][1]
    same_effective = set_nfb_slot_rotation(rotated, 0, 0, mode=OVERRIDE, value=270)
    assert same_effective == rotated
    assert original == frozen


def test_ac23_rotation_drops_orphaned_revision_even_without_manual_x():
    original = _draft()
    slot = original["layers"][0]["slots"][0]
    assert slot["manual_x_mm"] is None
    slot["datum_revision"] = "obsolete-source"
    slot["datum_snapshot"] = {"width": 800}
    changed = set_nfb_slot_rotation(original, 0, 0, mode=OVERRIDE, value=90)
    current = changed["layers"][0]["slots"][0]
    assert current["manual_x_mm"] is None
    assert current["manual_x_state"] == NONE
    assert current["datum_snapshot"] is None
    assert "datum_revision" not in current
    assert original["layers"][0]["slots"][0]["datum_revision"] == "obsolete-source"


def test_ac23_second_effective_rotation_change_keeps_pending_reconfirmation():
    """Repeat datum changes must not demote RECONFIRM_REQUIRED to UNVERIFIED."""
    from ae_engine.receiving_nfb_ui1a_edits import RECONFIRM

    original = _draft()
    original = set_nfb_manual_x(original, 0, 0, 0)
    original["layers"][0]["slots"][0]["manual_x_state"] = RECONFIRM
    original["layers"][0]["slots"][0]["datum_revision"] = "stale-rev"
    unchanged = deepcopy(original)
    moved = set_nfb_slot_rotation(original, 0, 0, mode=OVERRIDE, value=90)
    first = moved["layers"][0]["slots"][0]
    assert first["manual_x_mm"] == 0
    assert first["manual_x_state"] == RECONFIRM
    assert first["datum_snapshot"] is None
    assert "datum_revision" not in first
    repeated = set_nfb_slot_rotation(moved, 0, 0, mode=OVERRIDE, value=180)
    assert repeated["layers"][0]["slots"][0]["manual_x_state"] == RECONFIRM
    assert original == unchanged
