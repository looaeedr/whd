"""Temporary combined multi-settings entry: cheap single preview, saved mode owners."""
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk
import pytest

from gui_modules.application.receiving_multi_settings_window import (
    open_multi_settings, default_preview_dimensions, display_dimension,
)
from phase6_assembly_panel import Phase6AssemblyPanel, AssemblyPanelActions


def test_preview_one_box_uses_existing_mode_dimensions_without_geometry():
    data = {"active_mode": "set_bay", "receiving_layout": {"sets": [{"bays": [
        {"width": 900, "height": 1700, "depth": 400},
        {"width": 1200, "height": 1800, "depth": 500},
    ]}]}}
    assert default_preview_dimensions(data) == (900, 1700, 400)
    assert default_preview_dimensions({"active_mode": "quantity"}) == (800, 1600, 350)
    assert display_dimension(800.0) == "800"
    assert display_dimension(800.5) == "800.5"


def test_assembly_button_is_hidden_until_receiving_assembly():
    root = tk.Tk()
    root.withdraw()
    calls = []
    try:
        owner = Phase6AssemblyPanel(
            root,
            actions=AssemblyPanelActions(
                on_visibility_changed=lambda: None,
                on_multi_settings=lambda: calls.append(1),
            ),
        )
        owner.host.pack()
        assert not owner.multi_settings_entry.winfo_manager()
        owner.set_multi_settings_visible(True)
        root.update_idletasks()
        assert owner.multi_settings_entry.winfo_manager()
        owner.multi_settings_button.invoke()
        assert calls == [1]
        owner.set_multi_settings_visible(False)
        assert not owner.multi_settings_entry.winfo_manager()
    finally:
        root.destroy()


def test_multi_settings_first_open_is_one_cheap_cabinet_and_preserves_section_state(monkeypatch):
    # This smoke test intentionally does not mock the manufacturing service:
    # the initial dialog must not import or call it at all.
    root = tk.Tk()
    root.withdraw()
    state = {"active_mode": "set_bay", "receiving_layout": {
        "sets": [{"bays": [{"width": 800, "height": 1600, "depth": 350}]}],
    }}
    quantity = {
        "schema": "phase6-quantity-v1",
        "versions": [{"version_id": "quantity-v1", "piece_count": 1,
                      "head_features": [], "tail_features": []}],
        "selected_version_id": "quantity-v1",
        "next_version_number": 2,
    }
    class Switch:
        brand = "士林"
        def connection_counts(self):
            return (1,)
    changes = []
    def change_mode(mode):
        state["active_mode"] = mode
        if mode == "quantity":
            state["receiving_quantity_box"] = {"w": 800, "h": 1600, "d": 350}
        changes.append(mode)
        return True
    def payload():
        return quantity if state["active_mode"] == "quantity" else None
    def add():
        quantity["versions"].append({
            "version_id": "quantity-v2", "piece_count": 1,
            "head_features": [], "tail_features": []})
        quantity["selected_version_id"] = "quantity-v2"
    ports = {
        "snapshot": payload, "add": add, "select": lambda v: None,
        "delete": lambda v: None, "count": lambda v: None,
        "holes": lambda role: None, "common": lambda: None,
    }
    try:
        win = open_multi_settings(
            root, get_snapshot=lambda: state, get_switch=Switch,
            switch_mode=change_mode, set_brand=lambda brand: None,
            add_set=lambda: None, remove_set=lambda: None,
            resize_connections=lambda index, delta: None,
            open_set_settings=lambda index: None, quantity_ports=ports,
        )
        root.update()
        assert win.title() == "多只設定"
        assert state["active_mode"] == "set_bay"
        assert len(win._receiving_multi_preview.find_all()) == 3
        assert len(win._receiving_multi_controls.layer_host.winfo_children()) == 1
        assert open_multi_settings(root, get_snapshot=lambda: state,
            get_switch=Switch, switch_mode=change_mode,
            set_brand=lambda brand: None, add_set=lambda: None,
            remove_set=lambda: None, resize_connections=lambda i,d: None,
            open_set_settings=lambda i: None, quantity_ports=ports) is win
        win._receiving_multi_notebook.select(1)
        root.update()
        assert changes == ["quantity"]
        assert win._receiving_multi_quantity.frame.winfo_manager()
        win._receiving_multi_quantity.add()
        assert len(quantity["versions"]) == 2
        win._receiving_multi_notebook.select(0)
        root.update()
        assert changes == ["quantity", "set_bay"]
        assert len(quantity["versions"]) == 2
        assert len(win._receiving_multi_preview.find_all()) == 3
        win.destroy()
    finally:
        root.destroy()
