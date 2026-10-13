# -*- coding: utf-8 -*-
"""Data-accurate inner-door previews: real Set/Bay vs selected candidate."""
from types import SimpleNamespace
import tkinter as tk
from tkinter import ttk

import pytest

from ae_engine.receiving_inner_door_candidates import (
    create_inner_candidate, inner_versions,
)
from ae_engine.receiving_layout import new_receiving_layout
from ae_engine.receiving_shared_settings import edit_setting, setting_value
from gui_modules.application.receiving_inner_door_thumbnail import (
    inner_door_preview_rows, paint_inner_door_thumbnail,
)
from gui_modules.application.receiving_multi_settings_window import open_multi_settings


def test_preview_inventory_rows_retain_duplicate_instances_and_legacy_values():
    source = {
        "layers": 2,
        "models": [["A.dxf", "A.dxf", "B.dxf"], "C.dxf"],
    }
    assert inner_door_preview_rows(source) == (
        ("A.dxf", "A.dxf", "B.dxf"), ("C.dxf",),
    )
    assert inner_door_preview_rows({"layers": 1, "models": ["", ""]}) == ((),)
    assert inner_door_preview_rows(None) == ()
    with pytest.raises(ValueError):
        inner_door_preview_rows({"layers": 3, "models": ["A.dxf", ""]})


def test_canvas_thumbnail_displays_layers_quantities_and_no_dxf_or_made_up_positions():
    root = tk.Tk()
    root.withdraw()
    try:
        canvas = tk.Canvas(root, width=256, height=158)
        canvas.pack()
        data = {"layers": 2, "models": [
            ["BH_25X95.dxf", "BH_25X95.dxf", "100_75X130_68.dxf"],
            ["LEAKAGE_75X130.dxf"],
        ]}
        result = paint_inner_door_thumbnail(canvas, data, title="候選：版本二")
        assert result == (
            ("BH_25X95.dxf", "BH_25X95.dxf", "100_75X130_68.dxf"),
            ("LEAKAGE_75X130.dxf",),
        )
        texts = [canvas.itemcget(item, "text") for item in canvas.find_all()
                 if canvas.type(item) == "text"]
        assert "候選：版本二" in texts
        assert "第 1 層  ·  3 顆" in texts
        assert "第 2 層  ·  1 顆" in texts
        assert any("BH_25X95×2" in part for part in texts)
        assert not any(".dxf" in part.lower() for part in texts)
        assert "配置示意，非實際開孔位置" in texts
        assert paint_inner_door_thumbnail(canvas, None) == ()
        texts = [canvas.itemcget(item, "text") for item in canvas.find_all()
                 if canvas.type(item) == "text"]
        assert "尚未選擇候選版本" in texts
        assert len(canvas.find_all()) < 10  # No stale glyphs left from former render
    finally:
        root.destroy()


def test_first_page_layer_then_version_and_distinct_applied_candidate_thumbnails():
    root = tk.Tk()
    root.withdraw()
    library, version_id = create_inner_candidate(None, {
        "layers": 2,
        "models": [["A.dxf", "A.dxf"], ["B.dxf"]],
    })
    state = {"layout": new_receiving_layout(width=800, height=1600, depth=350)}
    selected = {"bay": 0}
    events = []

    def ports(_si):
        def change(kind, value, indices=()):
            for index in indices or (selected["bay"],):
                state["layout"] = edit_setting(
                    state["layout"], set_index=0, bay_index=index,
                    kind=kind, value=value,
                )
        return {
            "row": lambda: state["layout"]["sets"][0],
            "select": lambda index: selected.__setitem__("bay", index),
            "change": change,
        }

    def candidate_ports():
        def apply(role, version, set_index, bays):
            assert role == "inner-door" and version == version_id
            assert set_index == 0 and tuple(bays) == (0,)
            config = inner_versions(library)[0]["config"]
            for bay in bays:
                for kind, field in (("inner_door_layers", "layers"),
                                    ("inner_door_models", "models")):
                    state["layout"] = edit_setting(
                        state["layout"], set_index=set_index, bay_index=bay,
                        kind=kind, value=config[field],
                    )
            events.append("applied")
        return {
            "versions": lambda _role: inner_versions(library),
            "apply": apply,
            "edit": lambda *_args: None,
        }

    try:
        win = open_multi_settings(
            root,
            get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (1,)),
            switch_mode=lambda _mode: True,
            resize_connections=lambda *_args: False,
            get_settings_ports=ports,
            get_inner_candidate_ports=candidate_ports,
        )
        root.update()
        assert win._receiving_multi_apply(0)
        listing = win._receiving_multi_setting_list
        listing.selection_set(1)
        listing.event_generate("<<ListboxSelect>>")
        root.update()
        host = win._receiving_multi_settings_host
        rows = host.winfo_children()
        assert any(isinstance(w, ttk.Label) and w.cget("text") == "內門層數"
                   for w in rows[0].winfo_children())
        assert not any(isinstance(w, ttk.Button) and w.cget("text") == "編輯"
                       for w in rows[0].winfo_children())
        assert any(isinstance(w, ttk.Label) and w.cget("text") == "內門版本"
                   for w in rows[1].winfo_children())
        assert sum(1 for widget in rows[1].winfo_children()
                   if isinstance(widget, ttk.Button) and widget.cget("text") == "編輯") == 1

        # The formerly embedded thumbnail comparison has been retired.
        assert win._receiving_multi_real_preview["win"] is None
        assert not any(
            isinstance(w, tk.Canvas) for w in host.winfo_children()
        )
        chooser = win._receiving_multi_candidate_combos["inner-door"]
        chooser.set("版本一")
        chooser.event_generate("<<ComboboxSelected>>")
        root.update()
        assert win._receiving_multi_candidate_selected["inner-door"] == version_id
        assert state["layout"]["sets"][0] == state["layout"]["sets"][0]

        apply_button = next(w for w in rows[1].winfo_children()
                            if isinstance(w, ttk.Button) and w.cget("text") == "套用")
        apply_button.invoke()
        root.update()
        assert events == ["applied"]
        assert setting_value(
            state["layout"]["sets"][0], 0, "inner_door_models",
        ) == [["A.dxf", "A.dxf"], "B.dxf"]
        win._receiving_multi_close()
    finally:
        root.destroy()
