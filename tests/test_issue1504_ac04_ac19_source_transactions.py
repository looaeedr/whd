# -*- coding: utf-8 -*-
"""#1504 NFB-AC-04/19: current UI-1A slot transactions, Q5/6/7/16, no fake manufacture.

Both accepted automated source scopes require affected-layer X reset, untouched
other layer, stable unit identity, exact fractional mm/zero, failed edit atomicity,
Q16 preserve/revalidate, Undo and Cancel. Full real Windows GUI and MFG remain
independently gated by #1500 and #1504.
"""
from copy import deepcopy

import pytest

from ae_engine.receiving_nfb_model_identity import numeric_model_ref
from ae_engine.receiving_nfb_ui1a import new_nfb_ui1a_draft, nfb_ui1a_preview
from ae_engine.receiving_nfb_ui1a_edits import (
    NONE, UNVERIFIED, NfbUi1aEditSession, editable_nfb_draft,
    insert_nfb_slot, delete_nfb_slot, move_nfb_slot, replace_nfb_slot_model,
    set_nfb_manual_x,
)

A = numeric_model_ref("士林", "2P400")
B = numeric_model_ref("士林", "3P125SN")


def _source():
    return editable_nfb_draft(new_nfb_ui1a_draft(
        set_brand="士林", layer_count=2, model_layers=([A, B], [A]),
    ))


def _with_offsets():
    d = _source()
    d = set_nfb_manual_x(d, 0, 0, 12.5, datum={"width": 800})
    d = set_nfb_manual_x(d, 0, 1, 0, datum={"width": 800})
    return set_nfb_manual_x(d, 1, 0, -99.25, datum={"width": 800})


@pytest.mark.parametrize("operation,args", [
    (move_nfb_slot, (0, 0, 1)),
    (insert_nfb_slot, (0, 1)),
    (delete_nfb_slot, (0, 0)),
])
def test_ac04_q5_q6_q7_reset_only_changed_layer_and_preserve_other_layer(operation, args):
    original = _with_offsets()
    frozen = deepcopy(original)
    other_layer = deepcopy(original["layers"][1])
    before_ids = [s["unit_id"] for s in original["layers"][0]["slots"]]
    session = NfbUi1aEditSession(original)
    receipt = session.apply("Q5_Q6_Q7", operation, *args)
    assert receipt is not None
    after = session.current
    assert after["layers"][1] == other_layer
    assert all(s["manual_x_state"] == NONE and s["manual_x_mm"] is None
               and s["datum_snapshot"] is None for s in after["layers"][0]["slots"])
    ids = [s["unit_id"] for s in after["layers"][0]["slots"]]
    assert len(ids) == len(set(ids))
    if operation is move_nfb_slot:
        assert ids == before_ids[::-1]
    elif operation is insert_nfb_slot:
        assert set(before_ids).issubset(ids) and len(ids) == 3
    else:
        assert ids == before_ids[1:]
    assert frozen == original
    assert session.undo().action == "Q5_Q6_Q7"
    assert session.current == frozen and not session.dirty


def test_ac19_q16_preserves_exact_offset_identity_nominal_pitch_and_rejects_bad_model():
    source = _with_offsets()
    session = NfbUi1aEditSession(source)
    before = deepcopy(session.current)
    preview = nfb_ui1a_preview(session.current, bay_width_mm=800, upper_cell_height_mm=1100)
    assert preview["layers"][0]["adjacent_x_mm"] == (360.0,)
    assert not preview["can_manufacture"] and not preview["has_absolute_x"]
    receipt = session.apply("Q16", replace_nfb_slot_model, 0, 0, B,
                            catalog={"士林": (A, B)})
    assert receipt is not None
    slot = session.current["layers"][0]["slots"][0]
    assert slot["unit_id"] == before["layers"][0]["slots"][0]["unit_id"]
    assert slot["manual_x_mm"] == 12.5
    assert slot["manual_x_state"] == UNVERIFIED
    assert slot["datum_snapshot"] is None
    assert session.current["layers"][0]["slots"][1] == before["layers"][0]["slots"][1]
    assert session.current["layers"][1] == before["layers"][1]
    after = nfb_ui1a_preview(session.current, bay_width_mm=800, upper_cell_height_mm=1100)
    assert after["layers"][0]["adjacent_x_mm"] == (360.0,)
    assert not after["can_manufacture"]
    snapshot = deepcopy(session.current)
    with pytest.raises(ValueError):
        session.apply("INVALID_Q16", replace_nfb_slot_model, 0, 0,
                      "UNLISTED.dxf", catalog={"士林": (A, B)})
    assert session.current == snapshot

    def collision(candidate):
        candidate["layers"][0]["slots"][0]["manual_x_mm"] = 999999
        raise ValueError("geometry collision")

    with pytest.raises(ValueError, match="geometry collision"):
        session.apply("REJECT_GEOMETRY", collision)
    assert session.current == snapshot
    assert session.undo().action == "Q16"
    assert session.current == before and not session.dirty
    assert session.cancel() == before
    assert source == before


