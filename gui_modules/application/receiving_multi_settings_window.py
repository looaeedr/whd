"""Receiving multi-settings: one modal operator surface, no preview popups.

A selected set's existing editor is embedded in this window. The simple cabinet
sketch is presentation only; never a manufacturing/FinalScene request.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from ae_engine.cabinet_types.receiving import BOX_BODY_DEFAULTS, default_door_layout_columns
from .receiving_set_bay_controls import (
    _build_receiving_settings_editor,
    build_receiving_set_bay_controls,
    refresh_receiving_layer_rows,
)
from .quantity_version_controls import build_quantity_controls


def display_dimension(value):
    number = float(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


def default_preview_dimensions(snapshot):
    data = dict(snapshot or {})
    if data.get("active_mode") == "quantity":
        box = data.get("receiving_quantity_box") or BOX_BODY_DEFAULTS
    else:
        layout = data.get("receiving_layout") or {}
        sets = layout.get("sets") or ()
        bays = sets[0].get("bays", ()) if sets else ()
        box = ({"w": bays[0]["width"], "h": bays[0]["height"],
                "d": bays[0]["depth"]} if bays else BOX_BODY_DEFAULTS)
    return tuple(float(box[axis]) for axis in ("w", "h", "d"))


def paint_one_cabinet(canvas, dimensions, door_columns=None):
    """Draw one coarse front elevation with *both* upper and lower doors."""
    w, h, d = (max(1.0, float(value)) for value in dimensions)
    canvas.delete("all")
    width, height = 340, 285
    scale = min(260 / w, 214 / h)
    bw, bh = w * scale, h * scale
    x, y = (width - bw) / 2, 12 + (215 - bh) / 2
    canvas.create_rectangle(x, y, x + bw, y + bh,
                            outline="#90b9dc", width=2, fill="#263a4d")
    # Use the saved door split when present; otherwise the Family's basic
    # 1100 / 500 upper/lower layout. Never calculate production door geometry.
    columns = door_columns or default_door_layout_columns()
    try:
        upper = float(columns[0][1][0])
        if not 0 < upper < h:
            upper = h * 1100 / 1600
    except (ValueError, IndexError, TypeError, KeyError):
        upper = h * 1100 / 1600
    inset = max(3.0, min(10.0, bw / 15, bh / 15))
    split = y + bh * (upper / h)
    canvas.create_rectangle(x + inset, y + inset, x + bw - inset,
                            split - 2, outline="#a7bfd2", width=1)
    canvas.create_rectangle(x + inset, split + 2, x + bw - inset,
                            y + bh - inset, outline="#a7bfd2", width=1)
    canvas.create_line(x + inset, split, x + bw - inset, split,
                       fill="#e0c487", width=2)
    canvas.create_text(x + bw / 2, (y + split) / 2,
                       text="上門", fill="#e2edf5")
    canvas.create_text(x + bw / 2, (split + y + bh) / 2,
                       text="下門", fill="#e2edf5")
    canvas.create_text(width / 2, 266,
                       text=f"{display_dimension(w)} × {display_dimension(h)} × {display_dimension(d)}",
                       fill="#c5d4e0", font=("TkDefaultFont", 10))
    return 2


def open_multi_settings(parent, *, get_snapshot, get_switch, switch_mode,
                        set_brand, add_set, remove_set, resize_connections,
                        open_set_settings=None, quantity_ports,
                        set_editor_ports=None, common_editor_ports=None):
    """Modal editor: original set/bay/quantity owners, inline simple geometry."""
    old = getattr(parent, "_receiving_multi_settings_window", None)
    if old is not None and old.winfo_exists():
        old.lift()
        old.focus_set()
        return old
    win = tk.Toplevel(parent)
    win.title("多只設定")
    win.transient(parent)
    win.geometry("850x690")
    win.minsize(650, 500)
    parent._receiving_multi_settings_window = win

    def close():
        if win.grab_current() is win:
            win.grab_release()
        parent._receiving_multi_settings_window = None
        win.destroy()

    win.protocol("WM_DELETE_WINDOW", close)
    win._receiving_multi_close = close
    # Grab after the Toplevel is mapped; this blocks main GUI and Fold GUI.
    def enforce_modal():
        if win.winfo_exists() and win.winfo_viewable():
            win.grab_set()
            win.focus_set()
    win.after_idle(enforce_modal)

    ttk.Label(win, text="多只設定", font=("TkDefaultFont", 13, "bold")).pack(
        anchor=tk.W, padx=12, pady=(12, 4))
    notebook = ttk.Notebook(win)
    notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=8)
    suites = ttk.Frame(notebook, padding=6)
    versions = ttk.Frame(notebook, padding=6)
    notebook.add(suites, text="套／連設定")
    notebook.add(versions, text="孔型版本／件數")

    suite_editor_host = ttk.Frame(suites)
    current = {"set_index": None, "count": 0, "panel": None, "canvas": None}
    controls = build_receiving_set_bay_controls(
        suites, tk=tk, ttk=ttk,
        on_switch_brand_selected=lambda brand: guarded(lambda: set_brand(brand)),
        on_add_layer=lambda: guarded(add_set),
        on_remove_layer=lambda: guarded(remove_set),
    )
    controls.frame.pack(fill=tk.X)
    suite_editor_host.pack(fill=tk.BOTH, expand=True, pady=(8, 0))
    ttk.Label(suite_editor_host, text="選擇一套後按「套用」，在此編輯；不另開設定視窗。").pack(
        anchor=tk.W)

    quantity = build_quantity_controls(versions, quantity_ports)
    quantity.frame.pack(fill=tk.X)
    common_host = ttk.Frame(versions)
    common_host.pack(fill=tk.BOTH, expand=True, pady=8)

    def guarded(action):
        try:
            result = action()
            refresh()
            return result
        except (ValueError, IndexError, RuntimeError) as exc:
            messagebox.showwarning("多只設定未完成", str(exc), parent=win)
            return False

    def door_columns(index):
        snapshot = get_snapshot()
        if snapshot.get("active_mode") == "quantity":
            box = snapshot.get("receiving_quantity_box") or {}
            return (box.get("door_state") or {}).get("door_layout_columns")
        sets = (snapshot.get("receiving_layout") or {}).get("sets") or ()
        if index < len(sets):
            bays = sets[index].get("bays") or ()
            if bays:
                return (bays[0].get("door_state") or {}).get("door_layout_columns")
        return snapshot.get("door_layout_columns")

    def mount_editor(host, ports, *, common_box=False, set_index=0):
        for widget in host.winfo_children():
            widget.destroy()
        panel = _build_receiving_settings_editor(
            host, tk=tk, ttk=ttk, ports=ports, common_box=common_box
        )
        canvas = tk.Canvas(host, width=340, height=285,
                           highlightthickness=0, background="#1a2734")
        canvas.pack(anchor=tk.CENTER, pady=(6, 0))
        def redraw():
            row = ports["row"]()
            bay = row["bays"][getattr(panel, "_receiving_active", 0)]
            dims = tuple(bay[key] for key in ("width", "height", "depth"))
            paint_one_cabinet(canvas, dims,
                              (bay.get("door_state") or {}).get("door_layout_columns")
                              or door_columns(set_index))
        panel._receiving_after_selection = redraw
        redraw()
        return panel, canvas

    def show_set(index):
        if set_editor_ports is None:
            # Keep compatibility for old callers, without opening another UI.
            return False
        ports = set_editor_ports(index)
        panel, canvas = mount_editor(
            suite_editor_host, ports, set_index=index
        )
        current.update(set_index=index, count=len(ports["row"]()["bays"]),
                       panel=panel, canvas=canvas)
        return True

    def show_common():
        if common_editor_ports is None:
            return False
        if get_snapshot().get("active_mode") != "quantity":
            return False
        mount_editor(common_host, common_editor_ports(), common_box=True)
        return True

    ttk.Button(versions, text="套用共用箱體設定",
               command=lambda: guarded(show_common)).pack(anchor=tk.W)

    def refresh():
        if not win.winfo_exists():
            return
        snapshot = get_snapshot()
        if snapshot.get("active_mode", "set_bay") == "set_bay":
            switch = get_switch()
            controls.switch_brand_var.set(switch.brand)
            counts = switch.connection_counts()
            refresh_receiving_layer_rows(
                controls, tk=tk, ttk=ttk,
                connection_counts=counts,
                on_resize_connections=lambda i, delta: guarded(
                    lambda: resize_connections(i, delta)),
                on_preview=lambda i: guarded(lambda: show_set(i)),
                preview_button_label="套用",
            )
            idx = current["set_index"]
            if idx is not None:
                if idx >= len(counts):
                    for widget in suite_editor_host.winfo_children():
                        widget.destroy()
                    current.update(set_index=None, count=0, panel=None, canvas=None)
                elif current["count"] != counts[idx]:
                    show_set(idx)
                elif current["panel"] is not None:
                    current["panel"]._receiving_refresh()
                    # The panel refresh calls its active-bay redraw callback.
        else:
            quantity.frame.pack(fill=tk.X)
            quantity.refresh()

    def changed(_event=None):
        wanted = "set_bay" if notebook.index(notebook.select()) == 0 else "quantity"
        if get_snapshot().get("active_mode", "set_bay") != wanted:
            if not switch_mode(wanted):
                notebook.select(0 if wanted == "quantity" else 1)
                return
        refresh()

    notebook.bind("<<NotebookTabChanged>>", changed)
    if get_snapshot().get("active_mode") == "quantity":
        notebook.select(1)
    refresh()
    win._receiving_multi_notebook = notebook
    win._receiving_multi_controls = controls
    win._receiving_multi_quantity = quantity
    win._receiving_multi_refresh = refresh
    win._receiving_multi_editor_host = suite_editor_host
    win._receiving_multi_common_host = common_host
    win._receiving_multi_current = current
    ttk.Button(win, text="關閉", command=close).pack(
        anchor=tk.E, padx=12, pady=8)
    return win
