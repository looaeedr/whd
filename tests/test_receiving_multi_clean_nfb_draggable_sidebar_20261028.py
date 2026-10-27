# -*- coding: utf-8 -*-
"""The multi-Bay UI has one NFB editor/Apply path and a draggable left rail."""
import os
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace
import pytest
from gui_modules.application.receiving_multi_settings_window import open_multi_settings

pytestmark = pytest.mark.skipif(
    os.name != "nt" and not os.environ.get("DISPLAY"),
    reason="Real Tk/window manager required",
)

RETIRED = (
    "確認套用 NFB", "複製至其他連",
    "還原為未配置", "復原上次 NFB 操作",
    "輸出已提交內門 DXF（僅局部）",
    "輸出內門與底板 DXF（成對局部）",
)

def _all_ttk_buttons(widget):
    children = [widget]
    result = []
    while children:
        element = children.pop()
        if isinstance(element, ttk.Button):
            result.append(element)
        children.extend(element.winfo_children())
    return result


def test_native_tk_receiving_multi_sidebar_90_percent_and_draggable_and_no_visible_nfb_actions():
    root = tk.Tk()
    root.geometry("900x650")
    root.update()
    source = {"active_mode": "set_bay"}
    receiving = SimpleNamespace(
        connection_counts=lambda: (5,),
        layout={"sets":[{"bays":[{"width":800, "height":1600, "depth":350}
                                 for _ in range(5)]}]},
    )
    def settings(_set_index):
        return {
            "select":lambda _bi:None,
            "row":lambda:{"bays":[{"stable_id":f"bay-{i}"} for i in range(5)]},
        }
    win = None
    try:
        win = open_multi_settings(
            root, get_snapshot=lambda:source,
            get_switch=lambda:receiving,
            switch_mode=lambda _m:True,
            resize_connections=lambda *_a:True,
            get_settings_ports=settings,
            get_nfb_transaction_ports=lambda:{
                "state":lambda *_:{"can_submit":True},
                "manifest":lambda *_:{"status":"LEGACY"},
            },
            get_inner_candidate_ports=lambda:{
                "versions":lambda _:[],
                "apply_live":lambda *_:None,
            },
        )
        root.update()
        pane = win._receiving_multi_splitter
        baseline = pane._receiving_default_left_width
        initial = pane._receiving_initial_left_width
        assert baseline >= 200
        assert initial == round(baseline*0.90)
        assert pane.sashpos(0) == initial
        assert win._receiving_multi_apply(0)
        setting = win._receiving_multi_setting_list
        setting.selection_clear(0,tk.END)
        setting.selection_set(1)
        setting.event_generate("<<ListboxSelect>>")
        root.update()
        buttons = _all_ttk_buttons(win._receiving_multi_settings_host)
        visible = [b.cget("text") for b in buttons if b.winfo_ismapped()]
        assert "編輯" in visible and "套用" in visible
        assert not (set(RETIRED) & set(visible)), visible
        assert all("NFB" not in label and "DXF" not in label
                   for label in visible), visible
        assert len(win._receiving_multi_canvas._receiving_bay_hitboxes)==5
        pane.sashpos(0, initial+75)
        root.update()
        moved = pane.sashpos(0)
        assert moved >= initial+40
        setting.selection_clear(0,tk.END)
        setting.selection_set(0)
        setting.event_generate("<<ListboxSelect>>")
        root.update()
        assert pane.sashpos(0) == moved
        win._receiving_multi_close()
        root.update()
        assert not win.winfo_exists()
    finally:
        if win is not None and win.winfo_exists():
            win._receiving_multi_close()
        root.destroy()