def test_ac04_ac19_fractional_mm_bad_input_cancel_and_undo_have_no_partial_mutation():
    session = NfbUi1aEditSession(_with_offsets())
    baseline = deepcopy(session.current)
    for invalid in (float("nan"), float("inf"), True, "12.5"):
        with pytest.raises(ValueError):
            session.apply("BAD_X", set_nfb_manual_x, 0, 0, invalid)
        assert session.current == baseline and not session.dirty
    session.apply("GOOD_X", set_nfb_manual_x, 0, 0, -0.125, datum={"width": 800})
    assert session.current["layers"][0]["slots"][0]["manual_x_mm"] == -0.125
    assert session.current["layers"][0]["slots"][1]["manual_x_mm"] == 0
    assert session.current["layers"][1] == baseline["layers"][1]
    assert session.escape() == baseline
    assert not session.dirty
    with pytest.raises(ValueError, match="no undo"):
        session.undo()


@pytest.mark.parametrize("operation,args", [
    (move_nfb_slot, (0, 0, 1)),
    (insert_nfb_slot, (0, 1)),
    (delete_nfb_slot, (0, 0)),
])
def test_ac28_q5_q6_q7_clears_obsolete_datum_revision_not_other_layer(operation, args):
    """Old world-X revision cannot remain after affected-tier X reset."""
    original = _with_offsets()
    for layer in original["layers"]:
        for slot in layer["slots"]:
            slot["datum_revision"] = "obsolete-world-x-rev"
    stable = deepcopy(original)
    session = NfbUi1aEditSession(original)
    session.apply("REBASE_TIER", operation, *args)
    assert all(
        "datum_revision" not in slot
        and slot["manual_x_state"] == NONE
        and slot["datum_snapshot"] is None
        for slot in session.current["layers"][0]["slots"]
    )
    assert session.current["layers"][1] == stable["layers"][1]
    assert session.undo().action == "REBASE_TIER"
    assert session.current == stable and original == stable


def test_ac28_clear_one_x_also_clears_old_revision_and_undo_restores():
    original = _with_offsets()
    original["layers"][0]["slots"][0]["datum_revision"] = "obsolete-world-x-rev"
    before = deepcopy(original)
    session = NfbUi1aEditSession(original)
    session.apply("CLEAR_X", set_nfb_manual_x, 0, 0, None)
    target = session.current["layers"][0]["slots"][0]
    assert target["manual_x_mm"] is None and target["manual_x_state"] == NONE
    assert target["datum_snapshot"] is None and "datum_revision" not in target
    assert session.current["layers"][0]["slots"][1] == before["layers"][0]["slots"][1]
    session.undo()
    assert session.current == before


def test_ac28_model_reselection_and_new_x_invalidate_old_revision():
    original = _with_offsets()
    original["layers"][0]["slots"][0]["datum_revision"] = "obsolete-world-x-rev"
    baseline = deepcopy(original)
    changed_model = replace_nfb_slot_model(
        original, 0, 0, B, catalog={"士林": (A, B)},
    )
    selected = changed_model["layers"][0]["slots"][0]
    assert selected["manual_x_mm"] == 12.5
    assert selected["manual_x_state"] == UNVERIFIED
    assert selected["datum_snapshot"] is None
    assert "datum_revision" not in selected

    reentered = set_nfb_manual_x(
        original, 0, 0, 14.5, datum={"width": 800},
    )
    edited = reentered["layers"][0]["slots"][0]
    assert edited["manual_x_mm"] == 14.5 and edited["manual_x_state"] == UNVERIFIED
    assert edited["datum_snapshot"] == {"width": 800}
    assert "datum_revision" not in edited
    assert original == baseline
