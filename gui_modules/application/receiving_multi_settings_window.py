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


class _IdleCanvasRedraw:
    """Coalesce Configure bursts and skip already-painted canvas dimensions.

    Selection redraws remain immediate. A real size change always paints the
    last observed size; a pending stale Configure is cancelled by an explicit
    paint. No geometry or state computation occurs inside this scheduler.
    """

    def __init__(self, canvas, draw):
        self.canvas = canvas
        self.draw = draw
        self.job = None
        self._painted_size = None

    def _size(self):
        return (self.canvas.winfo_width(), self.canvas.winfo_height())

    def request(self, _event=None):
        if not self.canvas.winfo_exists():
            return
        if self._painted_size == self._size():
            return
        if self.job is None:
            self.job = self.canvas.after_idle(self._run)

    def _run(self):
        self.job = None
        if self.canvas.winfo_exists() and self._painted_size != self._size():
            self.draw()
            self._painted_size = self._size()

    def mark_drawn(self):
        """The user-selected state has just been painted synchronously."""
        if not self.canvas.winfo_exists():
            return
        self._painted_size = self._size()
        self.cancel()

    def cancel(self):
        job, self.job = self.job, None
        if job is not None:
            try:
                self.canvas.after_cancel(job)
            except tk.TclError:
                pass


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


def paint_connected_bays(canvas, count, selected=None, door_marks=None, version_labels=None, bay_dimensions=None):
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
    # Draw from the canonical physical Bay W/H proportions, rather than an
    # equal-width placeholder that stays unchanged after size confirmation.
    # D is a depth axis: show it in the size summary, not as a false 2D width.
    source = tuple(bay_dimensions or ())
    physical = []
    for index in range(count):
        item = source[index] if index < len(source) else (800.0, 1600.0, 350.0)
        if isinstance(item, dict):
            w, h = float(item["width"]), float(item["height"])
        else:
            w, h = float(item[0]), float(item[1])
        physical.append((max(1.0, w), max(1.0, h)))
    scale = min(usable_w / sum(w for w, _ in physical),
                usable_h / max(h for _, h in physical))
    left = (width - sum(w for w, _ in physical) * scale) / 2
    bottom = (height + max(h for _, h in physical) * scale) / 2
    cursor_x = left
    hitboxes = []
    for index, (physical_w, physical_h) in enumerate(physical):
        x0, x1 = cursor_x, cursor_x + physical_w * scale
        cursor_x = x1
        top, bay_h = bottom - physical_h * scale, physical_h * scale
        bay_w = x1 - x0
        split = top + bay_h * min(1100.0 / physical_h, 0.999)
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
                                  outline="#f7c66f", width=1,
                                  tags=("receiving_nameplate",))
        labels = (version_labels or ())
        by_role = labels[index] if index < len(labels) else {}
        if by_role:
            label_lines = []
            for role, prefix in (("head", "封頭"), ("tail", "封尾"),
                                 ("inner-door", "內門")):
                version_id = by_role.get(role)
                if version_id is not None:
                    label = version_label(version_id) if version_id else "即時"
                    label_lines.append(f"{prefix}：{label}")
            # Canvas text is a status overlay only; source is saved per-Bay
            # identity, never candidate dropdown presentation state.
            for line_no, label in enumerate(label_lines):
                canvas.create_text(
                    (x0+x1)/2, top + bay_h * (0.2 + 0.13*line_no),
                    text=label, fill="#ffffff", width=max(18, bay_w-4),
                    font=("TkDefaultFont", 9, "bold"), tags=("applied_version",),
                )
        hitboxes.append((x0, top, x1, top + bay_h))
    canvas._receiving_bay_hitboxes = tuple(hitboxes)
    return count


def paint_one_cabinet(canvas, dimensions, door_columns=None):
    """Compatibility sketch helper (not a separate operator preview window)."""
    return paint_connected_bays(canvas, 1)


def dimension_group_summary(bays):
    """Derive arbitrary-sized W/H/D groups from canonical physical Bays."""
    rows = {}
    for index, bay in enumerate(bays):
        key = tuple(float(bay[field]) for field in ("width", "height", "depth"))
        rows.setdefault(key, []).append(index)
    return tuple((dimensions, tuple(indices)) for dimensions, indices in rows.items())


