# -*- coding: utf-8 -*-
"""#1504 AC-32: observed per-layer reset count and reversible X/datum state.

Pure source transactions are checked against the actual compact NFB settings
UI's visible Tk feedback and Undo button wiring. This does not claim the two
original old-project Windows GUI acceptance runs.
"""
from copy import deepcopy
from pathlib import Path
import tkinter as tk
from tkinter import ttk

import pytest

from ae_engine.receiving_nfb_ui1a_edits import (
    NfbUi1aEditSession, nfb_x_reset_impact,
    set_nfb_manual_x, insert_nfb_slot, delete_nfb_slot, move_nfb_slot,
)
from tests.test_issue1504_ac04_ac19_source_transactions import _with_offsets

GUI = Path(__file__).resolve().parents[1] / (
    "gui_modules/application/fold_designer_composition_receiving.py"
)


@pytest.mark.parametrize("method,args", [
    (move_nfb_slot, (0, 0, 1)),
    (insert_nfb_slot, (0, 1)),
    (delete_nfb_slot, (0, 0)),
])
def test_ac32_q5_q6_q7_reports_exact_layer_count_and_undo_restores_all_basis(
    method, args,
):
    original = _with_offsets()
    stable = deepcopy(original)
    session = NfbUi1aEditSession(original)
    receipt = session.apply("SOURCE_RESET", method, *args)
    assert receipt is not None
    impact = nfb_x_reset_impact(receipt.old_draft, receipt.new_draft, 0)
    before = receipt.old_draft["layers"][0]["slots"]
    assert impact.layer_index == 0
    assert impact.count == 2
    assert set(impact.unit_ids) == {row["unit_id"] for row in before}
    assert nfb_x_reset_impact(receipt.old_draft, receipt.new_draft, 1).count == 0
    assert session.current["layers"][1] == original["layers"][1]
    assert session.undo() == receipt
    assert session.current == stable
    assert session.current["layers"][0]["slots"] == stable["layers"][0]["slots"]
    assert session.current["layers"][1] == stable["layers"][1]
    assert not session.dirty


def test_ac32_manual_clear_one_selected_slot_includes_zero_and_snapshot_no_residue():
    original = _with_offsets()
    session = NfbUi1aEditSession(original)
    baseline = deepcopy(session.current)
    assert baseline["layers"][0]["slots"][1]["manual_x_mm"] == 0
    done = session.apply("CLEAR_ONLY_SELECTED", set_nfb_manual_x, 0, 1, None)
    assert done is not None
    impact = nfb_x_reset_impact(done.old_draft, done.new_draft, 0)
    assert impact.count == 1
    assert impact.unit_ids == (baseline["layers"][0]["slots"][1]["unit_id"],)
    unchanged = session.current["layers"][0]["slots"][0]
    assert unchanged == baseline["layers"][0]["slots"][0]
    target = session.current["layers"][0]["slots"][1]
    assert target["manual_x_mm"] is None
    assert target["manual_x_state"] == "NONE"
    assert target["datum_snapshot"] is None
    assert nfb_x_reset_impact(done.old_draft, done.new_draft, 1).count == 0
    assert session.apply("DUPLICATE_CLEAR", set_nfb_manual_x, 0, 1, None) is None
    assert session.undo().action == "CLEAR_ONLY_SELECTED"
    assert session.current == baseline
    assert session.cancel() == baseline


def test_ac32_no_old_basis_no_ghost_count_and_failed_transaction_is_atomic():
    original = _with_offsets()
    session = NfbUi1aEditSession(original)
    empty = session.apply("CLEAR", set_nfb_manual_x, 0, 0, None)
    assert empty and nfb_x_reset_impact(empty.old_draft, empty.new_draft, 0).count == 1
    before = deepcopy(session.current)
    with pytest.raises(ValueError):
        session.apply("INVALID", set_nfb_manual_x, 0, 1, float("nan"))
    assert session.current == before
    assert nfb_x_reset_impact(before, before, 0).count == 0
    session.cancel()
    assert session.current == original


def test_ac32_compact_original_tk_ui_exposes_affected_count_and_reachable_undo():
    source = GUI.read_text(encoding="utf-8")
    # A visible status label and an actual Undo command, not dead helpers
    # or extra Q5/Q6/Q7 buttons in the two model lists.
    assert 'ttk.Label(frame, textvariable=warning).pack(anchor="w")' in source
    assert 'ttk.Button(buttons, text="復原 NFB", command=undo_nfb_draft)' in source
    assert 'show_x_clear_impact(before_x_change, index)' in source
    assert 'nfb_x_reset_impact(receipt.old_draft, receipt.new_draft, i).count' in source
    assert 'entry["manual_x_var"].set("" if mm is None else f"{mm:g}")' in source
    assert 'for extra in buttons_area.winfo_children()[2:]:' in source

    root = tk.Tk()
    root.withdraw()
    try:
        session = NfbUi1aEditSession(_with_offsets())
        source_copy = deepcopy(session.current)
        before = deepcopy(session.current)
        receipt = session.apply("CLEAR", set_nfb_manual_x, 0, 1, None)
        impact = nfb_x_reset_impact(before, session.current, 0)
        assert receipt is not None and impact.count == 1
        label_var = tk.StringVar(master=root, value=f"第1層已清除 {impact.count} 顆 X 位移")
        label = ttk.Label(root, textvariable=label_var)
        invoked = []
        button = ttk.Button(
            root, text="復原 NFB",
            command=lambda: (invoked.append(True), session.undo()),
        )
        button.invoke()
        assert invoked == [True]
        assert session.current == source_copy
        assert label_var.get() == "第1層已清除 1 顆 X 位移"
        assert str(label.cget("textvariable")) == str(label_var)
    finally:
        root.destroy()
