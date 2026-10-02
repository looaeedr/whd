"""Presentation-only 2D previews for door-related parts.

This module consumes already-authoritative render snapshots supplied by the host.
It does not build part specs, call manufacturing APIs, own committed state, or
derive assembly/manufacturing geometry.
"""

import tkinter as tk

from ae_engine.sheetmetal_geometry import Vec2
from gui_modules.render_2d import (
    _draw_layout_baseline_secondary as _draw_layout_baseline_secondary_impl,
    _draw_layout_resolved_features as _draw_layout_resolved_features_impl,
)


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



def draw_door_layout_error(host, canvas, error):
    canvas.delete("all")
    host.door_layout_cell_items = {}
    host.door_layout_cell_bounds = {}
    cw = canvas.winfo_width()
    ch = canvas.winfo_height()
    if cw <= 1 or ch <= 1:
        return
    host.draw_grid(canvas, cw, ch)
    return canvas.create_text(
        cw / 2,
        ch / 2,
        text=f"多門配置無效:\n{error}",
        fill="#ff9f0a",
        font=("Microsoft JhengHei", 11, "bold"),
        width=max(240, cw - 80),
    )


def _door_layout_dimension_entry(host, canvas, column, column_index, x, y):
    entry = tk.Entry(
        canvas,
        textvariable=column["width_var"],
        width=9,
        bg=host.COLOR_INPUT_BG,
        fg="#30d158" if column.get("width_auto") else host.COLOR_TEXT,
        insertbackground=host.COLOR_TEXT,
        font=("Consolas", 13, "bold"),
        justify=tk.CENTER,
        bd=1,
        relief=tk.SOLID,
    )
    entry.bind(
        "<FocusOut>",
        lambda e, c=column_index: host.commit_door_layout_width(c),
    )
    entry.bind(
        "<Return>",
        lambda e, c=column_index: host.commit_door_layout_width(c),
    )
    host._door_layout_entry_menu(entry, column_index=column_index)
    win = canvas.create_window(
        x,
        y,
        window=entry,
        anchor=tk.CENTER,
        tags=("door_layout_dimension", "door_layout_width_entry"),
    )
    host.door_layout_width_entries[column_index] = entry
    host.door_layout_entry_windows.append(win)


def _door_layout_height_entry(
    host, canvas, column, column_index, row_index, x1, y1, y2,
):
    entry = tk.Entry(
        canvas,
        textvariable=column["height_vars"][row_index],
        width=9,
        bg=host.COLOR_INPUT_BG,
        fg="#30d158" if column["height_auto"][row_index] else host.COLOR_TEXT,
        insertbackground=host.COLOR_TEXT,
        font=("Consolas", 13, "bold"),
        justify=tk.CENTER,
        bd=1,
        relief=tk.SOLID,
    )
    entry.bind(
        "<FocusOut>",
        lambda e, c=column_index, r=row_index: host.commit_door_layout_height(c, r),
    )
    entry.bind(
        "<Return>",
        lambda e, c=column_index, r=row_index: host.commit_door_layout_height(c, r),
    )
    host._door_layout_entry_menu(
        entry, column_index=column_index, row_index=row_index
    )
    win = canvas.create_window(
        x1 + 4,
        (y1 + y2) / 2.0,
        window=entry,
        anchor=tk.W,
        tags=("door_layout_dimension", "door_layout_height_entry"),
    )
    host.door_layout_height_entries[(column_index, row_index)] = entry
    host.door_layout_entry_windows.append(win)


def _draw_door_layout_cell_payload(
    host, canvas, payload, bounds, column_index, row_index,
):
    mode = payload.get("mode")
    if mode == "local":
        _draw_layout_baseline_secondary_impl(
            canvas,
            payload["scene"],
            payload["width"],
            payload["height"],
            bounds,
            f"door_layout_baseline_{column_index}_{row_index}",
        )
        _draw_layout_resolved_features_impl(
            canvas,
            payload["resolved"],
            payload["width"],
            payload["height"],
            bounds,
            f"door_layout_feature_{column_index}_{row_index}",
        )
    elif mode == "peer":
        _draw_layout_baseline_secondary_impl(
            canvas,
            payload["scene"],
            payload["width"],
            payload["height"],
            bounds,
            f"corner_data_door_{column_index}_{row_index}",
        )


