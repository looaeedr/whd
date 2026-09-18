"""Presentation-only 2D previews for door-related parts.

This module consumes already-authoritative render snapshots supplied by the host.
It does not build part specs, call manufacturing APIs, own committed state, or
derive assembly/manufacturing geometry.
"""

import tkinter as tk

from ae_engine.sheetmetal_geometry import Vec2


def draw_preview_error(
    canvas, canvas_width, canvas_height, title, error, *, width=None, font_size=11,
):
    kwargs = {
        "text": f"{title} Final Part Geometry 載入失敗:\n{error}",
        "fill": "#ff3333",
        "font": ("Microsoft JhengHei", int(font_size), "bold"),
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



def draw_single_door_preview(
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
    canvas = host.canvas_door
    render_data = snapshot["render_data"]
    minx, miny, maxx, maxy = snapshot["bounds"]
    finished_w, finished_h = snapshot["finished_size"]
    door_val = snapshot["door_val"]
    model_name = snapshot["model_name"]

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

    stock_hint = "  STOCK: 青色虛線" if host.draw_stock_var.get() else ""
    baseline_hint = (
        f" ({model_name} 最終製造幾何)"
        if model_name
        else " (自訂最終製造幾何)"
    )
    canvas.create_text(
        25,
        25,
        anchor=tk.NW,
        text=(
            f"門板展開預覽{baseline_hint}\n"
            "CUTTING/截角/固定孔/使用者開孔：同一份 Final Part Geometry\n"
            f"折彎線 (BEND): 藍色虛線{stock_hint}\n"
            f"成品寬 = {finished_w:.2f} mm / 成品高 = {finished_h:.2f} mm\n"
            f"折邊: 左{door_val['door_fold_l']} 右{door_val['door_fold_r']} "
            f"上{door_val['door_fold_t']} 下{door_val['door_fold_b']}"
        ),
        fill=host.COLOR_TEXT_MUTED,
        font=("Microsoft JhengHei", 9),
        width=max(180, int(canvas_width * 0.48)),
        tags=("phase6_preview_hint",),
    )

    indicator_context = snapshot["indicator_context"]
    indicator_groups = snapshot["indicator_groups"]
    indicator_layout = snapshot["indicator_layout"]
    host.last_door_draw_params = {
        "transform": transform,
        "blank_w": maxx - minx,
        "blank_h": maxy - miny,
        "indicator_context": indicator_context,
        "indicator_groups": indicator_groups,
        "indicator_layout": indicator_layout,
        "frame_edges": snapshot["frame_edges"],
        "layout_cell": None,
        "render_data": render_data,
    }

    x_guide = snapshot.get("x_guide")
    y_guide = snapshot.get("y_guide")
    if x_guide is not None and y_guide is not None:
        p1_cx, p1_cy = transform.world_to_canvas(x_guide.start)
        p2_cx, p2_cy = transform.world_to_canvas(x_guide.end)
        p1_cy -= 20
        p2_cy -= 20
        canvas.create_line(
            p1_cx, p1_cy, p2_cx, p2_cy,
            fill="#ff9f0a", arrow=tk.BOTH, arrowshape=(6, 8, 3), width=1.2,
        )
        canvas.create_text(
            (p1_cx + p2_cx) / 2, p1_cy - 10,
            text=f"X={x_guide.value:.1f}",
            fill="#ff9f0a", font=("Consolas", 9, "bold"), tags="dim_x",
        )

        p1_cx, p1_cy = transform.world_to_canvas(y_guide.start)
        p2_cx, p2_cy = transform.world_to_canvas(y_guide.end)
        p1_cx -= 20
        p2_cx -= 20
        canvas.create_line(
            p1_cx, p1_cy, p2_cx, p2_cy,
            fill="#ff9f0a", arrow=tk.BOTH, arrowshape=(6, 8, 3), width=1.2,
        )
        canvas.create_text(
            p1_cx - 30, (p1_cy + p2_cy) / 2,
            text=f"Y={y_guide.value:.1f}",
            fill="#ff9f0a", font=("Consolas", 9, "bold"), tags="dim_y",
        )

    annotation_drawer(canvas, render_data, transform, part_key="door")
    host._draw_phase6_finished_dimension_summary(canvas, part_key="door")
    hint_drawer(canvas, canvas_width, endcap=False)


def draw_base_plate_preview(
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
    canvas = host.canvas_base_plate
    render_data = snapshot["render_data"]
    minx, miny, maxx, maxy = snapshot["bounds"]
    world_min_x, world_min_y, world_max_x, world_max_y = snapshot["world_bounds"]
    box_l, box_b, box_w, box_h = snapshot["box_rect"]
    bend = snapshot["bend"]

    transform, _left, _bottom, _scale, _material_top = viewport(
        (world_min_x, world_min_y, world_max_x, world_max_y),
        canvas_width,
        canvas_height,
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

    bx0, by0 = transform.world_to_canvas(Vec2(box_l, box_b))
    bx1, by1 = transform.world_to_canvas(Vec2(box_l + box_w, box_b + box_h))
    canvas.create_rectangle(
        bx0, by0, bx1, by1,
        outline="#ff453a", width=1.2, dash=(4, 4),
    )

    stock_hint = " + [母材]" if host.draw_stock_var.get() else ""
    total_width = maxx - minx
    total_height = maxy - miny
    hole_w = total_width - 2.0 * bend - 30.0
    hole_h = total_height - 2.0 * bend - 30.0
    canvas.create_text(
        20,
        20,
        text=(
            "底板展開預覽｜Final Part Geometry\n"
            "CUTTING/截角/固定孔/使用者開孔：與 3D 完全同源\n"
            "箱身外框對照線: 紅色虛線\n"
            f"展開圖孔距 W:{hole_w:.1f} H:{hole_h:.1f}{stock_hint}"
        ),
        fill=host.COLOR_TEXT,
        font=("Microsoft JhengHei", 9, "bold"),
        anchor=tk.NW,
        width=max(180, int(canvas_width * 0.48)),
        tags=("phase6_preview_hint",),
    )
    annotation_drawer(canvas, render_data, transform, part_key="base_plate")
    host._draw_phase6_finished_dimension_summary(canvas, part_key="base_plate")
    hint_drawer(canvas, canvas_width, endcap=False)
