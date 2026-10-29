# -*- coding: utf-8 -*-
"""Legacy multi-Bay GUI must not resurrect the retired CSV or tier editor.

CSV V5 NFB identity and the physical layer count are edited in the one
original NFB editor. Multi-Bay only highlights target bays and links saved
inner-door candidate versions. This is a real Tk presentation contract.
"""
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

from ae_engine.receiving_layout import new_receiving_layout, resize_receiving_bays
from ae_engine.receiving_shared_settings import setting_value
from gui_modules.application import receiving_multi_settings_window as ui


def test_inner_door_list_no_extension_and_apply_to_highlighted_bays():
    root = tk.Tk()
    root.geometry("900x650+0+0")
    root.update_idletasks()
    root.update()
    state = {
        "layout": resize_receiving_bays(
            new_receiving_layout(width=800, height=1600, depth=350),
            set_index=0, bay_count=2,
        ),
        "selected": 0, "calls": [],
    }

    def ports(_set_index):
        def forbidden_layer_write(*args, **kwargs):
            # This panel no longer owns writable inner-door/NFB layers.
            state["calls"].append((args, kwargs))
            raise AssertionError("Retired multi-Bay layer entry was invoked")
        return {
            "row": lambda: state["layout"]["sets"][0],
            "select": lambda bay: state.__setitem__("selected", bay),
            "change": forbidden_layer_write,
        }

    win = None
    try:
        win = ui.open_multi_settings(
            root,
            get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (2,)),
            switch_mode=lambda _target: True,
            resize_connections=lambda *_args: False,
            get_settings_ports=ports,
            select_bay=lambda _si, bi: state.__setitem__("selected", bi),
        )
        root.update()
        assert win._receiving_multi_apply(0)

        selector = win._receiving_multi_setting_list
        selector.selection_set(1)
        selector.event_generate("<<ListboxSelect>>")
        root.update()
        assert tuple(selector.get(0, tk.END)) == ("封頭尾", "內門")

        host = win._receiving_multi_settings_host
        def visible_buttons(widget):
            result = []
            for child in widget.winfo_children():
                if isinstance(child, ttk.Button) and child.winfo_ismapped():
                    result.append(str(child.cget("text")))
                result.extend(visible_buttons(child))
            return result
        buttons = visible_buttons(host)
        assert "編輯" in buttons and "套用" in buttons
        assert "連動選取的連" not in buttons
        assert "解除本連連動" not in buttons
        assert "套用開關型號" not in buttons
        assert not any("NFB" in text or "DXF" in text for text in buttons)
        assert not hasattr(win, "_receiving_multi_inner_model_state")
        assert not any(isinstance(child, tk.Listbox)
                       for child in host.winfo_children())

        # The visible diagram selects two target bays; it does not mutate
        # either bay's NFB model or physical tier count.
        before = tuple(setting_value(state["layout"]["sets"][0], i,
                                     "inner_door_layers") for i in range(2))
        canvas = win._receiving_multi_canvas
        x0, y0, x1, y1 = canvas._receiving_bay_hitboxes[1]
        canvas.event_generate("<Button-1>",
                              x=int((x0 + x1)/2), y=int((y0 + y1)/2))
        root.update()
        assert win._receiving_multi_applied["selected_bays"] == (0, 1)
        after = tuple(setting_value(state["layout"]["sets"][0], i,
                                    "inner_door_layers") for i in range(2))
        assert after == before
        assert state["calls"] == []
    finally:
        if win is not None and win.winfo_exists():
            win._receiving_multi_close()
        root.destroy()
