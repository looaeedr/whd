# -*- coding: utf-8 -*-
"""#1504 NFB-AC-01: actual Receiving-only NFB Tk operator entry.

An original generic/Vault Door Hole Editor remains a different entry, not a
patched "Receiving" dialog; the ONLY wired Receiving UI is gated by the
canonical family capability.  Assert real Tk widgets and original entry
guards, not fabricated function-name flags or an NFB model-only preview.
This is current automated UI scope, not two historic .p6fold Windows UAT.
"""
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk

import pytest

from ae_engine.cabinet_types import policy as family_policy
from ae_engine.receiving_layout import new_receiving_layout
from ae_engine.receiving_switch_layout import RECEIVING_SWITCH_BRANDS
from gui_modules.application.fold_designer_capability_owners import (
    ReceivingCapabilityOwner, ReceivingCapabilityPorts,
)
from gui_modules.application.fold_designer_composition_receiving import (
    receiving_layout_applicable, open_receiving_multi_settings,
)
from gui_modules.application.receiving_inner_door_hole_editor import (
    is_inner_door_sheet, open_inner_door_hole_editor,
)
from gui_modules.application.receiving_multi_settings_window import (
    open_multi_settings,
)


def _actual_family_gateway(app):
    return ReceivingCapabilityOwner(ReceivingCapabilityPorts(
        input_snapshot=lambda: app._phase6_input_snapshot,
        current_adapter=lambda: None,
        publish_adapter=lambda _adapter: None,
        canonical_family_name=family_policy.canonical_family_name,
    ))


class _Entry:
    """Minimal workbench facade; calls UNMODIFIED production gateway."""
    receiving_layout_applicable = receiving_layout_applicable

    def __init__(self, app):
        self.app = app
        self._capabilities = SimpleNamespace(
            receiving=_actual_family_gateway(app),
        )


def _walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from _walk(child)


@pytest.mark.parametrize("family", ("金庫型", "控制箱", "配電箱"))
@pytest.mark.parametrize("mode", ("single", "multi"))
def test_ac01_nonreceiving_family_never_mounts_nfb_dialog_or_mutates_hole_editor(
    family, mode,
):
    root = tk.Tk()
    root.withdraw()
    try:
        app = SimpleNamespace(root=root, _phase6_input_snapshot={
            "model": family, "active_mode": "set_bay",
        })
        gateway = _Entry(app)
        baseline = tuple(root.winfo_children())
        before_snapshot = dict(app._phase6_input_snapshot)
        assert family_policy.canonical_family_name(before_snapshot) != "受電箱"
        assert gateway.receiving_layout_applicable() is False
        # No call into Receiving modal or NFB sources even via direct legacy
        # entry; the original generic Hole Editor and its features stay free.
        assert open_receiving_multi_settings(
            gateway, {}, single=(mode == "single"),
        ) is False
        assert tuple(root.winfo_children()) == baseline
        assert app._phase6_input_snapshot == before_snapshot
        assert not hasattr(root, "_receiving_multi_settings_window")
    finally:
        root.destroy()


def test_ac01_original_generic_hole_editor_door_entry_remains_unpatched():
    # The existing generic door part does not become a Receiving inner door
    # merely because a Receiving/NFB modal exists elsewhere in WHD.
    root = tk.Tk()
    root.withdraw()
    try:
        called = []
        class OriginalHost:
            def query(self, *_):
                return None
            def _open_unified_hole_editor(self, *_a, **_kw):
                called.append(True)
                raise AssertionError("Receiving must not steal generic Hole Editor")
        original = OriginalHost()
        app = SimpleNamespace(
            _scene_query_callback=original.query,
            designer_workspace=SimpleNamespace(available_parts=("door",),
                                               active_part="door"),
            _phase6_input_snapshot={"model": "金庫型"},
            root=root,
        )
        before = tuple(root.winfo_children())
        assert is_inner_door_sheet("door") is False
        assert is_inner_door_sheet("head") is False
        assert is_inner_door_sheet("tail") is False
        with pytest.raises(ValueError, match="不是可開孔編輯的內門"):
            open_inner_door_hole_editor(app, "door", settings_mode="single")
        assert called == []
        assert tuple(root.winfo_children()) == before
        # Even a forged inner-door-shaped part key cannot synthesize a
        # Receiving physical panel for a genuine non-Receiving family.
        with pytest.raises(ValueError, match="沒有這片內門"):
            open_inner_door_hole_editor(
                app, "inner_door:upper:panel", settings_mode="single",
            )
        assert called == []
        assert tuple(root.winfo_children()) == before
    finally:
        root.destroy()


@pytest.mark.parametrize("mode,brand", (
    ("set_bay", "士林"), ("quantity", "東元"),
))
def test_ac01_actual_receiving_tk_operator_nfb_selector_only_under_family(
    mode, brand,
):
    """Build the ACTUAL modal, inspect the real readonly NFB Combobox."""
    root = tk.Tk()
    root.withdraw()
    try:
        layout = new_receiving_layout(width=800, height=1600, depth=350)
        layout["sets"][0]["switch_brand"] = brand
        app = SimpleNamespace(root=root, _phase6_input_snapshot={
            "model": "受電箱", "active_mode": mode,
            "receiving_layout": layout,
        })
        actual_gateway = _Entry(app)
        assert actual_gateway.receiving_layout_applicable() is True
        switch = SimpleNamespace(layout=layout, connection_counts=lambda: (1,))
        changes = []
        win = open_multi_settings(
            root,
            get_snapshot=lambda: {"active_mode": mode},
            get_switch=lambda: switch,
            switch_mode=lambda _mode: True,
            resize_connections=lambda _index, _delta: None,
            get_brand=lambda: brand,
            set_brand=lambda value: changes.append(value) or True,
            dialog_kind="single" if mode == "quantity" else "multi",
        )
        assert win.winfo_exists()
        assert win.title() == ("單只設定" if mode == "quantity" else "多連設定")
        selector = win._receiving_multi_brand_selector
        assert isinstance(selector, ttk.Combobox)
        assert selector.instate(("readonly",)) is True
        assert tuple(selector.cget("values")) == RECEIVING_SWITCH_BRANDS
        assert win._receiving_multi_brand_var.get() == brand
        assert selector in tuple(_walk(win))
        nfb_titles = [x.cget("text") for x in _walk(win)
                      if isinstance(x, ttk.Label) and x.cget("text") == "NFB"]
        assert len(nfb_titles) == 1
        # Selection uses the ORIGINAL existing brand-control callback.
        alternative = "東元" if brand == "士林" else "士林"
        selector.set(alternative)
        selector.event_generate("<<ComboboxSelected>>")
        root.update()
        assert changes == [alternative]
        win._receiving_multi_close()
        assert not win.winfo_exists()
        assert root._receiving_multi_settings_window is None
    finally:
        root.destroy()