def draw_door_layout_overview_preview(host, snapshot, canvas):
    canvas.delete("all")
    host.door_layout_cell_items = {}
    host.door_layout_cell_bounds = {}

    cw = canvas.winfo_width()
    ch = canvas.winfo_height()
    if cw <= 1 or ch <= 1:
        return
    host.draw_grid(canvas, cw, ch)

    total_w = snapshot["total_w"]
    total_h = snapshot["total_h"]
    columns = snapshot["columns"]
    cells = snapshot["cells"]
    val = snapshot["val"]
    selected_key = snapshot["selected_key"]
    cell_payloads = snapshot["cell_payloads"]

    left_margin, right_margin = 58.0, 24.0
    top_margin, bottom_margin = 48.0, 24.0
    avail_w = max(1.0, cw - left_margin - right_margin)
    avail_h = max(1.0, ch - top_margin - bottom_margin)
    scale = min(avail_w / total_w, avail_h / total_h)
    draw_w = total_w * scale
    draw_h = total_h * scale
    x0 = left_margin + (avail_w - draw_w) / 2.0
    y0 = top_margin + (avail_h - draw_h) / 2.0

    cell_map = {(cell.column_index, cell.row_index): cell for cell in cells}
    x_cursor = x0
    for column_index, (column_w, heights) in enumerate(columns):
        col_px = column_w * scale
        column = host.door_layout_columns[column_index]
        _door_layout_dimension_entry(
            host,
            canvas,
            column,
            column_index,
            x_cursor + col_px / 2.0,
            y0 - 24,
        )

        y_cursor = y0
        for row_index, segment_h in enumerate(heights):
            row_px = segment_h * scale
            x1, y1 = x_cursor, y_cursor
            x2, y2 = x_cursor + col_px, y_cursor + row_px
            key = f"{column_index}:{row_index}"
            selected = key == selected_key
            rect = canvas.create_rectangle(
                x1,
                y1,
                x2,
                y2,
                outline=host.COLOR_ACCENT if selected else "#30d158",
                width=3 if selected else 2,
                tags=("door_layout_cell", f"door_layout_cell_{column_index}_{row_index}"),
            )
            host.door_layout_cell_items[key] = rect
            bounds = (x1, y1, x2, y2)
            host.door_layout_cell_bounds[key] = bounds

            _door_layout_height_entry(
                host,
                canvas,
                column,
                column_index,
                row_index,
                x1,
                y1,
                y2,
            )
            _ = cell_map[(column_index, row_index)]
            _draw_door_layout_cell_payload(
                host,
                canvas,
                cell_payloads.get((column_index, row_index), {}),
                bounds,
                column_index,
                row_index,
            )
            y_cursor = y2
        x_cursor += col_px

    baseline_status = snapshot["baseline_status"]
    canvas.create_text(
        10,
        10,
        anchor=tk.NW,
        text=baseline_status,
        fill="#64d2ff" if baseline_status.startswith("基準檔：") else "#ff9f0a",
        font=("Microsoft JhengHei", 9, "bold"),
        tags=("door_baseline_status",),
    )
    canvas.create_text(
        10,
        30,
        anchor=tk.NW,
        text="各欄獨立分層：修改該欄綠色『自動』高度即可新增下一層（例 2 / 3 / 2）",
        fill=host.COLOR_TEXT_MUTED,
        font=("Microsoft JhengHei", 9, "bold"),
        tags=("door_layout_asymmetric_hint",),
    )

    host._draw_door_layout_dividers_and_frames(
        canvas, scale, x0, y0, columns, cells, val
    )
    host.last_door_layout_overview = {
        "columns": columns,
        "cell_count": len(cells),
        "selected": selected_key,
        "scale": scale,
        "origin": (x0, y0),
    }



def _door_layout_world_to_canvas(world_x, world_y, *, total_w, total_h, scale, x0, y0):
    return (
        x0 + (float(world_x) + float(total_w) / 2.0) * float(scale),
        y0 + (float(total_h) / 2.0 - float(world_y)) * float(scale),
    )


