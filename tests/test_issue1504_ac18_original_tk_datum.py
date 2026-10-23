# -*- coding: utf-8 -*-
"""#1504 NFB-AC-18: native original WHD Tk one-tier owner and visible unknown datum.

Use the actual original candidate editor, its real 1/2 Radiobuttons and
the UI-1A preview. Never assert that nominal pitch/Y grants manufacturing.
"""
from copy import deepcopy
import tkinter as tk
from tkinter import ttk

from ae_engine.receiving_inner_door_candidates import KEY
from ae_engine.receiving_nfb_ui1a import nfb_ui1a_preview
from tests.test_issue1504_ac20_swt13_native_inner_brand_gui import (
    _open_original_editor, _walk, _button,
)


def _count_buttons(modal, layers):
    return [
        w for w in _walk(modal)
        if isinstance(w, ttk.Radiobutton)
        and w.cget("variable") == str(layers)
        and str(w.cget("value")) in ("1", "2")
    ]


def test_ac18_original_tk_single_layer_count_changes_only_real_draft_and_undo(monkeypatch):
    root, app, modal = _open_original_editor(monkeypatch)
    try:
        state = modal._receiving_inner_switch_state
        count = state["layers"]
        assert count is state["nfb_physical_layers"]
        buttons = _count_buttons(modal, count)
        assert len(buttons) == 2
        assert all(b.winfo_ismapped() for b in buttons)
        original = deepcopy(state["nfb_draft"]["draft"])
        assert original["layer_count"] == count.get() == 1
        two = next(b for b in buttons if str(b.cget("value")) == "2")
        two.invoke()
        root.update()
        assert count.get() == 2
        assert state["nfb_draft"]["draft"]["layer_count"] == 2
        assert state["edit_session"].current["layer_count"] == 2
        assert state["rows"][1]["section"].winfo_ismapped()
        assert KEY not in app._phase6_input_snapshot
        _button(modal, "復原 NFB").invoke()
        root.update()
        assert count.get() == 1
        assert state["nfb_draft"]["draft"] == original
        assert not state["rows"][1]["section"].winfo_ismapped()
        assert KEY not in app._phase6_input_snapshot
    finally:
        if modal.winfo_exists():
            modal.destroy()
        root.destroy()


def test_ac18_real_tk_nominal_pitch_not_world_x_and_non1100_y_shows_unknown(monkeypatch):
    root, app, modal = _open_original_editor(monkeypatch)
    try:
        state = modal._receiving_inner_switch_state
        # Valid work-height for a box without door-layout columns. This must
        # not create a second editable tier count or approved Y baseline.
        app._phase6_input_snapshot["h"] = 1600
        first = state["rows"][0]
        first["available"].selection_set(0)
        add = _button(first["section"], "＋加入")
        add.invoke()
        add.invoke()
        root.update()
        assert first["assigned"].size() == 2
        buttons = _count_buttons(modal, state["layers"])
        one = next(b for b in buttons if str(b.cget("value")) == "1")
        one.invoke()
        root.update()
        summary = state["nfb_draft_status"]
        label = [
            w for w in _walk(modal)
            if isinstance(w, ttk.Label) and str(w.cget("textvariable")) == str(summary)
        ]
        assert len(label) == 1
        assert label[0].winfo_ismapped()
        assert "X 基準未定" in summary.get()
        assert "相鄰孔距" in summary.get()
        assert "Y 未定" in summary.get()
        assert "僅預覽、不提交製造" in summary.get()
        d = state["nfb_draft"]["draft"]
        p = nfb_ui1a_preview(d, bay_width_mm=800, upper_cell_height_mm=1600,
                             layer_heights_mm=[330, 830])
        assert not p["can_manufacture"] and not p["has_absolute_x"]
        assert all(l["absolute_x_mm"] is None for l in p["layers"])
        assert all(slot["absolute_x_mm"] is None
                   for l in p["layers"] for slot in l["slots"])
        assert KEY not in app._phase6_input_snapshot
    finally:
        if modal.winfo_exists():
            modal.destroy()
        root.destroy()
