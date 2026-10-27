"""Receiving inner-door GUI: the 2D highlight is the only apply target.

The obsolete "連動選取的連" and unlink controls must not be restored.
"""
import tkinter as tk
from tkinter import ttk
from types import SimpleNamespace

from gui_modules.application.receiving_multi_settings_window import open_multi_settings


def test_inner_door_highlight_does_not_render_or_call_retired_link_actions():
    root = tk.Tk()
    root.withdraw()
    calls = []
    row = {"bays": [{"inner_door_layers": 1}, {"inner_door_layers": 1}]}
    def ports(_set_index):
        return {
            "row": lambda: row,
            "select": lambda bay: calls.append(("select", bay)),
            "share": lambda kind, targets: calls.append(("share", kind, targets)),
            "unlink": lambda kind: calls.append(("unlink", kind)),
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
        assert tuple(listing.get(0, tk.END)) == ("封頭尾", "內門")

        canvas = win._receiving_multi_canvas
        x0, y0, x1, y1 = canvas._receiving_bay_hitboxes[1]
        canvas.event_generate(
            "<Button-1>", x=int((x0 + x1) / 2), y=int((y0 + y1) / 2),
        )
        root.update()
        assert win._receiving_multi_applied["selected_bays"] == (0, 1)

        def all_button_labels(widget):
            labels = []
            for child in widget.winfo_children():
                if isinstance(child, ttk.Button):
                    labels.append(child.cget("text"))
                labels.extend(all_button_labels(child))
            return labels

        labels = all_button_labels(win._receiving_multi_settings_host)
        assert "連動選取的連" not in labels
        assert "解除本連連動" not in labels
        assert not any(call[0] in {"share", "unlink"} for call in calls)
        win._receiving_multi_close()
    finally:
        root.destroy()
