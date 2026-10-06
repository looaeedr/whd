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

    figure = Figure(figsize=(10.0, 6.2), dpi=100)
    figure.subplots_adjust(left=0.0, right=1.0, bottom=0.0, top=1.0)
    ax = figure.add_subplot(111, projection="3d")
    apply_mpl_dark_theme(figure, (ax,))
    canvas = FigureCanvasTkAgg(figure, master=body)
    preview_renderer = Phase6FinalSceneRenderer(
        SimpleNamespace(ax3d=ax, canvas=canvas)
    )

    render_data = render_request.render_data
    source_parts = tuple(getattr(render_data, "assembly_parts", ()) or ())
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

    def _render_preview(*, reset_view=False):
        try:
            elev, azim = float(ax.elev), float(ax.azim)
        except Exception:
            elev, azim = 22.0, -56.0
        if reset_view:
            elev, azim = 22.0, -56.0
            preview_renderer.zoom_scale = 1.0

        ax.clear()
        apply_mpl_dark_theme(figure, (ax,))
        if selected_part_keys:
            visible = (
                None
                if selected_part_keys == set(all_part_keys)
                else tuple(key for key in all_part_keys if key in selected_part_keys)
            )
            data = replace(render_data, visible_part_keys=visible)
            request = replace(render_request, render_data=data)
            triangles = tuple(preview_renderer.render(request) or ())
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
        ax.view_init(elev=elev, azim=azim)
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
