"""One modal multi-settings surface, inline set editing and Family box defaults."""
import tkinter as tk

import pytest

from ae_engine.receiving_layout import new_receiving_layout
from ae_engine.receiving_quantity_box import normalize_common_box, project_common_box
from gui_modules.application.receiving_multi_settings_window import (
    default_preview_dimensions, display_dimension, open_multi_settings,
    paint_one_cabinet,
)
from phase6_assembly_panel import Phase6AssemblyPanel, AssemblyPanelActions


def test_missing_quantity_box_uses_family_dimensions_without_initialization():
    box = normalize_common_box(None)
    assert (box["w"], box["h"], box["d"]) == (800, 1600, 350)
    assert (project_common_box({"active_mode": "quantity"})["w"],
            project_common_box({"active_mode": "quantity"})["h"]) == (800, 1600)
    with pytest.raises(ValueError):
        normalize_common_box("not-a-box")
    assert default_preview_dimensions({"active_mode": "quantity"}) == (800, 1600, 350)
    assert display_dimension(800.0) == "800"
    assert display_dimension(800.5) == "800.5"


def test_assembly_button_is_hidden_until_receiving_assembly():
    root = tk.Tk()
    root.withdraw()
    calls = []
    try:
        owner = Phase6AssemblyPanel(
            root, actions=AssemblyPanelActions(
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


def test_modal_multi_settings_embeds_bay_editor_and_doors_without_preview_window():
    root = tk.Tk()
    root.geometry("950x750+0+0")
    root.update_idletasks()
    state = {"active_mode": "set_bay", "receiving_layout": new_receiving_layout(
        width=800, height=1600, depth=350,
    )}
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
            return (len(row["bays"]) for row in state["receiving_layout"]["sets"])
    changes = []
    selected = []
    def change_mode(mode):
        state["active_mode"] = mode
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
        "holes": lambda role: None,
    }
    def set_ports(index):
        row = state["receiving_layout"]["sets"][index]
        return {
            "row": lambda: row, "select": lambda bay: selected.append(bay),
            "change": lambda *args: None, "share": lambda *args: None,
            "unlink": lambda *args: None,
            "dimensions": lambda *args: None,
            "alignment": lambda *args: None, "holes": lambda *args: None,
            "brand": lambda *args: None, "subscribe": lambda fn: None,
        }
    try:
        win = open_multi_settings(
            root, get_snapshot=lambda: state, get_switch=Switch,
            switch_mode=change_mode, set_brand=lambda brand: None,
            add_set=lambda: None, remove_set=lambda: None,
            resize_connections=lambda index, delta: None,
            quantity_ports=ports,
            set_editor_ports=set_ports,
            common_editor_ports=lambda: {
                **set_ports(0),
                "row": lambda: project_common_box({
                    "active_mode": "quantity"})["receiving_layout"]["sets"][0],
            },
        )
        root.update()
        assert win.title() == "多只設定"
        assert win.grab_current() is win  # Main GUI is blocked until close.
        assert not hasattr(win, "_receiving_multi_preview")
        assert not win._receiving_multi_editor_host.winfo_children() or not any(
            isinstance(w, tk.Canvas) for w in win._receiving_multi_editor_host.winfo_children()
        )
        # Row action is '套用', NOT a nested settings Toplevel.
        row = win._receiving_multi_controls.layer_host._phase6_receiving_layer_rows[0]
        assert row["preview_button"].cget("text") == "套用"
        before = len(root.winfo_children())
        row["preview_button"].invoke()
        root.update()
        assert len(root.winfo_children()) == before
        panel = win._receiving_multi_current["panel"]
        sketch = win._receiving_multi_current["canvas"]
        assert panel is not None
        assert sketch is not None
        assert len(sketch.find_all()) >= 6
        door_labels = [
            sketch.itemcget(item, "text")
            for item in sketch.find_all() if sketch.type(item) == "text"
        ]
        assert "上門" in door_labels and "下門" in door_labels
        assert panel._receiving_active == 0
        assert len(win._receiving_multi_controls.layer_host.winfo_children()) == 1

        assert open_multi_settings(root, get_snapshot=lambda: state, get_switch=Switch,
            switch_mode=change_mode, set_brand=lambda brand: None,
            add_set=lambda: None, remove_set=lambda: None,
            resize_connections=lambda i,d: None,
            quantity_ports=ports, set_editor_ports=set_ports) is win
        win._receiving_multi_notebook.select(1)
        root.update()
        assert changes == ["quantity"]
        win._receiving_multi_quantity.add()
        assert len(quantity["versions"]) == 2
        win._receiving_multi_notebook.select(0)
        root.update()
        assert changes == ["quantity", "set_bay"]
        assert len(quantity["versions"]) == 2
        win.protocol("WM_DELETE_WINDOW")()
        root.update()
        assert root.grab_current() is None
    finally:
        root.destroy()


def test_single_sketch_has_basic_upper_and_lower_doors():
    root = tk.Tk()
    root.withdraw()
    try:
        canvas = tk.Canvas(root, width=340, height=285)
        assert paint_one_cabinet(canvas, (800, 1600, 350)) == 2
        labels = [canvas.itemcget(i, "text") for i in canvas.find_all()
                  if canvas.type(i) == "text"]
        assert "上門" in labels and "下門" in labels
    finally:
        root.destroy()
