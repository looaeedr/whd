# -*- coding: utf-8 -*-
"""View-only builder for Receiving layer/connection controls.

The legacy filename is retained for compatibility, but operator-facing terms are
層/連. Layer/connection state is projected from receiving_switch_layout; this module owns
Tk widgets only and never owns manufacturing geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable


from ae_engine.receiving_switch_layout import RECEIVING_SWITCH_BRANDS


@dataclass(frozen=True)
class ReceivingSetBayControls:
    frame: object
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
        layer_actions, text="－層", command=on_remove_layer, width=5
    )
    remove_layer_button.pack(side=tk.LEFT, padx=(0, 2))
    add_layer_button = ttk.Button(
        layer_actions, text="＋層", command=on_add_layer, width=5
    )
    add_layer_button.pack(side=tk.LEFT)

    return ReceivingSetBayControls(
        frame=frame,
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
    """Render one layer as an actual 3D multi-connection preview.

    The incoming meshes are already-resolved current cabinet geometry, so CUTTING
    openings remain part of the preview. ``lock_circles`` are canonical Receiving
    Joint lock holes projected on each mating plane; this view never owns their
    coordinates or mutates the main renderer.
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

    win = tk.Toplevel(parent)
    win.title(f"第{index + 1}層 3D 預覽")
    win.transient(parent)
    win.geometry("1000x700")
    try:
        win.grab_set()
    except Exception:
        pass

    body = ttk.Frame(win, padding=10)
    body.pack(fill=tk.BOTH, expand=True)
    ttk.Label(
        body, text=f"第{index + 1}層｜{count}連｜開關：{label}"
    ).pack(anchor=tk.W, pady=(0, 6))

    figure = Figure(figsize=(9.6, 6.0), dpi=100)
    ax = figure.add_subplot(111, projection="3d")
    apply_mpl_dark_theme(figure, (ax,))
    preview_renderer = Phase6FinalSceneRenderer(SimpleNamespace(ax3d=ax))
    all_triangles = tuple(preview_renderer.render(render_request) or ())
    if not all_triangles:
        raise ValueError("Receiving preview FinalScene mesh is empty")
    # The Tk header already provides layer/connection context. Remove renderer
    # text overlays so the preview stays a clean geometry view.
    for artist in list(getattr(ax, "texts", ())):
        try:
            artist.remove()
        except Exception:
            pass

    import math
    lock_rows = tuple(lock_circles or ())
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

    ax.view_init(elev=22.0, azim=-56.0)
    ax.set_axis_off()

    canvas = FigureCanvasTkAgg(figure, master=body)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    canvas.draw_idle()

    actions = ttk.Frame(body)
    actions.pack(fill=tk.X, pady=(6, 0))
    ttk.Button(actions, text="關閉", command=win.destroy).pack(side=tk.RIGHT)

    # Exact GUI acceptance/readback metadata. These are presentation facts only.
    win._phase6_receiving_preview_canvas = canvas
    win._phase6_receiving_preview_connection_count = count
    win._phase6_receiving_preview_mesh_count = count
    win._phase6_receiving_preview_uses_final_scene_renderer = True
    win._phase6_receiving_preview_lock_circle_count = len(lock_rows)
    win._phase6_receiving_preview_feature_segment_count = 0
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
        preview_button = ttk.Button(frame, text="預覽", width=6)
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
        row["layer_label"].configure(text=f"第{layer_index + 1}層")
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
