# -*- coding: utf-8 -*-
"""View-only builder for Receiving layer/connection controls.

The legacy filename is retained for compatibility, but operator-facing terms are
套/連. Layer/connection state is projected from receiving_switch_layout; this module owns
Tk widgets only and never owns manufacturing geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
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
    """Show committed physical DrawingScenes in an interactive 2D settings view."""
    index = int(layer_index)
    count = max(1, int(connection_count))
    label = str(brand)
    if render_request is None:
        raise ValueError("Receiving preview requires a FinalScene render request")

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

    from .receiving_settings_preview_2d import ReceivingSettingsPreview2D, refresh_committed_preview
    view = ReceivingSettingsPreview2D(body, tk=tk, ttk=ttk,
        requests=tuple(bay_requests) or (render_request,), panel=settings_panel)
    if settings_panel is not None:
        settings_panel._receiving_after_selection = view.update_overlay
        subscribe = settings_ports.get("subscribe")
        if subscribe is not None:
            from .command_router import _Phase6UpdateScheduler
            scheduler = _Phase6UpdateScheduler(win, executor=lambda reasons:
                refresh_committed_preview(view, bay_request_provider) if win.winfo_exists() else None)
            subscribe(lambda: scheduler.submit("geometry", immediate=True) if win.winfo_exists() else None)
            win._phase6_receiving_preview_scheduler = scheduler
    actions = ttk.Frame(body)
    actions.pack(fill=tk.X, pady=(6, 0))
    ttk.Button(actions, text="放大", command=lambda: view.zoom(.8)).pack(side=tk.LEFT)
    ttk.Button(actions, text="縮小", command=lambda: view.zoom(1.25)).pack(side=tk.LEFT)
    ttk.Button(actions, text="重設視角", command=view.reset_view).pack(side=tk.LEFT)
    ttk.Label(actions, text="先選修改項目，再選連｜滾輪：縮放｜中鍵拖曳：平移").pack(side=tk.LEFT, padx=8)
    ttk.Button(actions, text="關閉", command=win.destroy).pack(side=tk.RIGHT)
    win._phase6_receiving_preview_canvas = view.canvas
    win._phase6_receiving_preview_2d = view
    win._phase6_receiving_settings_panel = settings_panel
    win._phase6_receiving_settings_ports = settings_ports
    win._phase6_receiving_preview_connection_count = count
    win._phase6_receiving_preview_mesh_count = 0
    win._phase6_receiving_preview_uses_final_scene_renderer = False
    win._phase6_receiving_preview_lock_circle_count = 0
    win._phase6_receiving_preview_feature_segment_count = 0
    win._phase6_receiving_preview_visibility_groups = tuple(view.visibility)
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
    kind_var = tk.StringVar(master=panel, value="請選修改項目")
    mode_labels = {"全板": "FULL", "半截": "HALF", "背開孔": "BACK_OPENING"}
    value_var = tk.StringVar(master=panel, value="全板")
    fields = {name: tk.StringVar(master=panel) for name in ("width", "height", "depth")}
    status = tk.StringVar(master=panel)
    door_fields = []
    joint_widgets = []

    def safely(action):
        from .receiving_settings_preview_2d import CommittedPreviewError
        try:
            action()
            refresh()
        except CommittedPreviewError as exc:
            messagebox.showwarning("設定已提交；預覽失敗", str(exc), parent=panel.winfo_toplevel())
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
        kind = kind_labels.get(kind_var.get())
        panel._receiving_kind = kind
        enabled = kind is not None
        for button in selectors + setting_actions:
            button.configure(state="normal" if enabled else "disabled")
        if not enabled:
            pending.clear()
            panel._receiving_pending = frozenset()
            panel._receiving_matches = ()
            value_selector.configure(state="disabled")
            status.set("請先選擇修改項目，再選要套用的連")
            callback = getattr(panel, "_receiving_after_selection", None)
            if callback:
                callback()
            return
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
        if kind_var.get() not in kind_labels:
            return
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
    ttk.Button(common, text="套用品牌", command=lambda: safely(lambda: ports["brand"](brand_var.get()))).pack(side=tk.LEFT)
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
    def select_kind(event=None):
        pending.clear()
        refresh()
    kind_selector.bind("<<ComboboxSelected>>", select_kind)
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

    setting_actions = []
    for label, action in (
        ("編輯／套用", apply_value),
        ("連動選取的連", lambda: ports["share"](kind_labels[kind_var.get()], sorted(pending))),
        ("解除本連連動", lambda: ports["unlink"](kind_labels[kind_var.get()]))):
        button = ttk.Button(settings, text=label, command=lambda action=action: safely(action))
        button.pack(side=tk.LEFT, padx=3)
        setting_actions.append(button)
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
            ttk.Button(joints, text="套用接合", command=lambda callback=callback: callback(None)).grid(
                row=index // 3, column=10 + index % 3, padx=3)
    panel._receiving_select_bay = select
    panel._receiving_kind_var = kind_var
    panel._receiving_refresh = refresh
    refresh()
    return panel