def open_multi_settings(parent, *, get_snapshot, get_switch, switch_mode,
                        resize_connections, resize_sets=None,
                        get_candidate_ports=None, get_inner_candidate_ports=None,
                        select_bay=None,
                        on_setting_selected=None, get_brand=None,
                        set_brand=None, get_brand_change_impact=None,
                        get_settings_ports=None,
                        get_nfb_transaction_ports=None,
                        get_original_door_marks=None,
                        get_initial_door_marks=None,
                        get_applied_version_labels=None,
                        get_real_cut_preview_request=None,
                        get_dimension_group=None,
                        get_single_size_quantity=None,
                        set_single_size_quantity=None,
                        edit_single_holes=None,
                        edit_single_inner_door=None, edit_multi_inner_door=None,
                        on_close=None, on_brand_close=None,
                        dialog_kind="multi"):
    """Full-screen modal Receiving operator UI with no unsolicited widgets."""
    old = getattr(parent, "_receiving_multi_settings_window", None)
    if old is not None and old.winfo_exists():
        old.lift()
        old.focus_set()
        return old

    win = tk.Toplevel(parent)
    title = "單只設定" if dialog_kind == "single" else "多連設定"
    win.title(title)
    # The primary application is not interactive while multi-settings is open.
    win.transient(parent)
    parent._receiving_multi_settings_window = win
    # Fail closed BEFORE installing modal callbacks or drawing widgets. A
    # refused Quantity/Set-Bay transition used to leave an unfinished Tk
    # Toplevel on screen; its close() callback referenced sketch_redraw,
    # close_real_preview and close_manager before those closures existed.
    initial_mode = "quantity" if dialog_kind == "single" else "set_bay"
    try:
        if get_snapshot().get("active_mode", "set_bay") != initial_mode:
            if not switch_mode(initial_mode):
                raise ValueError("無法切換設定模式")
    except Exception:
        # A failed source/geometry gate cannot leave a stale modal grab or a
        # parent pointer to an uninitialized, uncloseable Toplevel.
        parent._receiving_multi_settings_window = None
        win.destroy()
        raise
    topology_changed = {"value": False}
    brand_changed = {"value": False}

    def close():
        sketch_redraw.cancel()
        close_real_preview()
        close_manager()
        if win.grab_current() is win:
            win.grab_release()
        parent._receiving_multi_settings_window = None
        win.destroy()
        # Reconcile the original (hidden) controls only once on exit,
        # never from inside the +連 button's Tk callback.
        if brand_changed["value"] and on_brand_close is not None:
            on_brand_close()
        # Always restore the originating Assembly page, even without edits.
        if on_close is not None:
            on_close()

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
        capture_modal_focus()

    def capture_modal_focus():
        # On X11 a first after_idle may run before the Toplevel is mapped.
        # Grab only a visible window, and never steal a nested dialog's grab.
        if not win.winfo_exists() or not win.winfo_viewable():
            return
        if win.grab_current() is None:
            win.grab_set()
        if win.grab_current() is win:
            win.lift()
            win.focus_set()

    def on_modal_map(event):
        if event.widget is win:
            win.after_idle(capture_modal_focus)

    win.bind("<Map>", on_modal_map, add="+")
    win.after_idle(maximize_and_lock)
    win.columnconfigure(1, weight=1)
    win.rowconfigure(0, weight=1)

    # Two permanent columns. Left owns Set/Bay actions; right owns the
    # function selector above a separate 2D diagram. Neither section moves
    # when the category changes or when the version manager is opened.
    from .receiving_scroll_view import make_scrollable_frame
    left_scroll, left_content, left_scroll_canvas = make_scrollable_frame(
        win, tk=tk, ttk=ttk, width=280, height=610,
    )
    left_scroll.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
    left_host = ttk.Frame(left_content)
    left_host.pack(fill="both", expand=True)
    right_host = ttk.Frame(win)
    right_host.grid(row=0, column=1, sticky="nsew", padx=24, pady=16)
    right_host.columnconfigure(0, weight=1)
    right_host.rowconfigure(2, weight=1)

    # Reflect the authoritative mode instead of deferring a hidden mode switch
    # (and its complete geometry rebuild) to the first connection edit.
    # The obsolete Quantity main mode has been removed from this window.
    # Preserve the independent quantity allocation inside Version Manager.
    # The authoritative transition has already been accepted before Tk
    # installs any modal callbacks (or the modal is destroyed on failure).
    mode_var = tk.StringVar(master=win, value=initial_mode)
    top_left = ttk.Frame(left_host)
    top_left.pack(anchor="nw")
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
            previous = get_brand() if get_brand else "士林"
            proposed = brand_var.get()
            # Do not short-circuit same displayed Set brand: the one global
            # Set/Bay selector may still need to update other Sets that carry
            # a different inherited brand. set_brand() owns the no-op check.
            try:
                affected = (get_brand_change_impact(proposed)
                            if get_brand_change_impact is not None else 0)
                if affected and not messagebox.askyesno(
                    "確認切換 NFB 廠牌",
                    f"此次切換將有 {affected} 顆 NFB 原型號待重選。"
                    "確認後保留舊型號來源，但禁止未重選前製造。是否繼續？",
                    parent=win,
                ):
                    # ComboboxSelected changes Tk presentation first. Restore
                    # it without a product write, Undo entry or geometry solve.
                    brand_var.set(previous)
                    return
                if set_brand(proposed):
                    brand_changed["value"] = True
                    win.after_idle(show_setting_controls)
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
    if dialog_kind != "single":
        minus_set.pack(side="left", padx=(0, 3))
    plus_set = ttk.Button(
        set_actions, text="＋套", width=5, command=lambda: adjust_sets(1)
    )
    if dialog_kind != "single":
        plus_set.pack(side="left")

    applied = {"set_index": None, "count": 1, "selected": None,
               "selected_bays": (), "mode": initial_mode}
    single_mode = dialog_kind == "single"

    # Right TOP: cabinet dimensions and quantities stay visible at full width.
    # Function controls sit below, with the independently resizable 2D diagram.
    function_scroll, function_content, function_scroll_canvas = make_scrollable_frame(
        right_host, tk=tk, ttk=ttk, width=610, height=110,
    )
    function_scroll.grid(row=1, column=0, sticky="new", pady=(2, 0))
    function_host = ttk.Frame(
        function_content, padding=8, relief="groove", borderwidth=1,
    )
    function_host.pack(fill="both", expand=True)
    function_host.columnconfigure(1, weight=1)
    setting_list = tk.Listbox(
        function_host, height=3, width=16, selectmode=tk.BROWSE,
        exportselection=False, activestyle="dotbox",
    )
    for label in ("封頭尾", "內門"):
        setting_list.insert(tk.END, label)
    setting_list.grid(row=0, column=0, sticky="nw", padx=(0, 12))
    settings_host = ttk.Frame(function_host)
    settings_host.grid(row=0, column=1, sticky="new")

    diagram_host = ttk.Frame(right_host, padding=8, relief="groove", borderwidth=1)
    diagram_host.grid(row=2, column=0, sticky="nsew", pady=(2, 0))
    diagram_host.columnconfigure(0, weight=1)
    diagram_host.rowconfigure(0, weight=1)
    canvas = tk.Canvas(diagram_host, width=525, height=310, background="#1a2734",
                       highlightthickness=0)
    canvas.grid(row=0, column=0, sticky="nsew")

    rows_host = ttk.Frame(left_host)
    rows_host.pack(anchor="nw", pady=(8, 0))
    actions_host = ttk.Frame(rows_host)
    actions_host.pack(anchor="w")
    # Committed size/quantity rows belong under left Set/Bay operations.
    confirmed_groups_host = ttk.Frame(left_host)
    confirmed_groups_host.pack(anchor="nw", fill="x", pady=(4, 0))
    # W/H/D, quantity and Confirm cannot fit inside the 280px Set/Bay sidebar.
    size_groups_host = ttk.Frame(right_host, padding=8, relief="groove", borderwidth=1)
    size_groups_host.grid(row=0, column=0, sticky="ew")
    setting_kind = {"封頭尾": "head_features", "內門": "inner_door_layers"}
    selected_setting = {"set_index": None, "bay_index": None, "kind": None}
    active_ports = {"ports": None}
    candidate_selected = {"head": None, "tail": None, "inner-door": None}
    candidate_combos = {}
    manager_state = {"role": "head", "page": "candidates", "family": "endcap"}
    manager_window = {"win": None}
    manager_widgets = {"frame": None, "label": None, "buttons": (),
                       "buttons_frame": None, "quantity_frame": None,
                       "canvas": None}
    quantity_ui = None
    real_preview = {"win": None, "view": None, "status": None,
                    "role": None, "generation": 0}

    def close_real_preview():
        real_preview["generation"] += 1
        popup = real_preview["win"]
        real_preview.update(win=None, view=None, status=None, role=None)
        if popup is not None and popup.winfo_exists():
            if popup.grab_current() is popup:
                popup.grab_release()
            popup.destroy()
        if win.winfo_exists() and win.grab_current() is None:
            win.grab_set()

    def show_real_preview(role):
        """Movable verified FinalScene view; the main window stays blocked."""
        if get_real_cut_preview_request is None:
            return None
        popup = real_preview["win"]
        if popup is None or not popup.winfo_exists():
            popup = tk.Toplevel(win)
            popup.title("截角實體資料｜真實2D")
            popup.geometry("960x720")
            popup.minsize(460, 320)
            popup.transient(win)
            from .receiving_scroll_view import make_scrollable_frame
            popup_scroll, popup_content, popup_viewport = make_scrollable_frame(
                popup, tk=tk, ttk=ttk, width=920, height=660,
            )
            popup_scroll.pack(fill="both", expand=True)
            body = ttk.Frame(popup_content, padding=6)
            body.pack(fill="both", expand=True)
            popup._receiving_real_preview_scroll = popup_scroll
            status = tk.StringVar(master=popup, value="準備顯示實際幾何資料")
            ttk.Label(body, textvariable=status).pack(anchor="w")
            from .receiving_settings_preview_2d import ReceivingSettingsPreview2D
            view = ReceivingSettingsPreview2D(
                body, tk=tk, ttk=ttk, requests=(),
            )
            actions = ttk.Frame(body)
            actions.pack(fill="x")
            ttk.Button(actions, text="放大", command=lambda: view.zoom(.8)).pack(side="left")
            ttk.Button(actions, text="縮小", command=lambda: view.zoom(1.25)).pack(side="left")
            ttk.Button(actions, text="重設視角", command=view.reset_view).pack(side="left")
            ttk.Button(actions, text="關閉", command=close_real_preview).pack(side="right")
            popup.protocol("WM_DELETE_WINDOW", close_real_preview)
            real_preview.update(win=popup, view=view, status=status)
        if win.grab_current() is win:
            win.grab_release()
        if popup.grab_current() is not popup:
            popup.grab_set()
        popup.lift()
        popup.focus_set()
        real_preview["role"] = role
        real_preview["generation"] += 1
        generation = real_preview["generation"]
        selected_id = candidate_selected[role]
        si = applied["set_index"] if applied["set_index"] is not None else 0
        bi = selected_setting["bay_index"]
        if bi is None or selected_setting["set_index"] != si:
            bi = applied["selected"] if applied["selected"] is not None else 0
        label = "即時" if selected_id is None else version_label(selected_id)
        popup.title(f"{role.replace('inner-door', '內門').replace('head', '封頭').replace('tail', '封尾')}｜{label}｜真實截角2D")
        real_preview["status"].set("正在取得既有 FinalScene 真實幾何…")
        def refresh_exact():
            def still_current():
                # The geometry provider may run a nested Tk callback, switch
                # candidate/version or close the modal before it returns.
                # Never publish a superseded request or error to a newer view.
                return (
                    real_preview["generation"] == generation
                    and real_preview["win"] is popup
                    and popup.winfo_exists()
                    and real_preview["view"] is not None
                )

            if not still_current():
                return
            try:
                request = get_real_cut_preview_request(role, selected_id, si, bi)
                if not still_current():
                    return  # A newer operator choice already owns this view.
                if request is None:
                    raise ValueError("此版本缺少可驗證的實體幾何來源")
                real_preview["view"].draw_geometry((request,))
                if not still_current():
                    return
                popup._receiving_real_preview_request = request
                real_preview["status"].set(
                    f"第{si+1}套／第{bi+1}連｜{label}｜實際 FinalScene 投影；滾輪縮放／中鍵平移"
                )
            except Exception as exc:
                if not still_current():
                    return
                real_preview["view"].invalidate(str(exc))
                real_preview["status"].set("真實幾何不可用：" + str(exc))
        popup.after_idle(refresh_exact)
        return popup

    def editor_saved(role, version_id, *, keep_live=False):
        # Saving while "即時" creates a candidate but MUST NOT select it:
        # selecting v1 here would make the next Edit overwrite v1 instead of
        # creating v2. Existing-version edits retain their selected version.
        if not keep_live:
            candidate_selected[role] = version_id
        if win.winfo_exists():
            win.after_idle(show_setting_controls)
            win.after_idle(refresh_manager_controls)

    def safe_single_holes(role):
        try:
            edit_single_holes(role)
        except (ValueError, IndexError, RuntimeError) as exc:
            warn(exc)

    def safe_single_inner_door():
        try:
            edit_single_inner_door()
        except (ValueError, IndexError, RuntimeError) as exc:
            warn(exc)

    def show_setting_controls():
        for widget in settings_host.winfo_children():
            widget.destroy()
        active_ports["ports"] = None
        if single_mode:
            if selected_setting["kind"] == "head_features":
                if edit_single_holes is not None:
                    for role, label in (("head", "封頭孔"), ("tail", "封尾孔")):
                        ttk.Button(
                            settings_host, text=label + "編輯",
                            command=lambda role=role: safe_single_holes(role),
                        ).pack(side="left", padx=4)
            elif selected_setting["kind"] == "inner_door_layers":
                if edit_single_inner_door is not None:
                    ttk.Button(
                        settings_host, text="編輯",
                        command=lambda: safe_single_inner_door(),
                    ).pack(anchor="w")
                else:
                    ttk.Label(
                        settings_host, text="尚未連接原內門開孔編輯器"
                    ).pack(anchor="w")
            return
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
        # Highlighter owns the multi-selection. No second checkbox selector.
        # The canvas highlight, including an empty selection, is the ONLY apply target.
        targets = lambda: tuple(applied["selected_bays"])
        def perform(action):
            try:
                action()
                show_setting_controls()
            except (ValueError, IndexError, RuntimeError) as exc:
                warn(exc)
        candidate_combos.clear()

        def actions(parent, kind, *, role):
            row = ttk.Frame(parent)
            row.pack(anchor="w", pady=3)
            ttk.Label(
                row, text={"head": "封頭孔", "tail": "封尾孔",
                           "inner-door": "內門版本"}[role],
            ).pack(side="left", padx=(0, 5))
            source = (get_inner_candidate_ports if role == "inner-door"
                      else get_candidate_ports)
            if source is None:
                if role != "inner-door":
                    ttk.Button(
                        row, text="編輯",
                        command=lambda: perform(
                            lambda: ports["holes"](role, targets())
                        ),
                    ).pack(side="left", padx=3)
                return

            library = source()
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
                    state="normal" if candidate_selected[role] is not None
                    or "apply_live" in source() else "disabled"
                )
                refresh_manager_controls()
                show_real_preview(role)

            selector.bind("<<ComboboxSelected>>", choose)

            def edit_role():
                try:
                    selected_before = candidate_selected[role]
                    callback = (edit_multi_inner_door if role == "inner-door"
                                and edit_multi_inner_door is not None
                                else library["edit"])
                    if callback is edit_multi_inner_door:
                        callback(
                            selected_before,
                            lambda created, role=role, live=(selected_before is None):
                                editor_saved(role, created, keep_live=live),
                        )
                    else:
                        callback(
                            role, selected_before,
                            lambda created, role=role, live=(selected_before is None):
                                editor_saved(role, created, keep_live=live),
                        )
                except (ValueError, IndexError, RuntimeError) as exc:
                    warn(exc)

            def apply_role():
                try:
                    if applied["mode"] != "set_bay" or applied["set_index"] is None:
                        raise ValueError("請先套用一套並在簡易圖高亮要指定的連")
                    if not applied["selected_bays"]:
                        return  # Zero highlighted Bays is a valid no-op.
                    if candidate_selected[role] is None:
                        source()["apply_live"](
                            role, applied["set_index"], tuple(applied["selected_bays"]),
                        )
                    else:
                        source()["apply"](
                            role, candidate_selected[role],
                            applied["set_index"], tuple(applied["selected_bays"]),
                        )
                    render()
                    if real_preview["role"] == role:
                        show_real_preview(role)
                except (ValueError, IndexError, RuntimeError) as exc:
                    warn(exc)

            ttk.Button(row, text="編輯", command=edit_role).pack(side="left", padx=(0, 3))
            apply_button = ttk.Button(
                row, text="套用", command=apply_role,
                state="normal" if candidate_selected[role] is not None
                or "apply_live" in source() else "disabled",
            )
            apply_button.pack(side="left")

        if selected_setting["kind"] == "head_features":
            actions(settings_host, "head_features", role="head")
            actions(settings_host, "tail_features", role="tail")
            if get_candidate_ports is not None:
                ttk.Button(
                    settings_host, text="版本管理", command=open_manager,
                ).pack(anchor="e", pady=(5, 0))
        else:
            if get_inner_candidate_ports is not None:
                actions(settings_host, "inner_door_layers", role="inner-door")
                ttk.Button(
                    settings_host, text="版本管理",
                    command=lambda: open_manager("inner"),
                ).pack(anchor="e", pady=(5, 0))
            # Restore the existing per-Bay linkage without bringing back the
            # removed layer-count Edit button. The 2D highlight is authority.
            link_row = ttk.Frame(settings_host)
            link_row.pack(anchor="w", pady=3)
            ttk.Button(
                link_row, text="連動選取的連",
                command=lambda: perform(lambda: ports["share"](
                    "inner_door_layers", targets(),
                )) if targets() else None,
            ).pack(side="left", padx=(0, 5))
            # No per-Bay "unlink" action here: the operator-selected
            # highlight / version management is the sole current inner-door
            # workflow. The former "解除本連連動" control was explicitly retired.
            # #1500: the existing source-verified Receiving NFB transaction
            # ports must remain operable after the settings window refactor.
            # Use the SAME canvas Bay highlighter and single canonical adapter;
            # these controls never invent X/datum, a source DXF or a new owner.
            if (get_nfb_transaction_ports is not None
                    and applied["mode"] == "set_bay"
                    and applied["set_index"] == set_index
                    and applied["selected_bays"]):
                highlighted = targets()
                try:
                    status_ports = get_nfb_transaction_ports()
                    status = status_ports["state"](
                        set_index, highlighted[0], highlighted,
                    )
                    all_submitted = all(
                        status_ports["state"](
                            set_index, bi, highlighted,
                        ).get("can_restore", False)
                        for bi in highlighted
                    )
                except (ValueError, TypeError, KeyError, IndexError, OSError):
                    status = {}
                    all_submitted = False

                nfb_row = ttk.Frame(settings_host)
                nfb_row.pack(anchor="w", pady=(5, 1))

                def nfb_confirm(preview):
                    # The transaction's actual affected parts and blocked
                    # dependencies, not the button label, own the warning.
                    affected = "、".join(preview.impacted_parts) or "目前 NFB 設定"
                    held = "、".join(preview.held_parts)
                    message = (
                        f"動作：{preview.action}\n"
                        f"目標連：{'、'.join(preview.target_bay_ids)}\n"
                        f"影響板件：{affected}"
                    )
                    if held:
                        message += f"\n尚未製造放行：{held}"
                    if preview.dependency_warnings:
                        message += "\n待核對：" + "；".join(preview.dependency_warnings)
                    # Same validated transaction preview, not editable X or
                    # a second authority. Old synthetic test previews may
                    # omit these optional read-only rows.
                    operator_x_changes = getattr(preview, "operator_x_changes", ())
                    if operator_x_changes:
                        message += ("\n受影響 NFB／X 基準差異：\n"
                                    + "\n".join(operator_x_changes))
                    message += "\n確定套用這次 NFB 交易？"
                    return messagebox.askyesno("NFB 提交確認", message, parent=win)

                def run_nfb_transaction(action):
                    try:
                        current = targets()
                        if (applied["mode"] != "set_bay"
                                or applied["set_index"] != set_index
                                or not current):
                            raise ValueError("NFB 操作連位已切換，請重新選擇")
                        live = get_nfb_transaction_ports()
                        current_state = live["state"](
                            set_index, current[0], current,
                        )
                        if action == "submit":
                            if len(current) != 1 or not current_state.get("can_submit"):
                                raise ValueError(
                                    current_state.get("reason")
                                    or "目前沒有可提交的 NFB 交易證據，請先完成來源核對"
                                )
                            changed = live["submit"](
                                set_index, current, nfb_confirm,
                            )
                        elif action == "copy":
                            if len(current) != 2 or not current_state.get("can_copy"):
                                raise ValueError(
                                    "NFB 複製必須高亮恰好兩連，"
                                    "且目標連已獨立核對實體世界 X／來源"
                                )
                            changed = live["copy"](
                                set_index, current, nfb_confirm,
                            )
                        elif action == "restore":
                            if not all(live["state"](
                                set_index, bi, current,
                            ).get("can_restore") for bi in current):
                                raise ValueError("只有已提交 NFB 的連可以還原")
                            changed = live["restore"](
                                set_index, current, nfb_confirm,
                            )
                        elif action == "undo":
                            if not current_state.get("can_undo"):
                                raise ValueError("目前沒有可復原的 NFB 提交")
                            if not messagebox.askyesno(
                                "NFB Undo", "確定復原上一次 NFB 交易？",
                                parent=win,
                            ):
                                return
                            live["undo"]()
                            changed = True
                        else:
                            raise ValueError("未知 NFB 交易")
                        if changed:
                            render()
                        # A successful commit changes the live can_submit,
                        # can_copy, can_restore and can_undo guards. Rebuild
                        # the visible controls immediately; otherwise old
                        # enabled actions survive while their proof is gone.
                        show_setting_controls()
                    except (ValueError, TypeError, KeyError, IndexError,
                            RuntimeError, OSError) as exc:
                        warn(exc)

                for label, action, enabled in (
                    ("確認套用 NFB", "submit",
                     len(highlighted) == 1 and status.get("can_submit", False)),
                    ("複製至其他連", "copy",
                     len(highlighted) == 2 and status.get("can_copy", False)),
                    ("還原為未配置", "restore", all_submitted),
                    ("復原上次 NFB 操作", "undo",
                     status.get("can_undo", False)),
                ):
                    ttk.Button(
                        nfb_row, text=label,
                        command=lambda action=action: run_nfb_transaction(action),
                        state="normal" if enabled else "disabled",
                    ).pack(side="left", padx=(0, 4))
                if (len(highlighted) == 1
                        and not status.get("can_submit")
                        and not status.get("submitted")
                        and status.get("reason")):
                    ttk.Label(
                        settings_host, text=status["reason"],
                        wraplength=570, justify="left",
                    ).pack(anchor="w")
            # #1501: ONLY a genuinely READY current highlighted Set/Bay
            # gets the explicit partial manufacturing action. The existing
            # physical writer is still revalidated after folder selection.
            if get_nfb_transaction_ports is not None and applied["selected_bays"]:
                from .receiving_nfb_partial_batch_dispatcher import (
                    require_highlighted_nfb_inner_doors,
                    export_highlighted_nfb_inner_doors,
                )
                try:
                    nfb_ports = get_nfb_transaction_ports()
                    require_highlighted_nfb_inner_doors(
                        nfb_ports, set_index, targets(), allow_held=True,
                    )
                except (ValueError, TypeError, KeyError, IndexError, OSError):
                    pass  # Do not display an enabled button without live proof.
                else:
                    def export_nfb_partial():
                        try:
                            if (applied["mode"] != "set_bay"
                                    or applied["set_index"] != set_index):
                                raise ValueError("NFB 匯出套位已切換，請重新選擇")
                            # Selection and source are independently refreshed
                            # on click, not authorized by the rendered button.
                            current = tuple(applied["selected_bays"])
                            live_ports = get_nfb_transaction_ports()
                            require_highlighted_nfb_inner_doors(
                                live_ports, set_index, current, allow_held=True,
                            )
                            from tkinter import filedialog
                            folder = filedialog.askdirectory(
                                title="選擇 NFB 已驗證內門部分 DXF 資料夾",
                                parent=win,
                            )
                            if not folder:
                                return
                            completed = export_highlighted_nfb_inner_doors(
                                live_ports, set_index=set_index,
                                bay_indices=current, output_directory=folder, allow_held=True,
                            )
                            messagebox.showinfo(
                                "NFB 部分 DXF",
                                f"已輸出 {len(completed)} 片已驗證內門。"
                                "受阻連未輸出，詳見同批部分匯出清單。"
                                 "中／底板、PAD／EAR 和整箱尚未放行。",
                                parent=win,
                            )
                        except (ValueError, TypeError, IndexError,
                                KeyError, RuntimeError, OSError) as exc:
                            warn(exc)
                    ttk.Button(
                        settings_host,
                        text="輸出已驗證內門 DXF（僅部分）",
                        command=export_nfb_partial,
                    ).pack(anchor="e", pady=(5, 0))
            # #1502: this current physical-Bay action atomically exports a verified
            # inner-door + Base Plate pair, instead of separate half-products.
            # It is displayed only for one already-submitted NFB Bay with
            # a selected real Receiving physical Base Plate; it never grants
            # whole-box or EAR-Z/PAD manufacturing.
            if (get_nfb_transaction_ports is not None
                    and applied["mode"] == "set_bay"
                    and len(applied["selected_bays"]) == 1):
                chosen_bay = applied["selected_bays"][0]
                try:
                    base_ports = get_nfb_transaction_ports()
                    base_ready = bool(
                        base_ports["state"](set_index, chosen_bay).get("base_partial_ready")
                    )
                except (ValueError, TypeError, KeyError, IndexError, OSError):
                    base_ready = False
                if base_ready:
                    def export_nfb_paired_partial():
                        try:
                            if (applied["mode"] != "set_bay"
                                    or applied["set_index"] != set_index
                                    or tuple(applied["selected_bays"]) != (chosen_bay,)):
                                raise ValueError("NFB 底板輸出連位已切換，請重新選擇")
                            live_ports = get_nfb_transaction_ports()
                            if not live_ports["state"](
                                set_index, chosen_bay
                            ).get("base_partial_ready"):
                                raise ValueError("NFB 底板實體選型／提交驗證已失效")
                            from tkinter import filedialog
                            folder = filedialog.askdirectory(
                                title="選擇 NFB 內門＋底板成對 DXF 資料夾",
                                parent=win,
                            )
                            if not folder:
                                return
                            paired = live_ports["pair_partial_export"](
                                set_index, chosen_bay, folder,
                            )
                            messagebox.showinfo(
                                "NFB 內門＋底板部分 DXF",
                                "已原子輸出並驗證內門：" + paired.inner_door_path
                                + "；實體底板：" + "、".join(
                                    getattr(paired, "base_plate_paths", ())
                                    or (getattr(paired, "base_plate_path", ""),)
                                )
                                + "。耳朵焊接 Z、PAD／EAR 與整箱 MFG-2 尚未放行。"
                                + ("\n" + paired.verified_v5_scope.operator_label
                                   if getattr(paired, "verified_v5_scope", None) is not None
                                   else ""),
                                parent=win,
                            )
                        except (ValueError, TypeError, IndexError,
                                KeyError, RuntimeError, OSError) as exc:
                            warn(exc)
                    ttk.Button(
                        settings_host,
                        text="輸出內門＋底板 DXF（成對部分）",
                        command=export_nfb_paired_partial,
                    ).pack(anchor="e", pady=(5, 0))
            # #1501 operator disclosure: show the REAL per-part live result,
            # including blocked Bays and source reasons, not a fabricated
            # green checkbox. No widget at all for fully legacy selections.
            if get_nfb_transaction_ports is not None and applied["selected_bays"]:
                from .receiving_nfb_manifest_view import (
                    highlighted_nfb_manifest_lines,
                )
                try:
                    report_lines = highlighted_nfb_manifest_lines(
                        get_nfb_transaction_ports(), set_index, targets(),
                    )
                except (ValueError, TypeError, KeyError,
                        IndexError, OSError) as exc:
                    report_lines = ("NFB 板件狀態不可用：" + str(exc),)
                if report_lines:
                    report_host = ttk.LabelFrame(
                        settings_host, text="NFB 板件清單（唯讀）",
                    )
                    report_host.pack(fill="x", pady=(6, 0))
                    for item in report_lines:
                        ttk.Label(
                            report_host, text=item, wraplength=580,
                            justify="left",
                        ).pack(anchor="w", padx=6, pady=1)
            # Switch configuration belongs to the separate version editor.
            manager_widgets.update(frame=None, label=None, buttons=(),
                                   buttons_frame=None, quantity_frame=None)

    def close_manager():
        nonlocal quantity_ui
        pending_redraw = manager_widgets.get("redraw_queue")
        if pending_redraw is not None:
            pending_redraw.cancel()
        manager_widgets["redraw_queue"] = None
        manager = manager_window["win"]
        if manager is None or not manager.winfo_exists():
            manager_window["win"] = None
            quantity_ui = None
            return
        if manager.grab_current() is manager:
            manager.grab_release()
        manager_window["win"] = None
        quantity_ui = None
        manager.destroy()
        manager_widgets.update(frame=None, label=None, buttons=(),
                               buttons_frame=None, quantity_frame=None, canvas=None)
        if win.winfo_exists():
            if win.grab_current() is None:
                win.grab_set()
            win.lift()
            win.focus_set()

    def refresh_manager_controls():
        manager = manager_window["win"]
        title = manager_widgets["label"]
        if (manager is None or not manager.winfo_exists() or
                title is None or not title.winfo_exists()):
            return
        role = manager_state["role"]
        chosen = candidate_selected[role]
        title.configure(text=({"head": "封頭孔", "tail": "封尾孔",
                               "inner-door": "內門"}[role])
                        + "｜" + ("即時" if chosen is None else version_label(chosen)))
        buttons = manager_widgets["buttons"]
        for button in buttons:
            button.configure(state="normal" if chosen is not None else "disabled")
        if len(buttons) == 3:
            buttons[1].configure(text="複製到封尾" if role == "head" else "複製到封頭")
        candidate_frame = manager_widgets["buttons_frame"]
        quantity_frame = manager_widgets["quantity_frame"]
        if quantity_ui is not None and manager_state["page"] == "quantity":
            candidate_frame.pack_forget()
            quantity_frame.pack(anchor="w", fill="x", pady=(8, 3))
            quantity_ui.show(quantity_frame, role)
        else:
            if quantity_frame is not None:
                quantity_frame.pack_forget()
            if candidate_frame is not None:
                candidate_frame.pack(anchor="w", pady=(8, 3))
        render_manager_diagram()

    def render_manager_diagram():
        manager = manager_window["win"]
        if manager is None or not manager.winfo_exists():
            return
        diagram = manager_widgets["canvas"]
        if diagram is None:
            return
        if (quantity_ui is not None and manager_state["page"] == "quantity" and
                quantity_ui.draft.step[manager_state["role"]] == 2):
            if not diagram.master.winfo_manager():
                diagram.master.pack(fill="both", expand=True, pady=(12, 0))
            quantity_ui.paint()
            redraw_queue = manager_widgets.get("redraw_queue")
            if redraw_queue is not None:
                redraw_queue.mark_drawn()
        else:
            diagram.master.pack_forget()

    def open_manager(family="endcap"):
        nonlocal quantity_ui
        source = (get_inner_candidate_ports if family == "inner"
                  else get_candidate_ports)
        if source is None:
            return
        old = manager_window["win"]
        if old is not None and old.winfo_exists():
            old.lift()
            old.focus_set()
            return old
        manager_state["family"] = family
        manager_state["role"] = ("inner-door" if family == "inner"
                                 else manager_state["role"]
                                 if manager_state["role"] in ("head", "tail")
                                 else "head")
        manager_state["page"] = "candidates"
        manager = tk.Toplevel(win)
        manager.title("內門版本管理" if family == "inner" else "版本管理")
        manager.transient(win)
        manager.geometry("960x720")
        manager.minsize(570, 350)
        manager_window["win"] = manager
        manager.protocol("WM_DELETE_WINDOW", close_manager)

        manager_scroll, manager_content, manager_viewport = make_scrollable_frame(
            manager, tk=tk, ttk=ttk, width=920, height=660,
        )
        manager_scroll.pack(fill="both", expand=True)
        body = ttk.Frame(manager_content, padding=14)
        body.pack(fill="both", expand=True)
        manager._receiving_manager_scroll = manager_scroll
        top = ttk.Frame(body)
        top.pack(anchor="nw", fill="x")

        role_var = tk.StringVar(master=manager, value=manager_state["role"])
        page_var = tk.StringVar(master=manager, value=manager_state["page"])
        def choose_role():
            manager_state["role"] = role_var.get()
            refresh_manager_controls()
        def choose_page():
            manager_state["page"] = page_var.get()
            refresh_manager_controls()
        if family == "inner":
            ttk.Label(top, text="內門").pack(side="left")
        else:
            for label, value in (("封頭孔", "head"), ("封尾孔", "tail")):
                ttk.Radiobutton(
                    top, text=label, value=value, variable=role_var,
                    command=choose_role,
                ).pack(side="left", padx=(0, 14))
        tabs = ttk.Frame(body)
        tabs.pack(anchor="nw", pady=(10, 0))
        for label, value in (("候選版本", "candidates"), ("數量配置", "quantity")):
            ttk.Radiobutton(
                tabs, text=label, value=value, variable=page_var,
                command=choose_page,
            ).pack(side="left", padx=(0, 14))
        title = ttk.Label(body, text="")
        title.pack(anchor="nw", pady=(10, 0))
        buttons = ttk.Frame(body)
        actions_map = []
        menu_actions = ([("複製為新版本", "same"),
                         ("刪除目前版本", "delete")] if family == "inner"
                        else [("複製為新版本", "same"),
                              ("複製到另一側", "other"),
                              ("刪除目前版本", "delete")])
        for label, action in menu_actions:
            control = ttk.Button(
                buttons, text=label,
                command=lambda action=action: manage_action(action),
            )
            control.pack(side="left", padx=(0, 6))
            actions_map.append(control)
        quantity_frame = ttk.Frame(body)

        # The only all-Set quantity sketch belongs to this child window.
        # Main-window 2D retains its normal per-Bay highlight and click owner.
        diagram_host = ttk.Frame(body, padding=8, relief="groove", borderwidth=1)
        diagram_host.columnconfigure(0, weight=1)
        diagram_host.rowconfigure(0, weight=1)
        diagram = tk.Canvas(
            diagram_host, width=800, height=380, background="#1a2734",
            highlightthickness=0,
        )
        diagram.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(diagram_host, orient="vertical", command=diagram.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        diagram.configure(yscrollcommand=scrollbar.set)
        from .receiving_quantity_allocation_ui import ReceivingQuantityAllocationUI
        quantity_ui = ReceivingQuantityAllocationUI(
            manager, diagram,
            get_counts=lambda: tuple(get_switch().connection_counts()),
            get_ports=source,
            get_marks=get_original_door_marks,
            roles=("inner-door",) if family == "inner" else ("head", "tail"),
            validate_role=(lambda role: role if role == "inner-door"
                           else (_ for _ in ()).throw(ValueError("內門權責錯誤")))
                          if family == "inner" else None,
            on_render=render_manager_diagram,
            warn=warn,
        )
        diagram.bind("<Button-1>", quantity_ui.click)
        manager_redraw = _IdleCanvasRedraw(diagram, render_manager_diagram)
        manager_widgets["redraw_queue"] = manager_redraw
        diagram.bind("<Configure>", manager_redraw.request)
        def scroll_quantity(event):
            if manager_state["page"] != "quantity":
                return
            direction = (-1 if getattr(event, "delta", 0) > 0 or
                         getattr(event, "num", 0) == 4 else 1)
            diagram.yview_scroll(direction, "units")
            return "break"
        diagram.bind("<MouseWheel>", scroll_quantity)
        diagram.bind("<Button-4>", scroll_quantity)
        diagram.bind("<Button-5>", scroll_quantity)
        manager_widgets.update(
            frame=body, label=title, buttons=tuple(actions_map),
            buttons_frame=buttons, quantity_frame=quantity_frame,
            canvas=diagram,
        )
        manager._receiving_quantity_ui = quantity_ui
        manager._receiving_manager_state = manager_state
        manager._receiving_manager_canvas = diagram
        manager._receiving_manager_buttons = tuple(actions_map)
        manager._receiving_manager_page_var = page_var
        manager._receiving_manager_tabs = tabs
        manager._receiving_manager_role_var = role_var
        refresh_manager_controls()
        if win.grab_current() is win:
            win.grab_release()
        manager.grab_set()
        manager.lift()
        manager.focus_set()
        return manager

    def manage_action(action):
        role = manager_state["role"]
        selected_id = candidate_selected[role]
        source = (get_inner_candidate_ports if role == "inner-door"
                  else get_candidate_ports)
        if selected_id is None or source is None:
            return
        try:
            library = source()
            if action == "delete":
                if not messagebox.askyesno(
                    "刪除候選版本", "確定刪除此候選版本？已套用到板件的孔位不會刪除。",
                    parent=manager_window["win"],
                ):
                    return
                library["delete"](role, selected_id)
                candidate_selected[role] = None
            else:
                if role == "inner-door" and action == "other":
                    raise ValueError("內門不能複製到封頭尾")
                destination = role if action == "same" else (
                    "tail" if role == "head" else "head"
                )
                created = library["copy"](role, selected_id, destination)
                candidate_selected[destination] = created
                manager_state["role"] = destination
                window = manager_window["win"]
                if window is not None and window.winfo_exists():
                    window._receiving_manager_role_var.set(destination)
            if win.winfo_exists():
                win.after_idle(show_setting_controls)
                win.after_idle(refresh_manager_controls)
        except (ValueError, IndexError, RuntimeError) as exc:
            warn(exc)

    def warn(exc):
        messagebox.showwarning(title, str(exc), parent=win)
        return False

    def ensure_set_mode():
        if get_snapshot().get("active_mode", "set_bay") != "set_bay":
            if not switch_mode("set_bay"):
                return False
        return True

    mark_cache = {"key": None, "values": ()}
    size_cache = {"set_index": None, "dimensions": ()}

    def render():
        # The main sketch always remains a Set/Bay highlighter. Quantity
        # allocation uses the separate version-manager window's own canvas.
        canvas.configure(scrollregion=(0, 0, 0, 0))
        canvas.yview_moveto(0)
        count = applied["count"] if applied["mode"] == "set_bay" else 1
        selected = applied["selected_bays"] if applied["mode"] == "set_bay" else None
        marks = ()
        if (applied["mode"] in ("set_bay", "quantity")
                and applied["set_index"] is None
                and get_initial_door_marks is not None):
            marks = tuple(get_initial_door_marks() or ())
        if (applied["mode"] == "set_bay"
                and applied["set_index"] is not None
                and get_original_door_marks is not None):
            set_index = applied["set_index"]
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
        labels = ()
        if (applied["mode"] == "set_bay" and
                applied["set_index"] is not None and
                get_applied_version_labels is not None):
            labels = get_applied_version_labels(applied["set_index"])
        # Geometry dimensions are cached per applied Set. Canvas Configure
        # redraws can fire repeatedly; don't deep-copy the complete Receiving
        # layout (including switch/NFB payloads) on every pixel resize.
        if (applied["set_index"] is not None and applied["mode"] == "set_bay"
                and size_cache["set_index"] != applied["set_index"]):
            source = get_switch()
            layout = getattr(source, "layout", None)
            size_cache["dimensions"] = (
                tuple(layout["sets"][applied["set_index"]]["bays"])
                if layout is not None else ()
            )
            size_cache["set_index"] = applied["set_index"]
        paint_connected_bays(canvas, count, selected, marks, labels,
                             bay_dimensions=size_cache["dimensions"])
        canvas._receiving_selected_bay = (
            applied["selected"] if applied["mode"] == "set_bay" else None
        )
        # A direct highlight/mode paint supersedes a queued same-size
        # Configure callback; a future physical size change is still painted.
        sketch_redraw.mark_drawn()

    size_input = {}
    size_controls = {"single": None}

    def input_dimensions(values):
        import re
        parsed = {}
        for name, label in (("width", "W"), ("height", "H"), ("depth", "D"), ("count", "數量")):
            raw = values[name].get().strip()
            if re.fullmatch(r"[0-9]+", raw) is None or int(raw) <= 0:
                raise ValueError(f"{label} 必須為正整數")
            parsed[name] = int(raw)
        return parsed

    def refresh_dimension_rows():
        for widget in size_groups_host.winfo_children():
            widget.destroy()
        for widget in confirmed_groups_host.winfo_children():
            widget.destroy()
        if single_mode or applied["set_index"] is None or get_dimension_group is None:
            return
        set_index = applied["set_index"]
        layout = get_switch().layout
        bays = layout["sets"][set_index]["bays"]
        size_cache.update(set_index=set_index, dimensions=tuple(bays))
        ttk.Label(
            confirmed_groups_host, text=f"第{set_index + 1}套｜已確定尺寸／數量",
        ).pack(anchor="w")
        group_table = ttk.Frame(confirmed_groups_host)
        group_table.pack(anchor="w", pady=4)
        for column, label in enumerate(("W", "H", "D", "數量")):
            ttk.Label(group_table, text=label, width=7).grid(
                row=0, column=column, padx=2,
            )
        for row_index, (dimensions, indices) in enumerate(dimension_group_summary(bays), start=1):
            for column, text in enumerate((*dimensions, len(indices))):
                ttk.Label(
                    group_table, text=display_dimension(text), width=7,
                ).grid(row=row_index, column=column, padx=2, pady=1)
        ttk.Label(size_groups_host, text="其他尺寸：高亮右圖相對箱體，再輸入尺寸及數量").pack(anchor="w")
        entry_row = ttk.Frame(size_groups_host)
        entry_row.pack(anchor="w", pady=3)
        if not size_input:
            from ae_engine.cabinet_types.receiving import BOX_BODY_DEFAULTS
            size_input.update({
                key: tk.StringVar(master=win, value=display_dimension(BOX_BODY_DEFAULTS[axis]))
                for key, axis in (("width", "w"), ("height", "h"), ("depth", "d"))
            })
            size_input["count"] = tk.StringVar(master=win, value="1")
        for label, key in (("W", "width"), ("H", "height"), ("D", "depth"), ("數量", "count")):
            ttk.Label(entry_row, text=label).pack(side="left", padx=(2, 0))
            ttk.Entry(entry_row, textvariable=size_input[key], width=6).pack(side="left", padx=2)
        ttk.Button(entry_row, text="確定", command=confirm_dimension_group).pack(side="left", padx=4)
        # No duplicate selected-count message below the size entry row.

    # Tracks EXPLICIT confirmations, not "non-default" sizes. A confirmed
    # 800x1600x350 Bay is configured, too; no extra project data is invented.
    confirmed_indices_by_set = {}

    def confirm_dimension_group():
        if applied["set_index"] is None or get_dimension_group is None:
            return
        try:
            dims = input_dimensions(size_input)
            indices = tuple(applied["selected_bays"])
            if len(indices) != dims["count"]:
                raise ValueError(f"請在右側圖面高亮剛好 {dims['count']} 個箱體")
            set_index = applied["set_index"]
            get_dimension_group(
                set_index, indices,
                dims["width"], dims["height"], dims["depth"], dims["count"],
            )
            confirmed = confirmed_indices_by_set.setdefault(set_index, set())
            confirmed.update(indices)
            # Drop the whole old multi-selection. Focus exactly the next Bay
            # that has NOT been explicitly confirmed during this edit session.
            count = len(get_switch().layout["sets"][set_index]["bays"])
            next_index = next((
                candidate
                for step in range(1, count + 1)
                for candidate in ((max(indices) + step) % count,)
                if candidate not in confirmed
            ), None)
            applied.update(selected=None, selected_bays=())
            if next_index is not None:
                applied.update(selected=next_index, selected_bays=(next_index,))
                if select_bay is not None:
                    select_bay(set_index, next_index)
            # Recompute the committed grouping from canonical per-Bay W/H/D.
            refresh_dimension_rows()
            if next_index is not None:
                bay = get_switch().layout["sets"][set_index]["bays"][next_index]
                for field in ("width", "height", "depth"):
                    size_input[field].set(display_dimension(bay[field]))
                size_input["count"].set("1")
            render()
            return True
        except (ValueError, IndexError, RuntimeError) as exc:
            warn(exc)
            return False

    def refresh_single_dimensions():
        if get_single_size_quantity is None:
            return
        values = get_single_size_quantity()
        for key in ("width", "height", "depth", "count"):
            size_input[key].set(display_dimension(values[key]))
        size_controls["status"].set(
            f"總數量 {values['total_count']}"
        )

    def confirm_single_dimensions():
        if set_single_size_quantity is None:
            return
        try:
            dims = input_dimensions(size_input)
            set_single_size_quantity(
                dims["width"], dims["height"], dims["depth"], dims["count"],
            )
            refresh_single_dimensions()
        except (ValueError, IndexError, RuntimeError) as exc:
            warn(exc)

    def build_single_dimensions():
        if size_controls["single"] is not None:
            return
        root = ttk.LabelFrame(size_groups_host, text="單只｜尺寸與數量", padding=8)
        root.pack(anchor="w", fill="x")
        size_controls["single"] = root
        size_controls["status"] = tk.StringVar(master=win)
        if get_single_size_quantity is None:
            ttk.Label(root, text="單只尺寸來源尚未連接").pack(anchor="w")
            return
        entry_row = ttk.Frame(root)
        entry_row.pack(anchor="w")
        values = get_single_size_quantity()
        for key, label in (("width", "W"), ("height", "H"), ("depth", "D"), ("count", "數量")):
            ttk.Label(entry_row, text=label).pack(side="left", padx=(2, 0))
            size_input[key] = tk.StringVar(master=win, value=display_dimension(values[key]))
            ttk.Entry(entry_row, textvariable=size_input[key], width=7).pack(side="left", padx=3)
        ttk.Button(entry_row, text="確定", command=confirm_single_dimensions).pack(side="left", padx=4)
        ttk.Label(root, textvariable=size_controls["status"]).pack(anchor="w", pady=4)
        refresh_single_dimensions()

    # Retain button identity while a +連/−連 callback is executing.
    # Destroying its own Tk button mid-invoke is a first-click freeze risk.
    bay_rows = []

    def refresh_rows():
        if single_mode:
            set_actions.pack_forget()
            for entry in bay_rows:
                entry["frame"].destroy()
            bay_rows.clear()
            build_single_dimensions()
            return
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
                side="left", padx=(0, 4))
            minus = ttk.Button(row, text="－連", width=3,
                               command=lambda i=index: resize(i, -1))
            minus.pack(side="left", padx=(0, 2))
            count_label = ttk.Label(row, width=2, anchor="center")
            count_label.pack(side="left", padx=(0, 2))
            plus = ttk.Button(row, text="＋連", width=3,
                              command=lambda i=index: resize(i, 1))
            plus.pack(side="left", padx=(0, 2))
            apply_button = ttk.Button(row, text="套用", width=4,
                                      command=lambda i=index: apply(i))
            apply_button.pack(side="left")
            bay_rows.append({"frame": row, "count": count_label})
        for entry, count in zip(bay_rows, counts):
            entry["count"].configure(text=str(count))
        for index, count in enumerate(counts):
            confirmed_indices_by_set.setdefault(index, set()).intersection_update(
                range(count)
            )
        for index in tuple(confirmed_indices_by_set):
            if index >= len(counts):
                del confirmed_indices_by_set[index]
        # Topology invalidates an in-progress child-window allocation.
        # Schedule after idle so the invoking +連 button remains alive.
        if quantity_ui is not None and manager_window["win"] is not None:
            quantity_ui.reconcile()
            if manager_state["page"] == "quantity":
                win.after_idle(quantity_ui.draw_controls)
                win.after_idle(render_manager_diagram)

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
                if applied["set_index"] is not None:
                    refresh_dimension_rows()
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
            # Existing contract: +連/−連 changes canonical topology, but
            # the operator's sketch is projected only after 套用.
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
            refresh_dimension_rows()
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
                    if index in selected_bays:
                        selected_bays.remove(index)
                        active = min(selected_bays) if selected_bays else None
                    else:
                        selected_bays.add(index)
                        active = index
                    if active is not None and select_bay is not None:
                        select_bay(applied["set_index"], active)
                    applied["selected"] = active
                    applied["selected_bays"] = tuple(sorted(selected_bays))
                    if selected_setting["kind"] is not None and active is not None:
                        if on_setting_selected is not None:
                            on_setting_selected(applied["set_index"], active,
                                                selected_setting["kind"])
                        selected_setting.update(
                            set_index=applied["set_index"], bay_index=active
                        )
                    # Keep the last browsed Bay as the read-only context if
                    # everything is unhighlighted; never turn it into a target.
                    if active is None and selected_setting["kind"] is not None:
                        selected_setting.update(
                            set_index=applied["set_index"], bay_index=index
                        )
                    show_setting_controls()
                    render()
                except (ValueError, IndexError, RuntimeError) as exc:
                    warn(exc)
                return

    mode_transition = {"busy": False}

    def change_mode():
        target = mode_var.get()
        if mode_transition["busy"]:
            mode_var.set(applied["mode"])
            return
        if target == applied["mode"]:
            return
        mode_transition["busy"] = True
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
        finally:
            mode_transition["busy"] = False

    # No main mode radio buttons: this window edits Set/Bay only.
    # The Version Manager still owns its separate 數量配置 page.

    canvas.bind("<Button-1>", click_bay)
    sketch_redraw = _IdleCanvasRedraw(canvas, render)
    canvas.bind("<Configure>", sketch_redraw.request)
    refresh_rows()
    render()

    # Test hooks are presentation state only, not product data authority.
    win._receiving_multi_brand_var = brand_var
    win._receiving_multi_brand_selector = brand_selector
    win._receiving_multi_set_buttons = (minus_set, plus_set)
    win._receiving_multi_candidate_selected = candidate_selected
    win._receiving_multi_candidate_combos = candidate_combos
    win._receiving_multi_real_preview = real_preview
    win._receiving_multi_show_real_preview = show_real_preview
    win._receiving_multi_close_real_preview = close_real_preview
    win._receiving_multi_manager_state = manager_state
    win._receiving_multi_manager_window = manager_window
    win._receiving_multi_open_manager = open_manager
    win._receiving_multi_close_manager = close_manager
    win._receiving_multi_settings_host = settings_host
    win._receiving_multi_left_host = left_host
    win._receiving_multi_left_scroll = left_scroll
    win._receiving_multi_function_scroll = function_scroll
    win._receiving_multi_right_host = right_host
    win._receiving_multi_function_host = function_host
    win._receiving_multi_diagram_host = diagram_host
    win._receiving_multi_mode_var = mode_var
    win._receiving_multi_mode_controls = mode_row
    win._receiving_multi_rows_host = actions_host
    win._receiving_dimension_groups_host = size_groups_host
    win._receiving_confirmed_groups_host = confirmed_groups_host
    win._receiving_confirmed_indices = confirmed_indices_by_set
    win._receiving_dimension_group_input = size_input
    win._receiving_dimension_group_confirm = confirm_dimension_group
    win._receiving_multi_setting_list = setting_list
    win._receiving_multi_selected_setting = selected_setting
    win._receiving_multi_canvas = canvas
    win._receiving_multi_applied = applied
    win._receiving_multi_refresh = refresh_rows
    win._receiving_multi_apply = apply
    return win
