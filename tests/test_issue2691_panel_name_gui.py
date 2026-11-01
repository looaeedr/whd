# -*- coding: utf-8 -*-
"""#2691: native Tk panel-name editing routes to canonical Engine authority."""
from __future__ import annotations

import os
from types import SimpleNamespace
import tkinter as tk
from tkinter import messagebox

import pytest

from ae_engine import manufacturing_api
from ae_engine.receiving_layout import (
    new_receiving_layout, resize_receiving_bays, resize_receiving_sets,
)
from gui_modules.application.receiving_set_bay_adapter import ReceivingSetBayAdapter
from gui_modules.application.receiving_multi_settings_window import (
    open_multi_settings, paint_connected_bays,
)
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project
from phase6_settings_panel import Phase6SettingsPanel

pytestmark = pytest.mark.skipif(
    os.name != "nt" and not os.environ.get("DISPLAY"),
    reason="native Tk requires Windows desktop or Linux Xvfb",
)


def _layout():
    state = new_receiving_layout(width=800, height=1600, depth=350)
    state = resize_receiving_bays(state, set_index=0, bay_count=2)
    return resize_receiving_sets(state, set_count=2)


def _names(layout):
    return [bay["panel_name"] for group in layout["sets"] for bay in group["bays"]]


def _click_at(canvas, coords):
    x0, y0, x1, y1 = coords
    return int((x0 + x1) / 2), int((y0 + y1) / 2)


def test_native_receiving_label_canvas_edit_error_escape_and_two_sets(monkeypatch):
    root = tk.Tk()
    root.geometry("800x600+0+0")
    root.update()  # The transient child must map to receive actual Tk mouse events.
    state = {"layout": _layout()}
    selected = []
    warnings = []
    monkeypatch.setattr(messagebox, "showwarning", lambda *args, **kwargs:
                        warnings.append((args, kwargs)))
    def switch():
        value = state["layout"]
        return SimpleNamespace(
            layout=value,
            connection_counts=lambda: tuple(len(row["bays"]) for row in value["sets"]),
        )
    def rename(si, bi, text):
        state["layout"] = manufacturing_api.rename_receiving_panel(
            state["layout"], set_index=si, bay_index=bi, panel_name=text,
        )
        return True

    win = None
    try:
        win = open_multi_settings(
            root, get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=switch, switch_mode=lambda _mode: True,
            resize_connections=lambda _index, _delta: True,
            select_bay=lambda si, bi: selected.append((si, bi)),
            rename_bay=rename,
            get_brand=lambda: "士林",
        )
        root.update()
        assert win._receiving_multi_apply(0)
        root.update()
        canvas = win._receiving_multi_canvas
        assert len(canvas.find_withtag("receiving_panel_name")) == 2
        assert [canvas.itemcget(i, "text") for i in
                canvas.find_withtag("receiving_panel_name")] == ["P1", "P2"]

        # Existing click outside a label continues to select the physical Bay.
        x0, y0, x1, y1 = canvas._receiving_bay_hitboxes[1]
        canvas.event_generate("<Button-1>", x=int((x0+x1)/2),
                              y=int((y0+y1)/2))
        root.update()
        assert win._receiving_multi_applied["selected"] == 1
        assert selected[-1] == (0, 1)

        label = canvas._receiving_panel_name_hitboxes[1]
        x, y = _click_at(canvas, label)
        # Tcl event_generate forbids the Double modifier; exercise the exact
        # production callback bound to <Double-Button-1> instead.
        assert canvas.bind("<Double-Button-1>")
        win._receiving_panel_name_edit(SimpleNamespace(x=x, y=y))
        root.update()
        entry = win._receiving_panel_name_entry
        assert entry is not None and entry.get() == "P2"
        entry.delete(0, tk.END)
        entry.insert(0, "P1")
        win._receiving_panel_name_commit()
        assert warnings and "重複" in warnings[-1][0][1]
        assert win._receiving_panel_name_entry is entry
        assert _names(state["layout"]) == ["P1", "P2", "P3"]

        entry.delete(0, tk.END)
        entry.insert(0, "Bad/Name")
        win._receiving_panel_name_commit()
        assert win._receiving_panel_name_entry is entry
        assert _names(state["layout"]) == ["P1", "P2", "P3"]

        entry.delete(0, tk.END)
        entry.insert(0, "TMP")
        win._receiving_panel_name_cancel()
        assert win._receiving_panel_name_entry is None
        assert _names(state["layout"]) == ["P1", "P2", "P3"]

        label = canvas._receiving_panel_name_hitboxes[1]
        x, y = _click_at(canvas, label)
        # Tcl event_generate forbids the Double modifier; exercise the exact
        # production callback bound to <Double-Button-1> instead.
        assert canvas.bind("<Double-Button-1>")
        win._receiving_panel_name_edit(SimpleNamespace(x=x, y=y))
        entry = win._receiving_panel_name_entry
        assert entry is not None
        entry.delete(0, tk.END)
        entry.insert(0, "主受電盤")
        win._receiving_panel_name_commit()
        assert _names(state["layout"]) == ["P1", "主受電盤", "P3"]
        assert [canvas.itemcget(i, "text") for i in
                canvas.find_withtag("receiving_panel_name")] == ["P1", "主受電盤"]

        assert win._receiving_multi_apply(1)
        assert [canvas.itemcget(i, "text") for i in
                canvas.find_withtag("receiving_panel_name")] == ["P3"]
        assert _names(state["layout"]) == ["P1", "主受電盤", "P3"]

        # A Set switch while an inline draft is open discards that draft,
        # never accidentally renames a Bay from the previous Set.
        x, y = _click_at(canvas, canvas._receiving_panel_name_hitboxes[0])
        win._receiving_panel_name_edit(SimpleNamespace(x=x, y=y))
        assert win._receiving_panel_name_entry is not None
        assert win._receiving_multi_apply(0)
        assert win._receiving_panel_name_entry is None
        assert _names(state["layout"]) == ["P1", "主受電盤", "P3"]
    finally:
        if win is not None and win.winfo_exists():
            win._receiving_multi_close()
        root.destroy()


