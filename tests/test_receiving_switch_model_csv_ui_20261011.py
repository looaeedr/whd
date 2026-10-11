# -*- coding: utf-8 -*-
"""The inner-door list uses CSV names and the existing connected Bay highlighter."""
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays
from ae_engine.receiving_shared_settings import edit_setting, setting_value
from gui_modules.application import receiving_multi_settings_window as ui
from ae_engine.receiving_switch_model_catalog import model_filenames


def test_inner_door_list_no_extension_and_apply_to_highlighted_bays(monkeypatch, tmp_path):
    header = "圖塊名稱,士林,深,東元,深,伍菱,深\n"
    index_file = tmp_path / "開關索引.csv"
    index_file.write_text(
        header + "a,A1.dxf,,B1.dxf,,C1.dxf,\n"
        + "b,A1.dxf,,B1.dxf,,C1.dxf,\n", encoding="utf-8-sig",
    )
    monkeypatch.setattr(ui, "INDEX_PATH", index_file)
    monkeypatch.setattr(
        ui, "model_filenames",
        lambda brand: model_filenames(brand, path=index_file),
    )
    root = tk.Tk()
    root.withdraw()
    state = {
        "layout": resize_receiving_bays(
            new_receiving_layout(width=800, height=1600, depth=350),
            set_index=0, bay_count=2,
        ),
        "selected": 0, "calls": [],
    }

    def ports(_set_index):
        def change(kind, value, indices=()):
            state["calls"].append((kind, tuple(indices)))
            for index in indices or (state["selected"],):
                state["layout"] = edit_setting(
                    state["layout"], set_index=0, bay_index=index,
                    kind=kind, value=value,
                )
        return {
            "row": lambda: state["layout"]["sets"][0],
            "select": lambda bay: state.__setitem__("selected", bay),
            "change": change,
        }

    try:
        win = ui.open_multi_settings(
            root,
            get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (2,)),
            switch_mode=lambda _target: True,
            resize_connections=lambda *_args: False,
            get_settings_ports=ports,
            get_brand=lambda: "士林",
            select_bay=lambda _si, bi: state.__setitem__("selected", bi),
        )
        root.update()
        assert win._receiving_multi_apply(0)
        selector = win._receiving_multi_setting_list
        selector.selection_set(1)
        selector.event_generate("<<ListboxSelect>>")
        root.update()

        host = win._receiving_multi_settings_host
        # The first/main operator page must not expose switch model selection.
        texts = [
            child.cget("text")
            for widget in host.winfo_children()
            for child in widget.winfo_children()
            if isinstance(child, (ttk.Button, ttk.Label))
        ]
        assert "連動選取的連" not in texts
        assert "解除本連連動" not in texts
        assert "套用開關型號" not in texts
        assert not hasattr(win, "_receiving_multi_inner_model_state")
        assert not any(isinstance(child, tk.Listbox)
                       for child in host.winfo_children())

        hitbox = win._receiving_multi_canvas._receiving_bay_hitboxes[1]
        x0, y0, x1, y1 = hitbox
        win._receiving_multi_canvas.event_generate(
            "<Button-1>", x=(x0+x1)//2, y=(y0+y1)//2,
        )
        root.update()
        assert win._receiving_multi_applied["selected_bays"] == (0, 1)
        layer_row = host.winfo_children()[0]
        assert not any(isinstance(child, ttk.Button)
                       and child.cget("text") == "編輯"
                       for child in layer_row.winfo_children())
        layers = next(child for child in layer_row.winfo_children()
                      if isinstance(child, ttk.Combobox))
        layers.set("2")
        layers.event_generate("<<ComboboxSelected>>")
        root.update()
        assert state["calls"][-1] == ("inner_door_layers", (0, 1))
        for bay_index in (0, 1):
            assert setting_value(
                state["layout"]["sets"][0], bay_index, "inner_door_layers"
            ) == 2

        win._receiving_multi_close()
    finally:
        root.destroy()
