# -*- coding: utf-8 -*-
"""#1504 AC-20/SWT-13: original inner-door Tk editor layer and unit brand UX.

This actually opens the production inner editor via its existing candidate
ports, dispatches native ComboboxSelected events and clicks the real Undo
button. No faux standalone Tk controls, artificial approvals or factory DXF.
"""
from copy import deepcopy
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk, messagebox

from ae_engine.receiving_inner_door_candidates import ROLE, KEY
from ae_engine.receiving_layout import new_receiving_layout
from ae_engine.receiving_nfb_ui1a import INHERIT, OVERRIDE, NEEDS_RESELECTION, nfb_ui1a_preview
from ae_engine.receiving_nfb_model_identity import numeric_model_refs
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
from gui_modules.application import fold_designer_composition_receiving as comp
from gui_modules.application import receiving_multi_settings_window as view


def _walk(container):
    for w in container.winfo_children():
        yield w
        yield from _walk(w)


def _brand_combo(container, leading):
    matches = [
        w for w in _walk(container)
        if isinstance(w, ttk.Combobox)
        and tuple(w.cget("values"))[:1] == (leading,)
    ]
    assert len(matches) == 1, (leading, matches)
    return matches[0]


def _button(container, caption):
    matches = [
        w for w in _walk(container)
        if isinstance(w, ttk.Button) and w.cget("text") == caption
    ]
    assert len(matches) == 1, (caption, matches)
    return matches[0]


def _open_original_editor(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        view, "open_multi_settings",
        lambda _root, **kwargs: captured.update(kwargs) or object(),
    )
    root = tk.Tk()
    root.geometry("550x460+20+20")
    root.update_idletasks()
    adapter = ReceivingSetBayAdapter(
        new_receiving_layout(width=800, height=1600, depth=350),
    )
    app = SimpleNamespace(
        root=root,
        _phase6_input_snapshot={"active_mode": "set_bay", "model": "受電箱"},
        _settings_values={},
        _phase6_box_whd={"w": 800, "h": 1600, "d": 350, "t": 2},
        _phase6_endcap_bottom_wrap_state={},
        designer_workspace=None,
    )
    assembly = SimpleNamespace(
        app=app,
        receiving_layout_applicable=lambda: True,
        receiving_adapter=lambda _ns: adapter,
        receiving_switch_adapter=lambda _ns: SimpleNamespace(brand="士林"),
        corner_transaction_payload=lambda _ns: {},
        collect_workspace_state=lambda _ns: {},
    )
    try:
        comp.open_receiving_multi_settings(assembly, "test")
        editor = captured["get_inner_candidate_ports"]()["edit"]
        modal = editor(ROLE, None, lambda _version: None)
        root.update()
    except BaseException:
        root.destroy()
        raise
    return root, app, modal


def test_ac20_original_inner_tk_layer_brand_cancel_confirm_undo(monkeypatch):
    prompts = []
    answers = iter((False, True))
    monkeypatch.setattr(
        messagebox, "askyesno",
        lambda title, body, **kwargs: (
            prompts.append((title, body)), next(answers)
        )[1],
    )
    root, app, modal = _open_original_editor(monkeypatch)
    try:
        state = modal._receiving_inner_switch_state
        first = state["rows"][0]
        layer_combo = _brand_combo(first["section"], "繼承本套")
        assert layer_combo.winfo_ismapped()  # operator can actually use it
        assert _brand_combo(first["section"], "繼承本層").winfo_ismapped()
        first["available"].selection_set(0)
        _button(first["section"], "＋加入").invoke()
        root.update()
        initial = deepcopy(state["nfb_draft"]["draft"])
        original_ref = initial["layers"][0]["slots"][0]["filename"]
        assert original_ref in numeric_model_refs("士林")
        assert initial["layers"][0]["slots"][0]["source_brand"] == "士林"

        layer_combo.set("東元")
        layer_combo.event_generate("<<ComboboxSelected>>")
        root.update()
        assert len(prompts) == 1
        assert "1 顆" in prompts[0][1]
        assert state["nfb_draft"]["draft"] == initial
        assert state["edit_session"].current == initial
        assert layer_combo.get() == "繼承本套"
        assert KEY not in app._phase6_input_snapshot

        layer_combo.set("東元")
        layer_combo.event_generate("<<ComboboxSelected>>")
        root.update()
        changed = state["nfb_draft"]["draft"]
        assert len(prompts) == 2
        assert "1 顆" in prompts[1][1]
        assert changed["layers"][0]["brand"] == {
            "mode": OVERRIDE, "value": "東元",
        }
        assert changed["layers"][0]["slots"][0]["filename"] == original_ref
        assert changed["layers"][0]["slots"][0]["source_brand"] == "士林"
        preview = nfb_ui1a_preview(
            changed, bay_width_mm=800, upper_cell_height_mm=1100,
        )
        assert preview["layers"][0]["slots"][0]["status"] == NEEDS_RESELECTION
        assert not preview["can_manufacture"]
        assert KEY not in app._phase6_input_snapshot

        _button(modal, "復原 NFB").invoke()
        root.update()
        assert state["nfb_draft"]["draft"] == initial
        assert layer_combo.get() == "繼承本套"
        assert len(prompts) == 2
    finally:
        if modal.winfo_exists():
            modal.destroy()
        root.destroy()


