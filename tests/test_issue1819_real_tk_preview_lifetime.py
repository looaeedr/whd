"""#1819: a disposed real Tk 2D preview must not retain prior Figure/canvas.

This isolates the lifecycle of the preview widget; it is not a proxy for all
native allocator RSS or a claim that complete WHD GUI memory has plateaued.
"""
import gc
import weakref
import tkinter as tk
from tkinter import ttk

from gui_modules.application.receiving_settings_preview_2d import ReceivingSettingsPreview2D


def test_issue1819_closed_real_preview_reclaims_figure_canvas_and_widget_refs():
    root = tk.Tk()
    root.geometry("1000x800+0+0")
    refs = []
    try:
        root.update_idletasks()
        for _ in range(8):
            popup = tk.Toplevel(root)
            host = ttk.Frame(popup)
            host.pack(fill=tk.BOTH, expand=True)
            view = ReceivingSettingsPreview2D(
                host, tk=tk, ttk=ttk, requests=(),
            )
            root.update_idletasks()
            refs.append({
                "view": weakref.ref(view),
                "figure": weakref.ref(view.figure),
                "canvas": weakref.ref(view.canvas),
            })
            popup.destroy()
            del view, host, popup
            root.update_idletasks()
            gc.collect()
        still_alive = [
            (index, key)
            for index, item in enumerate(refs)
            for key, ref in item.items() if ref() is not None
        ]
        assert still_alive == [], (
            "Closed Tk previews still retain old Python objects: "
            + repr(still_alive)
        )
        assert not root.winfo_children()
    finally:
        root.destroy()