def _draw_door_layout_divider_payload(canvas, payload, *, total_w, total_h, scale, x0, y0):
    cx, cy, _cz = payload["world_offset"]
    span = float(payload["span"])
    axis = payload["axis"]
    if axis == "HORIZONTAL":
        x1, y = _door_layout_world_to_canvas(
            cx - span / 2.0, cy,
            total_w=total_w, total_h=total_h, scale=scale, x0=x0, y0=y0,
        )
        x2, _ = _door_layout_world_to_canvas(
            cx + span / 2.0, cy,
            total_w=total_w, total_h=total_h, scale=scale, x0=x0, y0=y0,
        )
        canvas.create_rectangle(
            x1, y - 3, x2, y + 3,
            fill="#00d4d4", outline="#00a3a3", width=1,
            tags=("door_layout_divider",),
        )
        canvas.create_text(
            (x1 + x2) / 2.0, y + 14,
            text=(
                f"中隔 W-2T={span:.1f} mm "
                f"(成型深={float(payload['formed_core_depth']):.1f})"
            ),
            fill="#00d4d4", font=("Consolas", 9, "bold"),
            tags=("door_layout_divider",),
        )
    elif axis == "VERTICAL":
        x, y1 = _door_layout_world_to_canvas(
            cx, cy + span / 2.0,
            total_w=total_w, total_h=total_h, scale=scale, x0=x0, y0=y0,
        )
        _, y2 = _door_layout_world_to_canvas(
            cx, cy - span / 2.0,
            total_w=total_w, total_h=total_h, scale=scale, x0=x0, y0=y0,
        )
        canvas.create_rectangle(
            x - 3, y1, x + 3, y2,
            fill="#00d4d4", outline="#00a3a3", width=1,
            tags=("door_layout_divider",),
        )


def _draw_door_layout_frame_payload(canvas, payload, *, total_w, total_h, scale, x0, y0):
    side = payload["side"]
    cx, cy, _cz = payload["world_offset"]
    span = float(payload["span"])
    if side == "top":
        x1, y = _door_layout_world_to_canvas(
            cx - span / 2.0, cy,
            total_w=total_w, total_h=total_h, scale=scale, x0=x0, y0=y0,
        )
        x2, _ = _door_layout_world_to_canvas(
            cx + span / 2.0, cy,
            total_w=total_w, total_h=total_h, scale=scale, x0=x0, y0=y0,
        )
        canvas.create_line(
            x1, y, x2, y, fill="#ff9f0a", width=2, dash=(6, 3),
            tags=("door_layout_frame",),
        )
        canvas.create_text(
            (x1 + x2) / 2.0, y + 14,
            text=f"內門框 (頂/左/右內縮50mm, 寬={span:.1f})",
            fill="#ff9f0a", font=("Microsoft JhengHei", 8, "bold"),
            tags=("door_layout_frame",),
        )
    elif side in {"left", "right"}:
        x, y1 = _door_layout_world_to_canvas(
            cx, cy + span / 2.0,
            total_w=total_w, total_h=total_h, scale=scale, x0=x0, y0=y0,
        )
        _, y2 = _door_layout_world_to_canvas(
            cx, cy - span / 2.0,
            total_w=total_w, total_h=total_h, scale=scale, x0=x0, y0=y0,
        )
        canvas.create_line(
            x, y1, x, y2, fill="#ff9f0a", width=2, dash=(6, 3),
            tags=("door_layout_frame",),
        )


def draw_door_layout_dividers_and_frames_preview(canvas, snapshot, scale, x0, y0):
    total_w = snapshot["total_w"]
    total_h = snapshot["total_h"]
    for payload in snapshot.get("dividers", ()):
        _draw_door_layout_divider_payload(
            canvas, payload,
            total_w=total_w, total_h=total_h, scale=scale, x0=x0, y0=y0,
        )
    for payload in snapshot.get("frames", ()):
        _draw_door_layout_frame_payload(
            canvas, payload,
            total_w=total_w, total_h=total_h, scale=scale, x0=x0, y0=y0,
        )
