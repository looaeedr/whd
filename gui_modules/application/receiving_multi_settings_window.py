"""One temporary operator surface for all Receiving multi-box functions.

The UI groups Set/Bay and quantity-version affordances under one Assembly
entry. Switching sections reuses ReceivingModeSession; it never merges their
distinct manufacturing state or creates a second quantity controller.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from ae_engine.cabinet_types.receiving import BOX_BODY_DEFAULTS
from .receiving_set_bay_controls import (
    build_receiving_set_bay_controls, refresh_receiving_layer_rows,
)
from .quantity_version_controls import build_quantity_controls


def display_dimension(value):
    """Operator integer display, without modifying older fractional CAD data."""
    number = float(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


def default_preview_dimensions(snapshot):
    """One representative cabinet only; no manufacturing/FinalScene solve."""
    data = dict(snapshot or {})
    if data.get("active_mode") == "quantity":
        box = data.get("receiving_quantity_box") or BOX_BODY_DEFAULTS
    else:
        layout = data.get("receiving_layout") or {}
        sets = layout.get("sets") or ()
        bays = sets[0].get("bays", ()) if sets else ()
        box = ({ "w": bays[0]["width"], "h": bays[0]["height"],
                 "d": bays[0]["depth"] } if bays else BOX_BODY_DEFAULTS)
    return tuple(float(box[axis]) for axis in ("w", "h", "d"))


def paint_one_cabinet(canvas, dimensions):
    """Very small non-manufacturing front outline for immediate first paint."""
    w, h, d = dimensions
    canvas.delete("all")
    width, height = 320, 235
    scale = min(240 / max(w, 1), 175 / max(h, 1))
    bw, bh = w * scale, h * scale
    x, y = (width - bw) / 2, (height - bh) / 2 - 12
    canvas.create_rectangle(x, y, x + bw, y + bh,
                            outline="#90b9dc", width=2, fill="#263a4d")
    canvas.create_line(x + 5, y + 5, x + bw - 5, y + 5, fill="#7b9bb5")
    canvas.create_text(width / 2, 219,
        text=f"示意單只  {display_dimension(w)} × {display_dimension(h)} × {display_dimension(d)}",
        fill="#c5d4e0", font=("TkDefaultFont", 10))
    return 1


def open_multi_settings(parent, *, get_snapshot, get_switch, switch_mode,
                        set_brand, add_set, remove_set, resize_connections,
                        open_set_settings, quantity_ports):
    """Open/reuse the lightweight dialog. All actions route to existing owners."""
    old = getattr(parent, "_receiving_multi_settings_window", None)
    if old is not None and old.winfo_exists():
        old.lift()
        old.focus_set()
        return old
    win = tk.Toplevel(parent)
    win.title("多只設定")
    win.geometry("770x670")
    win.minsize(610, 470)
    parent._receiving_multi_settings_window = win

    ttk.Label(win, text="多只設定", font=("TkDefaultFont", 13, "bold")).pack(
        anchor=tk.W, padx=12, pady=(12, 4))
    ttk.Label(win, text="所有功能暫放於此入口；套／連及孔型版本資料仍各自保存。").pack(
        anchor=tk.W, padx=12, pady=(0, 6))
    content = ttk.Frame(win, padding=(12, 0, 12, 0))
    content.pack(fill=tk.BOTH, expand=True)
    left = ttk.Frame(content)
    left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    right = ttk.LabelFrame(content, text="單只簡易預覽", padding=6)
    right.pack(side=tk.RIGHT, anchor=tk.N, padx=(12, 0))
    preview = tk.Canvas(right, width=320, height=235, highlightthickness=0,
                        background="#1a2734")
    preview.pack()
    paint_one_cabinet(preview, default_preview_dimensions(get_snapshot()))

    notebook = ttk.Notebook(left)
    notebook.pack(fill=tk.BOTH, expand=True)
    suites = ttk.Frame(notebook, padding=4)
    versions = ttk.Frame(notebook, padding=4)
    notebook.add(suites, text="套／連設定")
    notebook.add(versions, text="孔型版本／件數")

    def guarded(action):
        try:
            result = action()
            refresh()
            return result
        except (ValueError, IndexError, RuntimeError) as exc:
            messagebox.showwarning("多只設定未完成", str(exc), parent=win)
            return False

    controls = build_receiving_set_bay_controls(
        suites, tk=tk, ttk=ttk,
        on_switch_brand_selected=lambda brand: guarded(lambda: set_brand(brand)),
        on_add_layer=lambda: guarded(add_set),
        on_remove_layer=lambda: guarded(remove_set),
    )
    controls.frame.pack(fill=tk.X)

    quantity = build_quantity_controls(versions, quantity_ports)
    quantity.frame.pack(fill=tk.X)
    common = ttk.Button(versions, text="共用箱體設定",
                        command=lambda: guarded(quantity_ports["common"]))
    common.pack(anchor=tk.W, pady=6)

    def refresh():
        if not win.winfo_exists():
            return
        snapshot = get_snapshot()
        paint_one_cabinet(preview, default_preview_dimensions(snapshot))
        if snapshot.get("active_mode", "set_bay") == "set_bay":
            switch = get_switch()
            controls.switch_brand_var.set(switch.brand)
            refresh_receiving_layer_rows(
                controls, tk=tk, ttk=ttk,
                connection_counts=switch.connection_counts(),
                on_resize_connections=lambda i, delta: guarded(
                    lambda: resize_connections(i, delta)),
                on_preview=lambda i: guarded(lambda: open_set_settings(i)),
            )
        else:
            quantity.frame.pack(fill=tk.X)
            quantity.refresh()
    def changed(_event=None):
        wanted = ("set_bay" if notebook.index(notebook.select()) == 0
                  else "quantity")
        if get_snapshot().get("active_mode", "set_bay") != wanted:
            if not switch_mode(wanted):
                notebook.select(0 if wanted == "quantity" else 1)
                return
        refresh()
    notebook.bind("<<NotebookTabChanged>>", changed)
    current_mode = get_snapshot().get("active_mode", "set_bay")
    if current_mode == "quantity":
        notebook.select(1)
    refresh()
    win._receiving_multi_notebook = notebook
    win._receiving_multi_preview = preview
    win._receiving_multi_controls = controls
    win._receiving_multi_quantity = quantity
    win._receiving_multi_refresh = refresh
    ttk.Button(win, text="關閉", command=win.destroy).pack(
        anchor=tk.E, padx=12, pady=8)
    return win
