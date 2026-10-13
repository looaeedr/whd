"""Receiving 内門 action regression: reuse canonical highlighted Bay operations."""
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

from gui_modules.application.receiving_multi_settings_window import open_multi_settings


def test_inner_door_existing_highlight_auto_edit_share_and_unlink():
    root = tk.Tk()
    root.withdraw()
    calls = []
    selected = {"index": 0}
    bays = [{"inner_door_layers": 1}, {"inner_door_layers": 1}]

    def ports(_set_index):
        return {
            "row": lambda: {"bays": bays},
            "select": lambda bay: selected.__setitem__("index", bay),
            "change": lambda kind, value, targets=(): (
                calls.append(("change", kind, value, tuple(targets)))
            ),
            "share": lambda kind, targets: calls.append(
                ("share", kind, tuple(targets))
            ),
            "unlink": lambda kind: calls.append(
                ("unlink", kind, selected["index"])
            ),
        }

    try:
        win = open_multi_settings(
            root,
            get_snapshot=lambda: {"active_mode": "set_bay"},
            get_switch=lambda: SimpleNamespace(connection_counts=lambda: (2,)),
            switch_mode=lambda _mode: True,
            resize_connections=lambda *_args: False,
            get_settings_ports=ports,
        )
        root.update()
        assert win._receiving_multi_apply(0)
        listing = win._receiving_multi_setting_list
        listing.selection_set(1)
        listing.event_generate("<<ListboxSelect>>")
        root.update()

        host = win._receiving_multi_settings_host
        assert tuple(listing.get(0, tk.END)) == ("封頭尾", "內門")
        assert win._receiving_multi_function_host is listing.master
        labels = {
            child.cget("text") for row in host.winfo_children()
            for child in row.winfo_children()
            if isinstance(child, ttk.Button)
        }
        assert labels == {"連動選取的連", "解除本連連動"}

        canvas = win._receiving_multi_canvas
        x0, y0, x1, y1 = canvas._receiving_bay_hitboxes[1]
        canvas.event_generate("<Button-1>", x=int((x0 + x1) / 2),
                              y=int((y0 + y1) / 2))
        root.update()
        assert win._receiving_multi_applied["selected_bays"] == (0, 1)

        def button(label):
            return next(child for row in host.winfo_children()
                        for child in row.winfo_children()
                        if isinstance(child, ttk.Button)
                        and child.cget("text") == label)

        editor = host.winfo_children()[0]
        value = next(child for child in editor.winfo_children()
                     if isinstance(child, ttk.Combobox))
        value.set("2")
        value.event_generate("<<ComboboxSelected>>")
        root.update()
        assert calls[-1] == ("change", "inner_door_layers", 2, (0, 1))
        button("連動選取的連").invoke()
        root.update()
        assert calls[-1] == ("share", "inner_door_layers", (0, 1))
        button("解除本連連動").invoke()
        root.update()
        assert calls[-1][:2] == ("unlink", "inner_door_layers")
        win._receiving_multi_close()
    finally:
        root.destroy()
