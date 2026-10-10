"""Minimal Receiving multi-box UI. All other product owners remain intact.

Only two operator mode choices, one row per existing Set with +/− Bay and
Apply, and a lightweight lower-right connected 2D diagram are shown.
No hidden geometry solve, nested editor, preview popup or extra controls.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from ae_engine.cabinet_types.receiving import BOX_BODY_DEFAULTS, default_door_layout_columns


def display_dimension(value):
    number = float(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


def default_preview_dimensions(snapshot):
    data = dict(snapshot or {})
    if data.get("active_mode") == "quantity":
        box = data.get("receiving_quantity_box") or BOX_BODY_DEFAULTS
    else:
        sets = (data.get("receiving_layout") or {}).get("sets") or ()
        bays = sets[0].get("bays") or () if sets else ()
        box = ({"w": bays[0]["width"], "h": bays[0]["height"],
                "d": bays[0]["depth"]} if bays else BOX_BODY_DEFAULTS)
    return tuple(float(box[axis]) for axis in ("w", "h", "d"))


def paint_connected_bays(canvas, count, selected=None):
    """Cheap front-elevation sketch: touching bays with basic upper/lower doors.

    Selection is a pure presentation overlay. No FinalScene, manufacturing or
    DXF code may run during sketch creation.
    """
    count = max(1, int(count))
    canvas.delete("all")
    canvas._receiving_bay_hitboxes = ()
    canvas._receiving_selected_bay = selected
    width = max(int(canvas.winfo_width()), int(canvas.cget("width")))
    height = max(int(canvas.winfo_height()), int(canvas.cget("height")))
    usable_w = max(40, width - 24)
    usable_h = max(50, height - 24)
    bay_w = min(usable_w / count, usable_h * 0.5)
    bay_h = min(usable_h, bay_w * 2.0)
    left = (width - bay_w * count) / 2
    top = (height - bay_h) / 2
    split = top + bay_h * 1100.0 / 1600.0
    hitboxes = []
    for index in range(count):
        x0, x1 = left + index * bay_w, left + (index + 1) * bay_w
        active = index == selected
        outline = "#42bdf4" if active else "#8faec4"
        fill = "#315775" if active else "#263a4d"
        canvas.create_rectangle(x0, top, x1, top + bay_h,
                                fill=fill, outline=outline,
                                width=3 if active else 1)
        inset = min(7.0, max(2.0, bay_w * 0.07))
        canvas.create_rectangle(x0 + inset, top + inset, x1 - inset, split - 2,
                                outline="#c3d1dc", width=1)
        canvas.create_rectangle(x0 + inset, split + 2, x1 - inset,
                                top + bay_h - inset, outline="#c3d1dc", width=1)
        canvas.create_line(x0 + inset, split, x1 - inset, split,
                           fill="#e0c487", width=1)
        hitboxes.append((x0, top, x1, top + bay_h))
    canvas._receiving_bay_hitboxes = tuple(hitboxes)
    return count


def paint_one_cabinet(canvas, dimensions, door_columns=None):
    """Compatibility sketch helper (not a separate operator preview window)."""
    return paint_connected_bays(canvas, 1)


def open_multi_settings(parent, *, get_snapshot, get_switch, switch_mode,
                        resize_connections, select_bay=None):
    """Full-screen modal Receiving operator UI with no unsolicited widgets."""
    old = getattr(parent, "_receiving_multi_settings_window", None)
    if old is not None and old.winfo_exists():
        old.lift()
        old.focus_set()
        return old

    win = tk.Toplevel(parent)
    win.title("多只設定")
    win.transient(parent)
    parent._receiving_multi_settings_window = win

    def close():
        if win.grab_current() is win:
            win.grab_release()
        parent._receiving_multi_settings_window = None
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", close)
    win._receiving_multi_close = close

    # Maximize without hiding the native close affordance. Linux and Windows
    # Tk window managers expose different window state capabilities.
    def maximize_and_lock():
        if not win.winfo_exists():
            return
        win.geometry(
            f"{win.winfo_screenwidth()}x{win.winfo_screenheight()}+0+0"
        )
        try:
            win.state("zoomed")
        except tk.TclError:
            try:
                win.attributes("-zoomed", True)
            except tk.TclError:
                win.geometry(
                    f"{win.winfo_screenwidth()}x{win.winfo_screenheight()}+0+0"
                )
        if win.winfo_viewable():
            win.grab_set()
            win.focus_set()

    win.after_idle(maximize_and_lock)
    win.columnconfigure(1, weight=1)
    win.rowconfigure(1, weight=1)

    mode_var = tk.StringVar(master=win, value="set_bay")
    mode_row = ttk.Frame(win)
    mode_row.grid(row=0, column=0, columnspan=2, sticky="nw",
                  padx=16, pady=(16, 6))

    applied = {"set_index": None, "count": 1, "selected": None, "mode": "set_bay"}

    canvas = tk.Canvas(win, width=525, height=310, background="#1a2734",
                       highlightthickness=0)
    canvas.grid(row=1, column=1, sticky="se", padx=24, pady=12)

    rows_host = ttk.Frame(win)
    # The Set/Bay row belongs directly BELOW the two upper-left mode
    # choices; only the 2D canvas is anchored to the lower-right corner.
    rows_host.grid(row=1, column=0, sticky="nw",
                   padx=16, pady=(0, 16))

    def warn(exc):
        messagebox.showwarning("多只設定", str(exc), parent=win)
        return False

    def ensure_set_mode():
        if get_snapshot().get("active_mode", "set_bay") != "set_bay":
            if not switch_mode("set_bay"):
                return False
        return True

    def render():
        count = applied["count"] if applied["mode"] == "set_bay" else 1
        selected = applied["selected"] if applied["mode"] == "set_bay" else None
        paint_connected_bays(canvas, count, selected)

    def refresh_rows():
        for widget in rows_host.winfo_children():
            widget.destroy()
        if mode_var.get() != "set_bay":
            return
        for index, raw_count in enumerate(tuple(get_switch().connection_counts())):
            count = max(1, int(raw_count))
            row = ttk.Frame(rows_host)
            row.pack(anchor="w", pady=2)
            ttk.Label(row, text=f"第{index + 1}套").pack(side="left", padx=(0, 10))
            ttk.Button(row, text="＋連", command=lambda i=index: resize(i, 1)).pack(
                side="left", padx=(0, 3))
            # Keep the actual connection count between +連 and -連. The row
            # is rebuilt from the canonical Switch owner after each edit.
            ttk.Label(row, text=str(count), width=3, anchor="center").pack(
                side="left", padx=(0, 3))
            ttk.Button(row, text="－連", command=lambda i=index: resize(i, -1)).pack(
                side="left", padx=(0, 3))
            ttk.Button(row, text="套用", command=lambda i=index: apply(i)).pack(
                side="left")

    def resize(index, delta):
        try:
            if not ensure_set_mode():
                return False
            result = resize_connections(index, delta)
            refresh_rows()
            # Intentionally do not redraw: only 套用 projects the current
            # number of bays into the 2D diagram.
            return result
        except (ValueError, IndexError, RuntimeError) as exc:
            return warn(exc)

    def apply(index):
        try:
            if not ensure_set_mode():
                return False
            counts = tuple(get_switch().connection_counts())
            count = max(1, int(counts[index]))
            applied.update(mode="set_bay", set_index=index,
                           count=count, selected=0)
            if select_bay is not None:
                select_bay(index, 0)
            render()
            return True
        except (ValueError, IndexError, RuntimeError) as exc:
            return warn(exc)

    def click_bay(event):
        if applied["mode"] != "set_bay" or applied["set_index"] is None:
            return
        for index, (x0, y0, x1, y1) in enumerate(canvas._receiving_bay_hitboxes):
            if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                try:
                    if select_bay is not None:
                        select_bay(applied["set_index"], index)
                    applied["selected"] = index
                    render()
                except (ValueError, IndexError, RuntimeError) as exc:
                    warn(exc)
                return

    def change_mode():
        target = mode_var.get()
        try:
            if get_snapshot().get("active_mode", "set_bay") != target:
                if not switch_mode(target):
                    mode_var.set(applied["mode"])
                    return
            applied["mode"] = target
            if target == "quantity":
                applied.update(set_index=None, selected=None, count=1)
            refresh_rows()
            render()
        except (ValueError, IndexError, RuntimeError) as exc:
            mode_var.set(applied["mode"])
            warn(exc)

    for text, value in (("套／連", "set_bay"), ("數量", "quantity")):
        ttk.Radiobutton(mode_row, text=text, value=value,
                        variable=mode_var, command=change_mode).pack(
                            side="left", padx=(0, 16))

    canvas.bind("<Button-1>", click_bay)
    canvas.bind("<Configure>", lambda _event: render())
    refresh_rows()
    render()

    # Test hooks are presentation state only, not product data authority.
    win._receiving_multi_mode_var = mode_var
    win._receiving_multi_mode_controls = mode_row
    win._receiving_multi_rows_host = rows_host
    win._receiving_multi_canvas = canvas
    win._receiving_multi_applied = applied
    win._receiving_multi_refresh = refresh_rows
    win._receiving_multi_apply = apply
    return win
