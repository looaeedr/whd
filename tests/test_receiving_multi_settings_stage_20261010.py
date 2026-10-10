"""GUI contract: only explicitly requested multi-settings elements are visible."""
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

import pytest

from ae_engine.receiving_quantity_box import normalize_common_box, project_common_box
from gui_modules.application.receiving_multi_settings_window import (
    default_preview_dimensions, display_dimension, open_multi_settings,
    paint_connected_bays,
)
from phase6_assembly_panel import Phase6AssemblyPanel, AssemblyPanelActions


def test_family_dimensions_without_initialization_dialog():
    box = normalize_common_box(None)
    assert (box["w"], box["h"], box["d"]) == (800, 1600, 350)
    sample = project_common_box({"active_mode": "quantity"})
    assert (sample["w"], sample["h"]) == (800, 1600)
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


def _visible_texts(widget):
    result = []
    for child in widget.winfo_children():
        try:
            if child.winfo_ismapped():
                text = child.cget("text")
                if text:
                    result.append(str(text))
        except tk.TclError:
            pass
        result.extend(_visible_texts(child))
    return tuple(result)


def test_modal_fullscreen_strict_controls_apply_and_highlight():
    root = tk.Tk()
    root.geometry("800x600+0+0")
    root.update()
    counts = [1]
    mode = {"value": "set_bay"}
    selected = []
    selected_settings = []
    resized = []

    def resize(index, delta):
        resized.append((index, delta))
        counts[index] = max(1, counts[index] + delta)
        return True

    def switch(target):
        mode["value"] = target
        return True

    try:
        win = open_multi_settings(
            root, get_snapshot=lambda: {"active_mode": mode["value"]},
            get_switch=lambda: SimpleNamespace(
                connection_counts=lambda: tuple(counts)),
            switch_mode=switch, resize_connections=resize,
            select_bay=lambda set_index, bay_index: selected.append(
                (set_index, bay_index)),
            on_setting_selected=lambda set_index, bay_index, kind:
                selected_settings.append((set_index, bay_index, kind)),
        )
        root.update()
        assert win.title() == "多只設定"
        assert win.grab_current() is win
        assert win.winfo_width() >= win.winfo_screenwidth() - 2
        assert win.winfo_height() >= win.winfo_screenheight() - 2
        assert win._receiving_multi_mode_var.get() == "set_bay"
        texts = _visible_texts(win)
        assert set(texts) == {"套／連", "數量", "第1套", "＋連", "1", "－連", "套用"}
        assert not hasattr(win, "_receiving_multi_preview")
        assert not hasattr(win, "_receiving_multi_notebook")
        canvas = win._receiving_multi_canvas
        rows_host = win._receiving_multi_rows_host
        mode_row = win._receiving_multi_mode_controls
        setting_list = win._receiving_multi_setting_list
        controls_column = rows_host.master
        # Both the action row and the three-item LIST (not a dropdown) sit
        # directly below upper-left mode choices; 2D stays lower right.
        assert mode_row.grid_info()["row"] == 0
        assert controls_column.grid_info()["row"] == 1
        assert controls_column.grid_info()["column"] == 0
        assert canvas.grid_info()["row"] == 1
        assert canvas.grid_info()["column"] == 1
        assert abs(controls_column.winfo_rootx() - mode_row.winfo_rootx()) <= 2
        vertical_gap = controls_column.winfo_rooty() - (
            mode_row.winfo_rooty() + mode_row.winfo_height()
        )
        assert 0 <= vertical_gap <= 32
        assert isinstance(setting_list, tk.Listbox)
        assert setting_list.master is controls_column
        assert setting_list.winfo_ismapped()
        assert tuple(setting_list.get(0, tk.END)) == ("封頭", "封尾", "內門")
        assert setting_list.curselection() == ()
        assert len(canvas._receiving_bay_hitboxes) == 1
        assert win._receiving_multi_applied["set_index"] is None
        assert win._receiving_multi_applied["selected"] is None
        # Selecting existing settings forwards to the ORIGINAL per-bay
        # domain keys without opening another window or changing geometry.
        toplevels_before = len(root.winfo_children())
        setting_list.selection_set(0)
        setting_list.event_generate("<<ListboxSelect>>")
        root.update()
        assert selected_settings == [(0, 0, "head_features")]
        setting_list.selection_clear(0, tk.END)
        setting_list.selection_set(1)
        setting_list.event_generate("<<ListboxSelect>>")
        root.update()
        assert selected_settings[-1] == (0, 0, "tail_features")
        setting_list.selection_clear(0, tk.END)
        setting_list.selection_set(2)
        setting_list.event_generate("<<ListboxSelect>>")
        root.update()
        assert selected_settings[-1] == (0, 0, "inner_door_layers")
        assert len(root.winfo_children()) == toplevels_before
        assert len(canvas._receiving_bay_hitboxes) == 1

        def current_row():
            return rows_host.winfo_children()[0].winfo_children()

        def current_buttons():
            return [w for w in current_row() if isinstance(w, ttk.Button)]

        def displayed_count():
            labels = [w.cget("text") for w in current_row()
                      if isinstance(w, ttk.Label)]
            return labels[1]

        assert [w.cget("text") for w in current_row()] == [
            "第1套", "＋連", "1", "－連", "套用"]
        plus, minus, apply = current_buttons()
        plus.invoke()
        assert displayed_count() == "2"
        plus, minus, apply = current_buttons()
        plus.invoke()
        assert displayed_count() == "3"
        assert counts == [3]
        assert len(canvas._receiving_bay_hitboxes) == 1  # apply controls the sketch
        assert win._receiving_multi_apply(0) is True
        assert len(canvas._receiving_bay_hitboxes) == 3
        assert selected == [(0, 0)]
        assert win._receiving_multi_applied["selected"] == 0
        assert setting_list.curselection() == ()
        hits = canvas._receiving_bay_hitboxes
        assert hits[0][2] == hits[1][0] == hits[0][2]
        assert hits[1][2] == hits[2][0]

        x0, y0, x1, y1 = hits[2]
        canvas.event_generate("<Button-1>", x=int((x0 + x1) / 2),
                              y=int((y0 + y1) / 2))
        root.update()
        assert selected[-1] == (0, 2)
        assert win._receiving_multi_applied["selected"] == 2
        assert canvas._receiving_selected_bay == 2
        setting_list.selection_set(0)
        setting_list.event_generate("<<ListboxSelect>>")
        root.update()
        assert selected_settings[-1] == (0, 2, "head_features")
        x0, y0, x1, y1 = hits[1]
        canvas.event_generate("<Button-1>", x=int((x0 + x1) / 2),
                              y=int((y0 + y1) / 2))
        root.update()
        assert selected_settings[-1] == (0, 1, "head_features")

        plus, minus, apply = current_buttons()
        minus.invoke()
        assert counts == [2]
        assert displayed_count() == "2"
        assert len(canvas._receiving_bay_hitboxes) == 3
        apply.invoke()
        assert len(canvas._receiving_bay_hitboxes) == 2
        assert win._receiving_multi_applied["selected"] == 0

        # Two choices are mutually exclusive; no quantity-version table or
        # common-box affordance is exposed until explicitly requested.
        choices = [w for w in win._receiving_multi_mode_controls.winfo_children()
                   if isinstance(w, ttk.Radiobutton)]
        assert len(choices) == 2
        choices[1].invoke()
        root.update()
        assert mode["value"] == "quantity"
        assert not rows_host.winfo_children()
        assert not setting_list.winfo_ismapped()
        assert len(canvas._receiving_bay_hitboxes) == 1
        assert set(_visible_texts(win)) == {"套／連", "數量"}
        choices[0].invoke()
        root.update()
        assert mode["value"] == "set_bay"
        assert "第1套" in _visible_texts(win)
        assert setting_list.winfo_ismapped()
        assert tuple(setting_list.get(0, tk.END)) == ("封頭", "封尾", "內門")
        assert open_multi_settings(
            root, get_snapshot=lambda: {"active_mode": mode["value"]},
            get_switch=lambda: None, switch_mode=switch,
            resize_connections=resize,
        ) is win
        win._receiving_multi_close()
        root.update()
        assert root.grab_current() is None
    finally:
        root.destroy()


def test_two_doors_in_every_touching_bay_and_one_selection():
    root = tk.Tk()
    root.withdraw()
    try:
        canvas = tk.Canvas(root, width=500, height=300)
        assert paint_connected_bays(canvas, 4, selected=2) == 4
        assert len(canvas._receiving_bay_hitboxes) == 4
        assert canvas._receiving_selected_bay == 2
        bounds = canvas._receiving_bay_hitboxes
        assert all(bounds[i][2] == bounds[i+1][0] for i in range(3))
        # 4 pieces per bay: body, upper door, lower door, door divider.
        assert len(canvas.find_all()) == 16
        body = canvas.find_all()[8]
        assert canvas.itemcget(body, "outline") == "#42bdf4"
    finally:
        root.destroy()
