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

        models = win._receiving_multi_inner_model_state["listbox"]
        assert isinstance(models, tk.Listbox)
        assert models.get(0, tk.END) == ("A1",)  # case-preserving first unique
        hitbox = win._receiving_multi_canvas._receiving_bay_hitboxes[1]
        x0, y0, x1, y1 = hitbox
        win._receiving_multi_canvas.event_generate(
            "<Button-1>", x=(x0+x1)//2, y=(y0+y1)//2,
        )
        root.update()
        assert win._receiving_multi_applied["selected_bays"] == (0, 1)

        models = win._receiving_multi_inner_model_state["listbox"]
        models.selection_set(0)
        apply_button = next(
            child for child in win._receiving_multi_settings_host.winfo_children()
            if isinstance(child, ttk.Button)
            and child.cget("text") == "套用開關型號"
        )
        apply_button.invoke()
        root.update()
        assert state["calls"][-1] == ("inner_door_models", (0, 1))
        for bay_index in (0, 1):
            assert setting_value(
                state["layout"]["sets"][0], bay_index, "inner_door_models",
            ) == ["A1.dxf", ""]

        # The exact same CSV is re-read after an operator saves a changed file.
        index_file.write_text(
            header + "a,NEW_MODEL.dxf,,B1.dxf,,C1.dxf,\n",
            encoding="utf-8-sig",
        )
        win._receiving_multi_refresh_switch_models(force=True)
        assert win._receiving_multi_inner_model_state["listbox"].get(
            0, tk.END,
        ) == ("NEW_MODEL",)
        assert "已不在 CSV" in win._receiving_multi_inner_model_state["status"].get()
        # Source change never overwrites the previous saved selection.
        assert setting_value(
            state["layout"]["sets"][0], 0, "inner_door_models",
        ) == ["A1.dxf", ""]
        win._receiving_multi_close()
    finally:
        root.destroy()
