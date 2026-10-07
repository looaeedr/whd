# -*- coding: utf-8 -*-
"""View-only builder for Receiving layer/connection controls.

The legacy filename is retained for compatibility, but operator-facing terms are
套/連. Layer/connection state is projected from receiving_switch_layout; this module owns
Tk widgets only and never owns manufacturing geometry.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable, Iterable


from ae_engine.receiving_switch_layout import RECEIVING_SWITCH_BRANDS


@dataclass(frozen=True)
class ReceivingSetBayControls:
    frame: object
    header: object
    switch_brand_var: object
    switch_brand_selector: object
    layer_host: object
    add_layer_button: object
    remove_layer_button: object


def build_receiving_set_bay_controls(
    parent,
    *,
    tk,
    ttk,
    on_switch_brand_selected: Callable[[str], object],
    on_add_layer: Callable[[], object],
    on_remove_layer: Callable[[], object],
) -> ReceivingSetBayControls:
    """Construct Receiving layer/connection shell without owning product state."""
    frame = ttk.Frame(parent)

    header = ttk.Frame(frame)
    header.pack(fill=tk.X, pady=(0, 4))
    ttk.Label(header, text="開關").pack(side=tk.LEFT, padx=(0, 6))
    switch_brand_var = tk.StringVar(master=header, value=RECEIVING_SWITCH_BRANDS[0])
    switch_brand_selector = ttk.Combobox(
        header,
        textvariable=switch_brand_var,
        values=RECEIVING_SWITCH_BRANDS,
        state="readonly",
        width=8,
    )
    switch_brand_selector.pack(side=tk.LEFT)
    switch_brand_selector.bind(
        "<<ComboboxSelected>>",
        lambda _event: on_switch_brand_selected(str(switch_brand_var.get())),
    )

    layer_host = ttk.Frame(frame)
    layer_host.pack(fill=tk.X)

    layer_actions = ttk.Frame(frame)
    layer_actions.pack(anchor=tk.W, pady=(2, 0))
    remove_layer_button = ttk.Button(
        layer_actions, text="－套", command=on_remove_layer, width=5
    )
    remove_layer_button.pack(side=tk.LEFT, padx=(0, 2))
    add_layer_button = ttk.Button(
        layer_actions, text="＋套", command=on_add_layer, width=5
    )
    add_layer_button.pack(side=tk.LEFT)

    return ReceivingSetBayControls(
        frame=frame,
        header=header,
        switch_brand_var=switch_brand_var,
        switch_brand_selector=switch_brand_selector,
        layer_host=layer_host,
        add_layer_button=add_layer_button,
        remove_layer_button=remove_layer_button,
    )


def open_receiving_layer_preview(
    parent,
    *,
    tk,
    ttk,
    layer_index: int,
    connection_count: int,
    brand: str,
    render_request,
    lock_circles=(),
    settings_ports=None,
    bay_requests=(),
    bay_request_provider=None,
) -> bool:
    """Render one layer as an interactive 3D multi-connection preview.

    Geometry always comes from the authoritative FinalScene request.  This view
    owns only presentation: native mouse rotation, zoom controls, and temporary
    part visibility filters.  It never rebuilds manufacturing holes or offsets.
    """
    index = int(layer_index)
    count = max(1, int(connection_count))
    label = str(brand)
    if render_request is None:
        raise ValueError("Receiving preview requires a FinalScene render request")

    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    from phase6_final_scene_renderer import Phase6FinalSceneRenderer
    from whd_theme import apply_mpl_dark_theme
    from types import SimpleNamespace
    import math

    win = tk.Toplevel(parent)
    win.title(f"第{index + 1}套設定")
    win.transient(parent)
    # Open the settings surface maximized. Keep a portable fallback for Tk builds
    # that do not support the Windows ``zoomed`` state.
    try:
        win.state("zoomed")
    except Exception:
        try:
            win.attributes("-zoomed", True)
        except Exception:
            win.geometry(
                f"{win.winfo_screenwidth()}x{win.winfo_screenheight()}+0+0"
            )
    try:
        win.grab_set()
    except Exception:
        pass

    body = ttk.Frame(win, padding=0)
    body.pack(fill=tk.BOTH, expand=True)
    ttk.Label(
        body, text=f"第{index + 1}套｜{count}連｜開關：{label}"
    ).pack(anchor=tk.W, pady=(0, 6))

    settings_panel = None
    if settings_ports is not None:
        settings_host = ttk.Frame(body)
        settings_host.pack(fill=tk.X)
        settings_viewport = tk.Canvas(settings_host, highlightthickness=0, height=180)
        settings_scroll_y = ttk.Scrollbar(settings_host, orient=tk.VERTICAL, command=settings_viewport.yview)
        settings_scroll_x = ttk.Scrollbar(settings_host, orient=tk.HORIZONTAL, command=settings_viewport.xview)
        settings_viewport.configure(yscrollcommand=settings_scroll_y.set, xscrollcommand=settings_scroll_x.set)
        settings_viewport.grid(row=0, column=0, sticky="nsew")
        settings_scroll_y.grid(row=0, column=1, sticky="ns")
        settings_scroll_x.grid(row=1, column=0, sticky="ew")
        settings_host.columnconfigure(0, weight=1)
        settings_content = ttk.Frame(settings_viewport)
        settings_window = settings_viewport.create_window((0, 0), window=settings_content, anchor="nw")
        settings_panel = _build_receiving_settings_editor(settings_content, tk=tk, ttk=ttk, ports=settings_ports)

        def resize_settings(event=None):
            requested = settings_content.winfo_reqwidth()
            settings_viewport.itemconfigure(settings_window, width=max(requested, settings_viewport.winfo_width()))
            settings_viewport.configure(
                scrollregion=settings_viewport.bbox("all"),
                height=min(settings_content.winfo_reqheight(), max(120, int(win.winfo_screenheight() * 0.24))),
            )

        settings_content.bind("<Configure>", resize_settings)
        settings_viewport.bind("<Configure>", resize_settings)

    figure = Figure(figsize=(10.0, 6.2), dpi=100)
    figure.subplots_adjust(left=0.0, right=1.0, bottom=0.0, top=1.0)
    ax = figure.add_subplot(111, projection="3d")
    apply_mpl_dark_theme(figure, (ax,))
    canvas = FigureCanvasTkAgg(figure, master=body)
    class AppendOnlyAxes:
        # 本視窗一次清圖後依序加入不同連的 canonical request。
        # Renderer 的單次清理不應移除前一連的真實板件與孔輪廓。
        lines = ()
        collections = ()

        def __getattr__(self, name):
            return getattr(ax, name)

    preview_renderer = Phase6FinalSceneRenderer(
        SimpleNamespace(ax3d=AppendOnlyAxes(), canvas=canvas)
    )

    for method in ("_draw_assembly_box_body_bends", "_draw_scene_bends", "_draw_box_body_structure_bends", "_draw_scene_markings", "_draw_joint_marking_world_rows", "_draw_assembly_scene_markings", "_draw_operator_dimensions", "_draw_joint_diagnostic_overlays"):
        setattr(preview_renderer, method, lambda *args, **kwargs: None)

    render_data = render_request.render_data
    source_parts = tuple(
        part for request in (tuple(bay_requests) or (render_request,))
        for part in tuple(getattr(request.render_data, "assembly_parts", ()) or ())
    )
    all_part_keys = tuple(
        dict.fromkeys(str(getattr(part, "part_key", "") or "") for part in source_parts)
    )
    all_part_keys = tuple(key for key in all_part_keys if key)

    def _visibility_group(part_key):
        key = str(part_key)
        if "box_body:divider:" in key:
            return "divider"
        if key.endswith("box_body:left_side") or "box_body:left_side:" in key:
            return "left_side"
        if key.endswith("box_body:back") or "box_body:back:" in key:
            return "back"
        if key.endswith("box_body:right_side") or "box_body:right_side:" in key:
            return "right_side"
        if "inner_door:" in key:
            return "inner_door"
        if key.startswith("door") or ":door" in key:
            return "door"
        if key.startswith("base_plate") or ":base_plate" in key:
            return "base_plate"
        if key.startswith("indicator_box") or ":indicator_box" in key:
            return "indicator_box"
        if key.startswith("indicator_door") or ":indicator_door" in key:
            return "indicator_door"
        if key == "box_body" or key.endswith(":box_body"):
            return "box_body"
        if key == "head" or key.endswith(":head"):
            return "head"
        if key == "tail" or key.endswith(":tail"):
            return "tail"
        return key

    group_members = {}
    for part_key in all_part_keys:
        group_members.setdefault(_visibility_group(part_key), []).append(part_key)

    group_labels = {
        "box_body": "箱身",
        "head": "封頭",
        "tail": "封尾",
        "door": "門",
        "base_plate": "底板",
        "indicator_box": "指示燈盒",
        "indicator_door": "指示燈小門",
        "left_side": "左側板",
        "back": "後側板",
        "right_side": "右側板",
        "divider": "中隔",
        "inner_door": "內門框",
    }
    selected_part_keys = set(all_part_keys)

    visibility = ttk.LabelFrame(body, text="顯示零件", padding=4)
    visibility.pack(fill=tk.X, pady=(0, 5))
    visibility_vars = {}

    lock_rows = tuple(lock_circles or ())

    def _draw_lock_rows():
        for row in lock_rows:
            x = float(row["x"])
            y = float(row["y"])
            z = float(row["z"])
            radius = float(row["diameter"]) / 2.0
            points = tuple(
                (
                    x,
                    y + radius * math.cos(2.0 * math.pi * step / 48.0),
                    z + radius * math.sin(2.0 * math.pi * step / 48.0),
                )
                for step in range(49)
            )
            ax.plot(
                [point[0] for point in points],
                [point[1] for point in points],
                [point[2] for point in points],
                linewidth=2.0,
                color=Phase6FinalSceneRenderer._COLORS["box_body"][1],
            )

    bay_centers = []

    def _render_preview(*, reset_view=False):
        try:
            elev, azim = float(ax.elev), float(ax.azim)
        except Exception:
            elev, azim = 22.0, -56.0
        if reset_view:
            elev, azim = 22.0, -56.0
            preview_renderer.zoom_scale = 1.0

        ax.clear()
        # 先指定 canonical 高度 Y，再設定三軸比例，避免首次繪圖交換 H/D。
        ax.view_init(elev=elev, azim=azim, vertical_axis="y")
        apply_mpl_dark_theme(figure, (ax,))
        if selected_part_keys:
            visible = (
                None
                if selected_part_keys == set(all_part_keys)
                else tuple(key for key in all_part_keys if key in selected_part_keys)
            )
            data = replace(render_data, visible_part_keys=visible)
            request = replace(render_request, render_data=data)
            requests = tuple(bay_request_provider() if bay_request_provider else bay_requests) or (request,)
            triangles = []
            bay_centers.clear()
            for bay_index, bay_request in enumerate(requests):
                bay_data = bay_request.render_data
                bay_request = replace(bay_request, render_data=replace(bay_data, visible_part_keys=visible))
                palette = Phase6FinalSceneRenderer._COLORS
                if settings_panel is not None:
                    pending = getattr(settings_panel, "_receiving_pending", ())
                    matches = getattr(settings_panel, "_receiving_matches", ())
                    if bay_index in pending:
                        preview_renderer._COLORS = {key: ("#2563eb", edge) for key, (_, edge) in palette.items()}
                    elif bay_index in matches:
                        preview_renderer._COLORS = {key: ("#a9c5e2", edge) for key, (_, edge) in palette.items()}
                    else:
                        preview_renderer._COLORS = dict(palette)
                bay_triangles = tuple(preview_renderer.render(bay_request) or ())
                triangles.extend(bay_triangles)
                if bay_triangles:
                    points = [point for tri in bay_triangles for point in tri]
                    x0, x1 = min(point[0] for point in points), max(point[0] for point in points)
                    bay_centers.append(((x0 + x1) / 2, sum(point[1] for point in points) / len(points), sum(point[2] for point in points) / len(points)))
            if triangles:
                points = [point for tri in triangles for point in tri]
                spans = []
                for coordinate, setter in enumerate((ax.set_xlim, ax.set_ylim, ax.set_zlim)):
                    lower, upper = min(point[coordinate] for point in points), max(point[coordinate] for point in points)
                    spans.append(max(upper - lower, 1.0))
                    margin = max((upper - lower) * 0.06, 1.0)
                    setter(lower - margin, upper + margin)
                ax.set_box_aspect(spans)
            triangles = tuple(triangles)
            if not triangles:
                raise ValueError("Receiving preview FinalScene mesh is empty")
            if abs(float(preview_renderer.zoom_scale or 1.0) - 1.0) > 1e-12:
                preview_renderer.scale_current_3d_limits(preview_renderer.zoom_scale)
        else:
            ax.text2D(
                0.5, 0.5, "所有零件已隱藏",
                transform=ax.transAxes, ha="center", va="center",
            )

        # Header/controls already communicate context.  Keep only physical geometry.
        for artist in list(getattr(ax, "texts", ())):
            text_value = str(getattr(artist, "get_text", lambda: "")() or "")
            if text_value != "所有零件已隱藏":
                try:
                    artist.remove()
                except Exception:
                    pass

        _draw_lock_rows()
        ax.view_init(elev=elev, azim=azim, vertical_axis="y")
        ax.set_axis_off()
        # Matplotlib 3D normally keeps a square-ish axes box even when the Tk
        # canvas grows. Reuse the FinalScene rectangular viewport helper so the
        # model fills the settings window instead of staying in a small box.
        preview_renderer.configure_3d_only_figure()
        canvas.draw_idle()

    def _toggle_group(group):
        enabled = bool(visibility_vars[group].get())
        for part_key in group_members[group]:
            if enabled:
                selected_part_keys.add(part_key)
            else:
                selected_part_keys.discard(part_key)
        _render_preview()

    for ordinal, group in enumerate(group_members, start=1):
        var = tk.BooleanVar(master=visibility, value=True)
        visibility_vars[group] = var
        ttk.Checkbutton(
            visibility,
            text=group_labels.get(group, f"零件{ordinal}"),
            variable=var,
            command=lambda group=group: _toggle_group(group),
        ).pack(side=tk.LEFT, padx=(0, 8))

    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    canvas.mpl_connect("scroll_event", preview_renderer.on_scroll)
    def pick_bay(event):
        if settings_panel is None or event.inaxes is not ax or event.x is None:
            return
        from mpl_toolkits.mplot3d import proj3d
        projected = []
        for center in bay_centers:
            x, y, _ = proj3d.proj_transform(*center, ax.get_proj())
            px, py = ax.transData.transform((x, y))
            projected.append((px - event.x) ** 2 + (py - event.y) ** 2)
        if projected:
            settings_panel._receiving_select_bay(min(range(len(projected)), key=projected.__getitem__))
    canvas.mpl_connect("button_press_event", pick_bay)

    actions = ttk.Frame(body)
    actions.pack(fill=tk.X, pady=(6, 0))

    def _zoom(direction):
        old = float(preview_renderer.zoom_scale or 1.0)
        new = preview_renderer.adjust_zoom_scale(direction)
        if abs(new - old) > 1e-12:
            preview_renderer.scale_current_3d_limits(new / old)
            canvas.draw_idle()

    ttk.Button(actions, text="放大", command=lambda: _zoom("up"), width=7).pack(
        side=tk.LEFT, padx=(0, 3)
    )
    ttk.Button(actions, text="縮小", command=lambda: _zoom("down"), width=7).pack(
        side=tk.LEFT, padx=(0, 3)
    )
    ttk.Button(
        actions, text="重設視角", command=lambda: _render_preview(reset_view=True), width=9
    ).pack(side=tk.LEFT)
    ttk.Label(actions, text="滑鼠拖曳：旋轉｜滾輪：縮放").pack(
        side=tk.LEFT, padx=(10, 0)
    )
    ttk.Button(actions, text="關閉", command=win.destroy).pack(side=tk.RIGHT)

    if settings_panel is not None:
        settings_panel._receiving_after_selection = _render_preview
    _render_preview(reset_view=True)

    # Exact GUI acceptance/readback metadata. These are presentation facts only.
    win._phase6_receiving_preview_canvas = canvas
    win._phase6_receiving_preview_connection_count = count
    win._phase6_receiving_preview_mesh_count = count
    win._phase6_receiving_preview_uses_final_scene_renderer = True
    win._phase6_receiving_preview_lock_circle_count = len(lock_rows)
    win._phase6_receiving_preview_feature_segment_count = 0
    win._phase6_receiving_preview_visibility_groups = tuple(group_members)
    win._phase6_receiving_preview_interactive_zoom = True
    return True

def refresh_receiving_layer_rows(
    controls: ReceivingSetBayControls,
    *,
    tk,
    ttk,
    connection_counts: Iterable[int],
    on_resize_connections: Callable[[int, int], object],
    on_preview: Callable[[int], object],
) -> None:
    """Render one stable operator row per layer without rebuilding unchanged Tk rows."""
    host = controls.layer_host
    counts = tuple(max(1, int(raw)) for raw in connection_counts)
    rows = list(getattr(host, "_phase6_receiving_layer_rows", ()) or ())

    # Reuse existing rows so a connection-count edit only changes text/commands;
    # it must not tear down/recreate the input surface and indirectly disturb
    # the renderer canvas.
    while len(rows) > len(counts):
        row = rows.pop()
        try:
            row["frame"].destroy()
        except Exception:
            pass

    while len(rows) < len(counts):
        row_index = len(rows)
        frame = ttk.Frame(host)
        frame.pack(fill=tk.X, pady=(0, 3))
        layer_label = ttk.Label(frame, width=7, anchor=tk.W)
        layer_label.pack(side=tk.LEFT, padx=(0, 4))
        connection_label = ttk.Label(frame, width=5, anchor=tk.W)
        connection_label.pack(side=tk.LEFT, padx=(0, 4))
        minus_button = ttk.Button(frame, text="－連", width=5)
        minus_button.pack(side=tk.LEFT, padx=(0, 2))
        plus_button = ttk.Button(frame, text="＋連", width=5)
        plus_button.pack(side=tk.LEFT, padx=(0, 4))
        preview_button = ttk.Button(frame, text="設定", width=6)
        preview_button.pack(side=tk.LEFT)
        rows.append(
            {
                "frame": frame,
                "layer_label": layer_label,
                "connection_label": connection_label,
                "minus_button": minus_button,
                "plus_button": plus_button,
                "preview_button": preview_button,
                "layer_index": row_index,
            }
        )

    for layer_index, (row, connection_count) in enumerate(zip(rows, counts)):
        row["layer_index"] = layer_index
        row["layer_label"].configure(text=f"第{layer_index + 1}套")
        row["connection_label"].configure(text=f"{connection_count}連")
        row["minus_button"].configure(
            command=lambda layer_index=layer_index: on_resize_connections(layer_index, -1)
        )
        row["plus_button"].configure(
            command=lambda layer_index=layer_index: on_resize_connections(layer_index, 1)
        )
        row["preview_button"].configure(
            command=lambda layer_index=layer_index: on_preview(layer_index)
        )

    controls.remove_layer_button.configure(
        state=("normal" if len(counts) > 1 else "disabled")
    )
    host._phase6_receiving_layer_rows = tuple(rows)


def _build_receiving_settings_editor(parent, *, tk, ttk, ports):
    """以中文序號選連；選取與待套用狀態只存在此 presentation。"""
    from ae_engine.receiving_shared_settings import setting_value
    from tkinter import messagebox
    panel = ttk.LabelFrame(parent, text="每連設定", padding=6)
    panel.pack(fill=tk.X, pady=(0, 6))
    row = ports["row"]()
    active = tk.IntVar(master=panel, value=0)
    pending = set()
    selection = ttk.Frame(panel)
    selection.pack(fill=tk.X)
    selectors = []
    kind_labels = {"背板": "back_panel_mode", "封頭孔": "head_features", "封尾孔": "tail_features", "內門層數": "inner_door_layers"}
    kind_var = tk.StringVar(master=panel, value="背板")
    mode_labels = {"全板": "FULL", "半截": "HALF", "背開孔": "BACK_OPENING"}
    value_var = tk.StringVar(master=panel, value="全板")
    fields = {name: tk.StringVar(master=panel) for name in ("width", "height", "depth")}
    status = tk.StringVar(master=panel)
    door_fields = []
    joint_widgets = []

    def safely(action):
        try:
            action()
            refresh()
        except (ValueError, IndexError) as exc:
            messagebox.showwarning("設定未套用", str(exc), parent=panel.winfo_toplevel())

    def refresh(*, load_value=True):
        current_row = ports["row"]()
        for joint_index, depth_widget, height_widget in joint_widgets:
            left, right = current_row["bays"][joint_index:joint_index + 2]
            depth_widget.configure(state="readonly" if left["depth"] != right["depth"] else "disabled")
            height_widget.configure(state="readonly" if left["height"] != right["height"] else "disabled")
        current = ports["row"]()
        index = active.get()
        for key, var in fields.items():
            var.set(str(current["bays"][index][key]))
        rebuild_door_fields(current["bays"][index].get("door_state", {}).get("door_layout_columns", ()))
        kind = kind_labels[kind_var.get()]
        value = setting_value(current, index, kind)
        if not load_value and kind == "back_panel_mode":
            value = mode_labels[value_var.get()]
        elif not load_value and kind == "inner_door_layers":
            value = int(value_var.get())
        matches = [i + 1 for i in range(len(current["bays"])) if setting_value(current, i, kind) == value]
        for i, button in enumerate(selectors):
            button.configure(text=f"{'●' if i in pending else '○'} 第{i + 1}連", style="ReceivingPending.TButton" if i in pending else ("ReceivingMatch.TButton" if i + 1 in matches else "TButton"))
        status.set("目前相同設定：" + "、".join(map(str, matches)) + "連")
        if kind == "back_panel_mode":
            value_selector.configure(values=tuple(mode_labels), state="readonly")
            value_var.set(next(label for label, mode in mode_labels.items() if mode == value))
        elif kind == "inner_door_layers":
            value_selector.configure(values=("1", "2"), state="readonly")
            value_var.set(str(value))
        else:
            value_selector.configure(values=(), state="disabled")
            value_var.set(f"{len(value)} 個特徵")
        panel._receiving_pending = frozenset(pending)
        panel._receiving_matches = tuple(i - 1 for i in matches)
        callback = getattr(panel, "_receiving_after_selection", None)
        if callback:
            callback()

    def select(index):
        active.set(index)
        ports["select"](index)
        if index in pending:
            pending.remove(index)
        else:
            pending.add(index)
        refresh(load_value=False)

    style = ttk.Style(panel)
    selected_color = style.lookup("Treeview", "background", ("selected",)) or "#2563eb"
    style.configure("ReceivingPending.TButton", foreground=selected_color)
    style.configure("ReceivingMatch.TButton", foreground="#7c8fa6")
    for index in range(len(row["bays"])):
        button = ttk.Button(selection, text=f"第{index + 1}連", command=lambda index=index: select(index))
        button.grid(row=index // 8, column=index % 8, padx=2, pady=2, sticky="ew")
        selectors.append(button)
    brand_var = tk.StringVar(master=panel, value=row.get("switch_brand", "士林"))
    common = ttk.Frame(panel)
    common.pack(fill=tk.X, pady=4)
    ttk.Label(common, text="本套開關").pack(side=tk.LEFT)
    brand = ttk.Combobox(common, textvariable=brand_var, values=RECEIVING_SWITCH_BRANDS, width=6, state="readonly")
    brand.pack(side=tk.LEFT, padx=4)
    brand.bind("<<ComboboxSelected>>", lambda event: safely(lambda: ports["brand"](brand_var.get())))
    for key, label in (("width", "寬"), ("height", "高"), ("depth", "深")):
        ttk.Label(common, text=label).pack(side=tk.LEFT)
        ttk.Entry(common, textvariable=fields[key], width=8).pack(side=tk.LEFT, padx=3)
    def apply_dimensions():
        columns = None
        if door_fields:
            columns = tuple((float(width.get()), tuple(float(value.strip()) for value in heights.get().replace(",", "、").split("、"))) for width, heights in door_fields)
        ports["dimensions"](*(float(fields[key].get()) for key in ("width", "height", "depth")), door_columns=columns)
    ttk.Button(common, text="套用尺寸／門分割", command=lambda: safely(apply_dimensions)).pack(side=tk.LEFT, padx=4)
    door = ttk.Frame(panel)
    door.pack(fill=tk.X, pady=3)
    def rebuild_door_fields(columns):
        if len(door_fields) != len(columns):
            for child in door.winfo_children():
                child.destroy()
            door_fields.clear()
            for index in range(len(columns)):
                width_var = tk.StringVar(master=panel)
                height_var = tk.StringVar(master=panel)
                door_fields.append((width_var, height_var))
                ttk.Label(door, text=f"門第{index + 1}欄寬").grid(row=index, column=0, sticky="w")
                ttk.Entry(door, textvariable=width_var, width=8).grid(row=index, column=1, padx=3)
                ttk.Label(door, text="由上到下高度（以、分隔）").grid(row=index, column=2, sticky="w")
                ttk.Entry(door, textvariable=height_var, width=26).grid(row=index, column=3, padx=3)
        for (width_var, height_var), (width, heights) in zip(door_fields, columns):
            width_var.set(str(width))
            height_var.set("、".join(map(str, heights)))
    settings = ttk.Frame(panel)
    settings.pack(fill=tk.X)
    kind_selector = ttk.Combobox(settings, textvariable=kind_var, values=tuple(kind_labels), state="readonly", width=9)
    kind_selector.pack(side=tk.LEFT)
    kind_selector.bind("<<ComboboxSelected>>", lambda event: refresh())
    value_selector = ttk.Combobox(settings, textvariable=value_var, state="readonly", width=10)
    value_selector.pack(side=tk.LEFT, padx=4)
    value_selector.bind("<<ComboboxSelected>>", lambda event: refresh(load_value=False))

    def apply_value():
        kind = kind_labels[kind_var.get()]
        if kind in ("head_features", "tail_features"):
            ports["holes"]("head" if kind == "head_features" else "tail", sorted(pending))
        else:
            value = mode_labels[value_var.get()] if kind == "back_panel_mode" else int(value_var.get())
            ports["change"](kind, value, sorted(pending))

    ttk.Button(settings, text="編輯／套用", command=lambda: safely(apply_value)).pack(side=tk.LEFT, padx=3)
    ttk.Button(settings, text="連動選取的連", command=lambda: safely(lambda: ports["share"](kind_labels[kind_var.get()], sorted(pending)))).pack(side=tk.LEFT, padx=3)
    ttk.Button(settings, text="解除本連連動", command=lambda: safely(lambda: ports["unlink"](kind_labels[kind_var.get()]))).pack(side=tk.LEFT, padx=3)
    ttk.Label(panel, textvariable=status).pack(anchor=tk.W, pady=(4, 0))
    if row["joints"]:
        joints = ttk.Frame(panel)
        joints.pack(fill=tk.X, pady=4)
        for index, joint in enumerate(row["joints"]):
            ttk.Label(joints, text=f"第{index + 1}／{index + 2}連").grid(row=index // 3, column=(index % 3) * 3)
            depth_labels = {"前齊": "FRONT", "後齊": "REAR"}
            height_labels = {"上齊": "TOP", "下齊": "BOTTOM"}
            depth = tk.StringVar(master=panel, value=next(k for k, v in depth_labels.items() if v == joint["depth_alignment"]))
            height = tk.StringVar(master=panel, value=next(k for k, v in height_labels.items() if v == joint["height_alignment"]))
            left, right = row["bays"][index:index + 2]
            d_selector = ttk.Combobox(joints, textvariable=depth, values=tuple(depth_labels), width=7, state="readonly" if left["depth"] != right["depth"] else "disabled")
            h_selector = ttk.Combobox(joints, textvariable=height, values=tuple(height_labels), width=7, state="readonly" if left["height"] != right["height"] else "disabled")
            d_selector.grid(row=index // 3, column=(index % 3) * 3 + 1, padx=3)
            h_selector.grid(row=index // 3, column=(index % 3) * 3 + 2, padx=3)
            joint_widgets.append((index, d_selector, h_selector))
            callback = lambda event, index=index, depth=depth, height=height: safely(lambda: ports["alignment"](index, depth_labels[depth.get()], height_labels[height.get()]))
            d_selector.bind("<<ComboboxSelected>>", callback)
            h_selector.bind("<<ComboboxSelected>>", callback)
    panel._receiving_select_bay = select
    refresh()
    return panel