def test_render_name_overlay_changes_no_manufacturing_geometry():
    root = tk.Tk()
    root.withdraw()
    try:
        canvas = tk.Canvas(root, width=580, height=320)
        canvas.pack()
        paint_connected_bays(
            canvas, 2, selected=(0,), panel_names=("P1", "ABC"),
        )
        assert len(canvas._receiving_bay_hitboxes) == 2
        assert len(canvas._receiving_panel_name_hitboxes) == 2
        assert [canvas.itemcget(i, "text") for i in
                canvas.find_withtag("receiving_panel_name")] == ["P1", "ABC"]
    finally:
        root.destroy()


def test_receiving_adapter_rename_is_source_only_and_preserves_selection():
    adapter = ReceivingSetBayAdapter(_layout())
    adapter.select_set(2)
    adapter.select_bay(1)
    before = adapter.selection
    identity = adapter.current_bay()["stable_id"]
    assert adapter.rename_bay(0, 1, "分電盤") is True
    assert adapter.selection == before
    assert adapter.current_bay()["stable_id"] == identity
    assert _names(adapter.layout) == ["P1", "分電盤", "P3"]
    with pytest.raises(ValueError):
        adapter.rename_bay(1, 0, "分電盤")
    assert _names(adapter.layout) == ["P1", "分電盤", "P3"]


def test_vault_global_panel_name_uses_engine_and_save_reload(monkeypatch, tmp_path):
    root = tk.Tk()
    root.withdraw()
    snapshot = {"model": "金庫型"}
    updates = []
    warnings = []
    monkeypatch.setattr(messagebox, "showwarning", lambda *a, **k:
                        warnings.append((a, k)))
    def submit(name):
        nonlocal snapshot
        snapshot = manufacturing_api.set_cabinet_panel_name(snapshot, name)
        updates.append(snapshot["panel_name"])
        return snapshot["panel_name"]

    panel = Phase6SettingsPanel(
        values_snapshot=lambda: {"w": 500, "h": 600, "d": 200, "t": 2},
        stage_setting_update=lambda *_: None,
        flush_settings=lambda: None,
        save_defaults=lambda _: None,
        panel_name_getter=lambda: snapshot.get("panel_name", ""),
        panel_name_changed=submit,
    )
    try:
        panel.build_left_global_controls(
            root, baseline_models=("金庫型", "受電箱"),
            initial_model="金庫型",
        )
        assert panel.panel_name_frame.winfo_manager() == "grid"
        assert panel.panel_name_var.get() == ""
        panel.panel_name_var.set("ABC/DEF")
        panel.commit_panel_name()
        assert warnings
        assert updates == []
        assert panel.panel_name_var.get() == "ABC/DEF"
        panel.cancel_panel_name()
        assert panel.panel_name_var.get() == ""

        panel.panel_name_var.set("金庫01")
        panel.commit_panel_name()
        assert updates == ["金庫01"]
        path = write_project(tmp_path / "vault.p6fold", {
            "schema": PROJECT_SCHEMA, "snapshot": snapshot, "final_geometry": {},
        })
        snapshot = read_project(path)["snapshot"]
        panel.refresh_panel_name(force=True)
        assert panel.panel_name_var.get() == "金庫01"

        panel.baseline_model_var.set("受電箱")
        assert panel.panel_name_frame.winfo_manager() == ""
        panel.baseline_model_var.set("金庫型")
        assert panel.panel_name_frame.winfo_manager() == "grid"
        assert panel.panel_name_var.get() == "金庫01"
    finally:
        root.destroy()
