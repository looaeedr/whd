"""Presentation-only 2D previews for door-related parts.

This module consumes already-authoritative render snapshots supplied by the host.
It does not build part specs, call manufacturing APIs, own committed state, or
derive assembly/manufacturing geometry.
"""

import tkinter as tk

from ae_engine.sheetmetal_geometry import Vec2


def draw_preview_error(canvas, canvas_width, canvas_height, title, error, *, width=None):
    kwargs = {
        "text": f"{title} Final Part Geometry 載入失敗:\n{error}",
        "fill": "#ff3333",
        "font": ("Microsoft JhengHei", 11, "bold"),
    }
    if width is not None:
        kwargs["width"] = max(200, float(width))
    return canvas.create_text(canvas_width / 2, canvas_height / 2, **kwargs)


def draw_indicator_box_preview(
    host,
    snapshot,
    canvas_width,
    canvas_height,
    *,
    viewport,
    scene_renderer,
    annotation_drawer,
    hint_drawer,
):
    canvas = host.canvas_indicator_box
    render_data = snapshot["render_data"]
    minx, miny, maxx, maxy = snapshot["bounds"]
    layer_groups = snapshot["layer_groups"]
    baseline_label = snapshot["baseline_label"]

    transform, _left, _bottom, _scale, _material_top = viewport(
        (minx, miny, maxx, maxy), canvas_width, canvas_height
    )

    if host.draw_stock_var.get():
        sx0, sy0 = transform.world_to_canvas(Vec2(minx, miny))
        sx1, sy1 = transform.world_to_canvas(Vec2(maxx, maxy))
        canvas.create_rectangle(
            sx0, sy0, sx1, sy1,
            outline="#00d4d4", width=1.5, dash=(8, 4),
        )

    scene_renderer(
        canvas,
        render_data.scene,
        transform,
        skip_layers=("CHECK", "STOCK"),
    )

    stock_hint = "  STOCK 母材外框: 青色虛線" if host.draw_stock_var.get() else ""
    canvas.create_text(
        25,
        25,
        anchor=tk.NW,
        text=(
            f"指示燈盒子展開預覽｜{baseline_label}｜Final Part Geometry\n"
            "CUTTING/截角/固定孔/使用者開孔：與 3D 完全同源\n"
            f"折彎線 (BEND): 藍色虛線{stock_hint}\n"
            f"排列 {list(layer_groups)}，共 {sum(layer_groups)} 顆指示燈"
        ),
        fill=host.COLOR_TEXT_MUTED,
        font=("Microsoft JhengHei", 9),
        width=max(180, int(canvas_width * 0.48)),
        tags=("phase6_preview_hint",),
    )
    annotation_drawer(canvas, render_data, transform, part_key="indicator_box")
    host._draw_phase6_finished_dimension_summary(canvas, part_key="indicator_box")
    hint_drawer(canvas, canvas_width, endcap=False)


def draw_indicator_door_preview(
    host,
    snapshot,
    canvas_width,
    canvas_height,
    *,
    viewport,
    scene_renderer,
    annotation_drawer,
    hint_drawer,
):
    canvas = host.canvas_indicator_door
    render_data = snapshot["render_data"]
    minx, miny, maxx, maxy = snapshot["bounds"]
    finished_w, finished_h = snapshot["finished_size"]

    transform, _left, _bottom, _scale, _material_top = viewport(
        (minx, miny, maxx, maxy), canvas_width, canvas_height
    )

    if host.draw_stock_var.get():
        sx0, sy0 = transform.world_to_canvas(Vec2(minx, miny))
        sx1, sy1 = transform.world_to_canvas(Vec2(maxx, maxy))
        canvas.create_rectangle(
            sx0, sy0, sx1, sy1,
            outline="#00d4d4", width=1.5, dash=(8, 4),
        )

    scene_renderer(
        canvas,
        render_data.scene,
        transform,
        skip_layers=("CHECK", "STOCK"),
    )

    stock_hint = "  STOCK 母材外框: 青色虛線" if host.draw_stock_var.get() else ""
    canvas.create_text(
        25,
        25,
        anchor=tk.NW,
        text=(
            "指示燈小門展開預覽｜Final Part Geometry\n"
            "CUTTING/截角/固定孔/使用者開孔：與 3D 完全同源\n"
            f"成品 {finished_w:.2f} × {finished_h:.2f} mm{stock_hint}"
        ),
        fill=host.COLOR_TEXT_MUTED,
        font=("Microsoft JhengHei", 9),
        width=max(180, int(canvas_width * 0.48)),
        tags=("phase6_preview_hint",),
    )
    annotation_drawer(canvas, render_data, transform, part_key="indicator_door")
    host._draw_phase6_finished_dimension_summary(canvas, part_key="indicator_door")
    hint_drawer(canvas, canvas_width, endcap=False)