def test_swt13_original_inner_tk_unit_cancel_and_same_brand_override(monkeypatch):
    prompts = []
    answers = iter((False, True))
    monkeypatch.setattr(
        messagebox, "askyesno",
        lambda title, body, **kwargs: (
            prompts.append((title, body)), next(answers)
        )[1],
    )
    root, app, modal = _open_original_editor(monkeypatch)
    try:
        state = modal._receiving_inner_switch_state
        first = state["rows"][0]
        unit_combo = _brand_combo(first["section"], "繼承本層")
        assert unit_combo.winfo_ismapped()
        # No selected unit: must reject and restore the on-screen value.
        unit_combo.set("東元")
        unit_combo.event_generate("<<ComboboxSelected>>")
        root.update()
        assert unit_combo.get() == "繼承本層"
        assert "請先選取" in state["warning"].get()

        first["available"].selection_set(0)
        _button(first["section"], "＋加入").invoke()
        first["assigned"].selection_set(0)
        first["assigned"].event_generate("<<ListboxSelect>>")
        root.update()
        before = deepcopy(state["nfb_draft"]["draft"])
        source = before["layers"][0]["slots"][0]["filename"]
        assert source in numeric_model_refs("士林")

        unit_combo.set("東元")
        unit_combo.event_generate("<<ComboboxSelected>>")
        root.update()
        assert "1 顆" in prompts[0][1]
        assert state["nfb_draft"]["draft"] == before
        assert unit_combo.get() == "繼承本層"

        unit_combo.set("東元")
        unit_combo.event_generate("<<ComboboxSelected>>")
        root.update()
        changed = state["nfb_draft"]["draft"]
        assert len(prompts) == 2
        assert changed["layers"][0]["slots"][0]["brand"] == {
            "mode": OVERRIDE, "value": "東元",
        }
        assert changed["layers"][0]["slots"][0]["filename"] == source
        assert changed["layers"][0]["slots"][0]["source_brand"] == "士林"
        assert nfb_ui1a_preview(
            changed, bay_width_mm=800, upper_cell_height_mm=1100,
        )["layers"][0]["slots"][0]["status"] == NEEDS_RESELECTION

        _button(modal, "復原 NFB").invoke()
        root.update()
        assert state["nfb_draft"]["draft"] == before
        assert unit_combo.get() == "繼承本層"
        # Explicit same-value override must remain an override, not INHERIT.
        unit_combo.set("士林")
        unit_combo.event_generate("<<ComboboxSelected>>")
        root.update()
        same = state["nfb_draft"]["draft"]["layers"][0]["slots"][0]
        assert same["brand"] == {"mode": OVERRIDE, "value": "士林"}
        assert same["filename"] == source
        assert len(prompts) == 2
        _button(modal, "復原 NFB").invoke()
        root.update()
        assert state["nfb_draft"]["draft"] == before
        assert KEY not in app._phase6_input_snapshot
    finally:
        if modal.winfo_exists():
            modal.destroy()
        root.destroy()
