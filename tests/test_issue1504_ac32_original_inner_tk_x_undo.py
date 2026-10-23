# -*- coding: utf-8 -*-
"""#1504 NFB-AC-32: actual WHD inner-editor X reset and Undo operator cycle.

The original Tk editor's real +/- UI (not a test-only Undo button) must
report affected identities, including zero offsets and datum snapshots.
No absolute X or manufacturing capability is inferred from this draft.
"""
from copy import deepcopy
import tkinter as tk
from tkinter import messagebox

from ae_engine.receiving_inner_door_candidates import KEY
from ae_engine.receiving_nfb_ui1a_edits import set_nfb_manual_x
from tests.test_issue1504_ac20_swt13_native_inner_brand_gui import (
    _open_original_editor, _button,
)


def test_ac32_original_inner_tk_remove_reports_two_real_x_resets_and_undo_restores(monkeypatch):
    root, app, modal = _open_original_editor(monkeypatch)
    try:
        state = modal._receiving_inner_switch_state
        row = state["rows"][0]
        available, assigned = row["available"], row["assigned"]
        available.selection_set(0)
        add = _button(row["section"], "＋加入")
        add.invoke()
        add.invoke()
        root.update()
        assert assigned.size() == 2

        # Seed an existing draft's two physical datum conditions, including
        # a valid X=0. The actual removal and reversal MUST use WHD Tk.
        draft = state["nfb_draft"]
        for slot, mm in enumerate((12.5, 0.0)):
            draft["draft"] = set_nfb_manual_x(
                draft["draft"], 0, slot, mm,
                datum={"width": 800, "source": f"unit-{slot}"},
            )
        baseline = deepcopy(draft["draft"])
        ids = [slot["unit_id"] for slot in baseline["layers"][0]["slots"]]
        assert len(ids) == len(set(ids)) == 2
        assert [slot["manual_x_mm"] for slot in baseline["layers"][0]["slots"]] == [
            12.5, 0.0,
        ]

        assigned.selection_set(0)
        _button(row["section"], "－移除").invoke()
        root.update()
        changed = draft["draft"]
        assert len(changed["layers"][0]["slots"]) == 1
        assert changed["layers"][0]["slots"][0]["unit_id"] == ids[1]
        assert changed["layers"][0]["slots"][0]["manual_x_mm"] is None
        assert changed["layers"][0]["slots"][0]["manual_x_state"] == "NONE"
        assert changed["layers"][0]["slots"][0]["datum_snapshot"] is None
        assert "第1層已清除 2 顆 X 位移" in state["warning"].get()
        assert KEY not in app._phase6_input_snapshot

        _button(modal, "復原 NFB").invoke()
        root.update()
        assert draft["draft"] == baseline
        assert state["edit_session"].current == baseline
        assert [slot["unit_id"] for slot in draft["draft"]["layers"][0]["slots"]] == ids
        assert [slot["manual_x_mm"] for slot in draft["draft"]["layers"][0]["slots"]] == [
            12.5, 0.0,
        ]
        assert draft["draft"]["layers"][0]["slots"][0]["datum_snapshot"] == {
            "width": 800, "source": "unit-0",
        }
        assert draft["draft"]["layers"][0]["slots"][1]["datum_snapshot"] == {
            "width": 800, "source": "unit-1",
        }
        assert "已復原 第1層 2 顆的 X 位移與基準快照" in state["warning"].get()
        assert KEY not in app._phase6_input_snapshot
    finally:
        if modal.winfo_exists():
            modal.destroy()
        root.destroy()


def test_ac32_original_inner_cancel_after_pending_x_change_never_writes_candidate(monkeypatch):
    monkeypatch.setattr(messagebox, "askyesno", lambda *_args, **_kw: True)
    root, app, modal = _open_original_editor(monkeypatch)
    try:
        state = modal._receiving_inner_switch_state
        row = state["rows"][0]
        row["available"].selection_set(0)
        _button(row["section"], "＋加入").invoke()
        root.update()
        before = deepcopy(app._phase6_input_snapshot)
        draft = state["nfb_draft"]
        draft["draft"] = set_nfb_manual_x(
            draft["draft"], 0, 0, 0,
            datum={"width": 800, "current": False},
        )
        assert draft["draft"]["layers"][0]["slots"][0]["manual_x_mm"] == 0.0
        assert draft["draft"]["layers"][0]["slots"][0]["manual_x_state"] != "NONE"
        _button(modal, "取消").invoke()
        root.update()
        assert app._phase6_input_snapshot == before
        assert KEY not in app._phase6_input_snapshot
        assert not modal.winfo_exists()
    finally:
        if modal.winfo_exists():
            modal.destroy()
        root.destroy()
