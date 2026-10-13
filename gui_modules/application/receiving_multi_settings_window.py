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


def paint_connected_bays(canvas, count, selected=None, door_marks=None, version_labels=None):
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


def open_multi_settings(parent, *, get_snapshot, get_switch, switch_mode,
                        resize_connections, resize_sets=None,
                        get_candidate_ports=None, get_inner_candidate_ports=None,
                        select_bay=None,
                        on_setting_selected=None, get_brand=None,
                        set_brand=None, get_settings_ports=None,
                        get_nfb_transaction_ports=None,
                        get_original_door_marks=None,
                        get_applied_version_labels=None,
                        get_real_cut_preview_request=None,
                        on_close=None, on_brand_close=None):
    """Full-screen modal Receiving operator UI with no unsolicited widgets."""
    old = getattr(parent, "_receiving_multi_settings_window", None)
    if old is not None and old.winfo_exists():
        old.lift()
        old.focus_set()
        return old

    win = tk.Toplevel(parent)
    win.title("多只設定")
    # The primary application is not interactive while multi-settings is open.
    win.transient(parent)
    parent._receiving_multi_settings_window = win
    topology_changed = {"value": False}
    brand_changed = {"value": False}

    def close():
        close_real_preview()
        close_manager()
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
    right_host.rowconfigure(1, weight=1)

    # Reflect the authoritative mode instead of deferring a hidden mode switch
    # (and its complete geometry rebuild) to the first connection edit.
    initial_mode = get_snapshot().get("active_mode", "set_bay")
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
            try:
                if set_brand(brand_var.get()):
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
    minus_set.pack(side="left", padx=(0, 3))
    plus_set = ttk.Button(
        set_actions, text="＋套", width=5, command=lambda: adjust_sets(1)
    )
    plus_set.pack(side="left")

    applied = {"set_index": None, "count": 1, "selected": None,
               "selected_bays": (), "mode": initial_mode}

    # Right TOP: original Listbox and its selected category controls.
    # Right BOTTOM: the independent diagram region, never commandeered
    # by quantity version management.
    function_scroll, function_content, function_scroll_canvas = make_scrollable_frame(
        right_host, tk=tk, ttk=ttk, width=610, height=250,
    )
    function_scroll.grid(row=0, column=0, sticky="new")
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
    diagram_host.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
    diagram_host.columnconfigure(0, weight=1)
    diagram_host.rowconfigure(0, weight=1)
    canvas = tk.Canvas(diagram_host, width=525, height=310, background="#1a2734",
                       highlightthickness=0)
    canvas.grid(row=0, column=0, sticky="nsew")

    rows_host = ttk.Frame(left_host)
    rows_host.pack(anchor="nw", pady=(8, 0))
    actions_host = ttk.Frame(rows_host)
    actions_host.pack(anchor="w")
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
            if (real_preview["generation"] != generation or
                    not popup.winfo_exists()):
                return
            try:
                request = get_real_cut_preview_request(role, selected_id, si, bi)
                if request is None:
                    raise ValueError("此版本缺少可驗證的實體幾何來源")
                real_preview["view"].draw_geometry((request,))
                popup._receiving_real_preview_request = request
                real_preview["status"].set(
                    f"第{si+1}套／第{bi+1}連｜{label}｜實際 FinalScene 投影；滾輪縮放／中鍵平移"
                )
            except Exception as exc:
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
        # The canvas highlight, including an empty selection, is the ONLY apply target.
        targets = lambda: tuple(applied["selected_bays"])
        def perform(action):
            try:
                action()
                show_setting_controls()
            except (ValueError, IndexError, RuntimeError) as exc:
                warn(exc)
        candidate_combos.clear()

        def actions(parent, kind, *, role=None):
            row = ttk.Frame(parent)
            row.pack(anchor="w", pady=3)
            if role is None:
                from ae_engine.receiving_shared_settings import setting_value
                current = setting_value(ports["row"](), bay_index, kind)
                value = tk.StringVar(master=win, value=str(current))
                ttk.Label(row, text="內門層數").pack(side="left")
                selector = ttk.Combobox(
                    row, textvariable=value, values=("1", "2"),
                    width=5, state="readonly",
                )
                selector.pack(side="left", padx=3)
                # Previously "編輯" only committed the layer count.
                # Choosing 1/2 now applies it immediately to highlighted Bays.
                selector.bind(
                    "<<ComboboxSelected>>",
                    lambda _event: perform(
                        lambda: ports["change"](kind, int(value.get()), targets())
                    ),
                )
                return
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
                    library["edit"](
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
            actions(settings_host, "inner_door_layers")
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
            ttk.Button(
                link_row, text="解除本連連動",
                command=lambda: perform(lambda: ports["unlink"](
                    "inner_door_layers",
                )),
            ).pack(side="left")
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
                                + "；實體底板：" + paired.base_plate_path
                                + "。耳朵焊接 Z、PAD／EAR 與整箱 MFG-2 尚未放行。",
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
        diagram.bind("<Configure>", lambda _event: render_manager_diagram())
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
        messagebox.showwarning("多只設定", str(exc), parent=win)
        return False

    def ensure_set_mode():
        if get_snapshot().get("active_mode", "set_bay") != "set_bay":
            if not switch_mode("set_bay"):
                return False
        return True

    mark_cache = {"key": None, "values": ()}

    def render():
        # The main sketch always remains a Set/Bay highlighter. Quantity
        # allocation uses the separate version-manager window's own canvas.
        canvas.configure(scrollregion=(0, 0, 0, 0))
        canvas.yview_moveto(0)
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
        labels = ()
        if (applied["mode"] == "set_bay" and
                applied["set_index"] is not None and
                get_applied_version_labels is not None):
            labels = get_applied_version_labels(applied["set_index"])
        paint_connected_bays(canvas, count, selected, marks, labels)
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
    win._receiving_multi_setting_list = setting_list
    win._receiving_multi_selected_setting = selected_setting
    win._receiving_multi_canvas = canvas
    win._receiving_multi_applied = applied
    win._receiving_multi_refresh = refresh_rows
    win._receiving_multi_apply = apply
    return win
