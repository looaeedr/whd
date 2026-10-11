"""Minimal Receiving multi-box UI. All other product owners remain intact.

Only two operator mode choices, one row per existing Set with +/− Bay and
Apply, and a lightweight lower-right connected 2D diagram are shown.
No hidden geometry solve, nested editor, preview popup or extra controls.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from ae_engine.receiving_hole_candidates import version_label

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


def extract_original_door_marks(scene):
    """Project only identified original Door nameplate holes and handle contour.

    No fallback coordinates: when the original baseline does not identify the
    features unambiguously, the lightweight sketch draws none.
    Normalized vectors are presentation-only, never manufacturing geometry.
    """
    from ae_engine.sheetmetal_drawing import CirclePrimitive, PolylinePrimitive

    empty = {"nameplate": (), "handle": ()}
    if scene is None:
        return empty
    outlines = [
        p for p in scene.primitives
        if isinstance(p, PolylinePrimitive) and p.layer == "CUTTING"
        and p.closed and len(p.points) >= 3
    ]
    if not outlines:
        return empty

    def bounds(polyline):
        xs = [float(pt.x) for pt in polyline.points]
        ys = [float(pt.y) for pt in polyline.points]
        return min(xs), min(ys), max(xs), max(ys)

    outer = max(outlines, key=lambda item:
                (bounds(item)[2] - bounds(item)[0]) *
                (bounds(item)[3] - bounds(item)[1]))
    x0, y0, x1, y1 = bounds(outer)
    if x1 <= x0 or y1 <= y0:
        return empty

    def xy(point):
        return ((float(point.x) - x0) / (x1 - x0),
                1.0 - (float(point.y) - y0) / (y1 - y0))

    # Only the stable feature identity from the original Door baseline
    # identifies nameplate circles; do not guess from radius or position.
    nameplate = tuple(
        (*xy(p.center), float(p.radius) / (x1 - x0),
         float(p.radius) / (y1 - y0))
        for p in scene.primitives
        if isinstance(p, CirclePrimitive)
        and p.layer == "CUTTING" and p.source_type == "nameplate_mount"
    )
    # The certified Door baseline has exactly one extra interior CUTTING
    # contour for the handle. Multiple candidates are ambiguous: draw none.
    interior = [
        p for p in outlines if p is not outer
        and bounds(p)[0] > x0 and bounds(p)[1] > y0
        and bounds(p)[2] < x1 and bounds(p)[3] < y1
    ]
    handle = tuple(xy(pt) for pt in interior[0].points) if len(interior) == 1 else ()
    return {"nameplate": nameplate, "handle": handle}


def paint_connected_bays(canvas, count, selected=None, door_marks=None):
    """Cheap front-elevation sketch: touching bays with basic upper/lower doors.

    Selection is a pure presentation overlay. No FinalScene, manufacturing or
    DXF code may run during sketch creation.
    """
    count = max(1, int(count))
    canvas.delete("all")
    canvas._receiving_bay_hitboxes = ()
    selected_bays = ({selected} if isinstance(selected, int)
                     else set(selected or ()))
    selected_bays = frozenset(index for index in selected_bays
                              if isinstance(index, int) and 0 <= index < count)
    canvas._receiving_selected_bays = selected_bays
    canvas._receiving_selected_bay = (
        selected if isinstance(selected, int) else
        (max(selected_bays) if selected_bays else None)
    )
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
        active = index in selected_bays
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
        marks = (door_marks or ())
        this_bay = marks[index] if index < len(marks) else ()
        door_faces = (
            (x0 + inset, top + inset, x1 - inset, split - 2),
            (x0 + inset, split + 2, x1 - inset, top + bay_h - inset),
        )
        for row_index, face in enumerate(door_faces):
            if row_index >= len(this_bay):
                continue
            entry = this_bay[row_index]
            if not entry:
                continue
            fx0, fy0, fx1, fy1 = face
            dw, dh = fx1 - fx0, fy1 - fy0
            if dw <= 0 or dh <= 0:
                continue
            handle = entry.get("handle") or ()
            if len(handle) >= 3:
                coords = [
                    coordinate
                    for px, py in handle
                    for coordinate in (fx0 + px * dw, fy0 + py * dh)
                ]
                canvas.create_polygon(*coords, fill="", outline="#f7c66f", width=1)
            for cx, cy, rx, ry in entry.get("nameplate") or ():
                # Minimum is a screen visibility rule, not a hole dimension.
                px, py = fx0 + cx * dw, fy0 + cy * dh
                sx, sy = max(1.0, rx * dw), max(1.0, ry * dh)
                canvas.create_oval(px - sx, py - sy, px + sx, py + sy,
                                  outline="#f7c66f", width=1)
        hitboxes.append((x0, top, x1, top + bay_h))
    canvas._receiving_bay_hitboxes = tuple(hitboxes)
    return count


def paint_one_cabinet(canvas, dimensions, door_columns=None):
    """Compatibility sketch helper (not a separate operator preview window)."""
    return paint_connected_bays(canvas, 1)


def open_multi_settings(parent, *, get_snapshot, get_switch, switch_mode,
                        resize_connections, resize_sets=None,
                        get_candidate_ports=None, select_bay=None,
                        on_setting_selected=None, get_brand=None,
                        set_brand=None, get_settings_ports=None,
                        get_original_door_marks=None,
                        on_close=None, on_brand_close=None):
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
    topology_changed = {"value": False}
    brand_changed = {"value": False}

    def close():
        if win.grab_current() is win:
            win.grab_release()
        parent._receiving_multi_settings_window = None
        win.destroy()
        # Reconcile the original (hidden) controls only once on exit,
        # never from inside the +連 button's Tk callback.
        if (topology_changed["value"] or brand_changed["value"]) and on_close is not None:
            on_close()
        if brand_changed["value"] and on_brand_close is not None:
            on_brand_close()

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
    top_left = ttk.Frame(win)
    top_left.grid(row=0, column=0, sticky="nw", padx=16, pady=(16, 6))
    brand_row = ttk.Frame(top_left)
    brand_row.pack(anchor="w", pady=(0, 8))
    ttk.Label(brand_row, text="NFB").pack(side="left", padx=(0, 8))
    brand_var = tk.StringVar(master=win, value=get_brand() if get_brand else "士林")
    from ae_engine.receiving_switch_layout import RECEIVING_SWITCH_BRANDS
    brand_selector = ttk.Combobox(
        brand_row, textvariable=brand_var, values=RECEIVING_SWITCH_BRANDS,
        state="readonly", width=8,
    )
    brand_selector.pack(side="left")
    def apply_brand(_event=None):
        if set_brand is not None:
            try:
                if set_brand(brand_var.get()):
                    brand_changed["value"] = True
            except (ValueError, IndexError, RuntimeError) as exc:
                warn(exc)
                brand_var.set(get_brand() if get_brand else "士林")
    brand_selector.bind("<<ComboboxSelected>>", apply_brand)
    mode_row = ttk.Frame(top_left)
    mode_row.pack(anchor="w")
    set_actions = ttk.Frame(top_left)
    set_actions.pack(anchor="w", pady=(5, 0))
    minus_set = ttk.Button(
        set_actions, text="－套", width=5, command=lambda: adjust_sets(-1)
    )
    minus_set.pack(side="left", padx=(0, 3))
    plus_set = ttk.Button(
        set_actions, text="＋套", width=5, command=lambda: adjust_sets(1)
    )
    plus_set.pack(side="left")

    applied = {"set_index": None, "count": 1, "selected": None,
               "selected_bays": (), "mode": "set_bay"}

    right_host = ttk.Frame(win)
    right_host.grid(row=1, column=1, sticky="nsew", padx=24, pady=12)
    right_host.columnconfigure(0, weight=1)
    right_host.rowconfigure(1, weight=1)
    settings_host = ttk.Frame(right_host)
    settings_host.grid(row=0, column=0, sticky="new")
    canvas = tk.Canvas(right_host, width=525, height=310, background="#1a2734",
                       highlightthickness=0)
    canvas.grid(row=1, column=0, sticky="se")

    rows_host = ttk.Frame(win)
    # The Set/Bay row belongs directly BELOW the two upper-left mode
    # choices; only the 2D canvas is anchored to the lower-right corner.
    rows_host.grid(row=1, column=0, sticky="nw",
                   padx=16, pady=(0, 16))
    # The retained per-bay setting categories live directly below the
    # Set/Bay controls. Selection has no implicit edit or popup side effect.
    actions_host = ttk.Frame(rows_host)
    actions_host.pack(anchor="w")
    setting_list = tk.Listbox(
        rows_host, height=3, width=16, selectmode=tk.BROWSE,
        exportselection=False, activestyle="dotbox",
    )
    for label in ("封頭尾", "內門"):
        setting_list.insert(tk.END, label)
    setting_list.pack(anchor="w", pady=(6, 0))
    setting_kind = {"封頭尾": "head_features", "內門": "inner_door_layers"}
    selected_setting = {"set_index": None, "bay_index": None, "kind": None}
    active_ports = {"ports": None}
    candidate_selected = {"head": None, "tail": None}
    candidate_combos = {}
    manager_state = {"open": False, "role": "head"}
    manager_widgets = {"frame": None, "label": None, "buttons": ()}

    def show_setting_controls():
        for widget in settings_host.winfo_children():
            widget.destroy()
        active_ports["ports"] = None
        if selected_setting["kind"] is None or applied["mode"] == "quantity":
            # Version feature design will be handled separately. Preserve the
            # existing QuantityModel but do not render a version editor here.
            return
        if get_settings_ports is None:
            return
        set_index = selected_setting["set_index"]
        bay_index = selected_setting["bay_index"]
        ports = get_settings_ports(set_index)
        ports["select"](bay_index)
        active_ports["ports"] = ports
        from ae_engine.receiving_shared_settings import setting_value
        # Highlighter owns the multi-selection. No second checkbox selector.
        targets = lambda: tuple(sorted(set(applied["selected_bays"]) | {bay_index}))
        def perform(action):
            try:
                action()
                show_setting_controls()
            except (ValueError, IndexError, RuntimeError) as exc:
                warn(exc)
        candidate_combos.clear()

        def editor_saved(role, version_id):
            candidate_selected[role] = version_id
            if win.winfo_exists():
                win.after_idle(show_setting_controls)

        def actions(parent, kind, *, role=None):
            row = ttk.Frame(parent)
            row.pack(anchor="w", pady=3)
            if role is None:
                from ae_engine.receiving_shared_settings import setting_value
                current = setting_value(ports["row"](), bay_index, kind)
                value = tk.StringVar(master=win, value=str(current))
                ttk.Label(row, text="內門層數").pack(side="left")
                ttk.Combobox(row, textvariable=value, values=("1", "2"),
                             width=5, state="readonly").pack(side="left", padx=3)
                ttk.Button(row, text="編輯",
                           command=lambda: perform(lambda: ports["change"](kind, int(value.get())))).pack(side="left", padx=3)
                return
            ttk.Label(row, text="封頭孔" if role == "head" else "封尾孔").pack(
                side="left", padx=(0, 5)
            )
            if get_candidate_ports is None:
                ttk.Button(row, text="編輯",
                           command=lambda: perform(lambda: ports["holes"](role, targets()))).pack(side="left", padx=3)
                return

            library = get_candidate_ports()
            versions = library["versions"](role)
            ids = {version_label(item["id"]): item["id"]
                   for item in versions}
            current_id = candidate_selected[role]
            if current_id not in ids.values():
                candidate_selected[role] = None
            chosen = next((label for label, key in ids.items()
                           if key == candidate_selected[role]), "即時")
            variable = tk.StringVar(master=win, value=chosen)
            # Use the ORIGINAL native readonly ttk.Combobox, not a drawn menu.
            selector = ttk.Combobox(
                row, textvariable=variable, values=("即時", *ids),
                width=11, state="readonly",
            )
            selector.pack(side="left", padx=(0, 5))
            candidate_combos[role] = selector

            def choose(_event=None):
                candidate_selected[role] = ids.get(variable.get())
                apply_button.configure(
                    state="normal" if candidate_selected[role] else "disabled"
                )
                refresh_manager_controls()

            selector.bind("<<ComboboxSelected>>", choose)

            def edit_role():
                try:
                    library["edit"](
                        role, candidate_selected[role],
                        lambda created, role=role: editor_saved(role, created),
                    )
                except (ValueError, IndexError, RuntimeError) as exc:
                    warn(exc)

            def apply_role():
                try:
                    if applied["mode"] != "set_bay" or applied["set_index"] is None:
                        raise ValueError("請先套用一套並在簡易圖高亮要指定的連")
                    get_candidate_ports()["apply"](
                        role, candidate_selected[role],
                        applied["set_index"], tuple(applied["selected_bays"]),
                    )
                except (ValueError, IndexError, RuntimeError) as exc:
                    warn(exc)

            ttk.Button(row, text="編輯", command=edit_role).pack(side="left", padx=(0, 3))
            apply_button = ttk.Button(
                row, text="套用", command=apply_role,
                state="normal" if candidate_selected[role] else "disabled",
            )
            apply_button.pack(side="left")

        if selected_setting["kind"] == "head_features":
            actions(settings_host, "head_features", role="head")
            actions(settings_host, "tail_features", role="tail")
            if get_candidate_ports is not None:
                manage_toggle = ttk.Button(
                    settings_host, text="版本管理",
                    command=lambda: toggle_manager()
                )
                manage_toggle.pack(anchor="e", pady=(5, 0))
                manage = ttk.Frame(settings_host)
                title = ttk.Label(manage, text="")
                title.pack(anchor="w")
                choices = ttk.Frame(manage)
                choices.pack(anchor="w", pady=(4, 2))
                role_var = tk.StringVar(master=win, value=manager_state["role"])
                def choose_manage_role():
                    manager_state["role"] = role_var.get()
                    refresh_manager_controls()
                for label, value in (("封頭孔", "head"), ("封尾孔", "tail")):
                    ttk.Radiobutton(
                        choices, text=label, value=value,
                        variable=role_var, command=choose_manage_role,
                    ).pack(side="left", padx=(0, 10))
                buttons = ttk.Frame(manage)
                buttons.pack(anchor="w", pady=3)
                actions_map = []
                for label, destination in (("複製為新版本", "same"),
                                           ("複製到另一側", "other"),
                                           ("刪除目前版本", "delete")):
                    control = ttk.Button(
                        buttons, text=label,
                        command=lambda action=destination: manage_action(action)
                    )
                    control.pack(side="left", padx=(0, 4))
                    actions_map.append(control)
                manager_widgets.update(frame=manage, label=title, buttons=tuple(actions_map))
                refresh_manager_controls()
                if manager_state["open"]:
                    manage.pack(anchor="e")
            else:
                manager_widgets.update(frame=None, label=None, buttons=())
        else:
            actions(settings_host, "inner_door_layers")
            manager_widgets.update(frame=None, label=None, buttons=())

    def refresh_manager_controls():
        title = manager_widgets["label"]
        if title is None or not title.winfo_exists():
            return
        role = manager_state["role"]
        chosen = candidate_selected[role]
        title.configure(text=("封頭孔" if role == "head" else "封尾孔")
                        + "｜" + ("即時" if chosen is None else
                                 version_label(chosen)))
        for button in manager_widgets["buttons"]:
            button.configure(state="normal" if chosen is not None else "disabled")
        if manager_widgets["buttons"]:
            manager_widgets["buttons"][1].configure(
                text="複製到封尾" if role == "head" else "複製到封頭"
            )

    def toggle_manager():
        frame = manager_widgets["frame"]
        if frame is None:
            return
        manager_state["open"] = not manager_state["open"]
        if manager_state["open"]:
            frame.pack(anchor="e")
            refresh_manager_controls()
        else:
            frame.pack_forget()

    def manage_action(action):
        role = manager_state["role"]
        selected_id = candidate_selected[role]
        if selected_id is None or get_candidate_ports is None:
            return
        try:
            library = get_candidate_ports()
            if action == "delete":
                if not messagebox.askyesno(
                    "刪除候選版本", "確定刪除此候選版本？已套用到板件的孔位不會刪除。",
                    parent=win,
                ):
                    return
                library["delete"](role, selected_id)
                candidate_selected[role] = None
            else:
                destination = role if action == "same" else (
                    "tail" if role == "head" else "head"
                )
                created = library["copy"](role, selected_id, destination)
                candidate_selected[destination] = created
                manager_state["role"] = destination
            win.after_idle(show_setting_controls)
        except (ValueError, IndexError, RuntimeError) as exc:
            warn(exc)

    def warn(exc):
        messagebox.showwarning("多只設定", str(exc), parent=win)
        return False

    def ensure_set_mode():
        if get_snapshot().get("active_mode", "set_bay") != "set_bay":
            if not switch_mode("set_bay"):
                return False
        return True

    mark_cache = {"key": None, "values": ()}

    def render():
        count = applied["count"] if applied["mode"] == "set_bay" else 1
        selected = applied["selected_bays"] if applied["mode"] == "set_bay" else None
        marks = ()
        if applied["mode"] == "set_bay" and get_original_door_marks is not None:
            set_index = applied["set_index"]
            if set_index is None:
                set_index = 0
            key = (set_index, count)
            if mark_cache["key"] != key:
                # The baseline is requested once per applied Set/connection
                # count, not on every canvas resize or selection redraw.
                mark_cache["values"] = tuple(
                    get_original_door_marks(set_index, bay_index)
                    for bay_index in range(count)
                )
                mark_cache["key"] = key
            marks = mark_cache["values"]
        paint_connected_bays(canvas, count, selected, marks)
        canvas._receiving_selected_bay = (
            applied["selected"] if applied["mode"] == "set_bay" else None
        )

    # Retain button identity while a +連/−連 callback is executing.
    # Destroying its own Tk button mid-invoke is a first-click freeze risk.
    bay_rows = []

    def refresh_rows():
        if mode_var.get() != "set_bay":
            set_actions.pack_forget()
            for entry in bay_rows:
                entry["frame"].destroy()
            bay_rows.clear()
            # Quantity keeps the original version entry, not Set/Bay controls.
            if tuple(setting_list.get(0, tk.END)) != ("封頭尾",):
                setting_list.delete(0, tk.END)
                setting_list.insert(tk.END, "封頭尾")
            if not setting_list.winfo_manager():
                setting_list.pack(anchor="w", pady=(6, 0))
            return
        if not set_actions.winfo_manager():
            set_actions.pack(anchor="w", pady=(5, 0))
        if tuple(setting_list.get(0, tk.END)) != ("封頭尾", "內門"):
            setting_list.delete(0, tk.END)
            setting_list.insert(tk.END, "封頭尾", "內門")
        if not setting_list.winfo_manager():
            setting_list.pack(anchor="w", pady=(6, 0))
        counts = tuple(max(1, int(n)) for n in get_switch().connection_counts())
        # Only create or remove rows when the number of Sets changes.
        while len(bay_rows) > len(counts):
            bay_rows.pop()["frame"].destroy()
        while len(bay_rows) < len(counts):
            index = len(bay_rows)
            row = ttk.Frame(actions_host)
            row.pack(anchor="w", pady=2)
            ttk.Label(row, text=f"第{index + 1}套").pack(
                side="left", padx=(0, 10))
            minus = ttk.Button(row, text="－連",
                               command=lambda i=index: resize(i, -1))
            minus.pack(side="left", padx=(0, 3))
            count_label = ttk.Label(row, width=3, anchor="center")
            count_label.pack(side="left", padx=(0, 3))
            plus = ttk.Button(row, text="＋連",
                              command=lambda i=index: resize(i, 1))
            plus.pack(side="left", padx=(0, 3))
            apply_button = ttk.Button(row, text="套用",
                                      command=lambda i=index: apply(i))
            apply_button.pack(side="left")
            bay_rows.append({"frame": row, "count": count_label})
        for entry, count in zip(bay_rows, counts):
            entry["count"].configure(text=str(count))

    def select_setting(_event=None):
        indices = setting_list.curselection()
        if not indices:
            return
        label = str(setting_list.get(indices[0]))
        set_index = applied["set_index"]
        if set_index is None:
            set_index = 0
        bay_index = applied["selected"]
        if bay_index is None:
            bay_index = 0
        kind = setting_kind[label]
        try:
            # In quantity mode the embedded version controls use QuantityModel,
            # not an accidental per-Bay mutation.
            if applied["mode"] == "set_bay" and on_setting_selected is not None:
                on_setting_selected(set_index, bay_index, kind)
            selected_setting.update(
                set_index=set_index, bay_index=bay_index, kind=kind
            )
            show_setting_controls()
        except (ValueError, IndexError, RuntimeError) as exc:
            warn(exc)

    setting_list.bind("<<ListboxSelect>>", select_setting)

    def adjust_sets(delta):
        if resize_sets is None or mode_var.get() != "set_bay":
            return False
        try:
            if not ensure_set_mode():
                return False
            result = resize_sets(delta)
            if result:
                topology_changed["value"] = True
                counts = tuple(get_switch().connection_counts())
                if (applied["set_index"] is not None
                        and applied["set_index"] >= len(counts)):
                    applied.update(set_index=None, selected=None,
                                   selected_bays=(), count=1)
                    selected_setting.update(set_index=None, bay_index=None, kind=None)
                    setting_list.selection_clear(0, tk.END)
                    show_setting_controls()
                    render()
                refresh_rows()
            return result
        except (ValueError, IndexError, RuntimeError) as exc:
            return warn(exc)

    def resize(index, delta):
        try:
            if not ensure_set_mode():
                return False
            result = resize_connections(index, delta)
            if result:
                topology_changed["value"] = True
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
                           count=count, selected=0, selected_bays=(0,))
            selected_setting.update(set_index=None, bay_index=None, kind=None)
            setting_list.selection_clear(0, tk.END)
            show_setting_controls()
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
                    selected_bays = set(applied["selected_bays"])
                    if index in selected_bays and len(selected_bays) > 1:
                        selected_bays.remove(index)
                        active = min(selected_bays)
                    else:
                        selected_bays.add(index)
                        active = index
                    if select_bay is not None:
                        select_bay(applied["set_index"], active)
                    applied["selected"] = active
                    applied["selected_bays"] = tuple(sorted(selected_bays))
                    if selected_setting["kind"] is not None:
                        if on_setting_selected is not None:
                            on_setting_selected(applied["set_index"], active,
                                                selected_setting["kind"])
                        selected_setting.update(
                            set_index=applied["set_index"], bay_index=active
                        )
                    show_setting_controls()
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
            applied.update(set_index=None, selected=None, selected_bays=(), count=1)
            selected_setting.update(set_index=None, bay_index=None, kind=None)
            setting_list.selection_clear(0, tk.END)
            show_setting_controls()
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
    win._receiving_multi_brand_var = brand_var
    win._receiving_multi_brand_selector = brand_selector
    win._receiving_multi_set_buttons = (minus_set, plus_set)
    win._receiving_multi_candidate_selected = candidate_selected
    win._receiving_multi_candidate_combos = candidate_combos
    win._receiving_multi_manager_state = manager_state
    win._receiving_multi_settings_host = settings_host
    win._receiving_multi_mode_var = mode_var
    win._receiving_multi_mode_controls = mode_row
    win._receiving_multi_rows_host = actions_host
    win._receiving_multi_setting_list = setting_list
    win._receiving_multi_selected_setting = selected_setting
    win._receiving_multi_canvas = canvas
    win._receiving_multi_applied = applied
    win._receiving_multi_refresh = refresh_rows
    win._receiving_multi_apply = apply
    return win
