"""Presentation-only BoxBody 2D rendering.

This module consumes already-authoritative BoxBody render data and physical-piece
records. It does not build part specs or derive manufacturing geometry.
"""

import tkinter as tk

from ae_engine.sheetmetal_geometry import Vec2


def draw_box_body_piece_preview(
    host,
    aggregate_render_data,
    piece,
    part_key,
    *,
    viewport,
    scene_renderer,
    annotation_drawer,
):
    canvas = host.canvas_z
    render_data = piece.render_data
    minx, miny, maxx, maxy = (float(v) for v in render_data.material.bounds)
    transform, _offset_x, _offset_y, _scale, _material_top = viewport(
        (minx, miny, maxx, maxy),
        canvas.winfo_width(),
        canvas.winfo_height(),
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

    label = host._box_body_piece_label(part_key)
    formed = tuple(
        float(v) for v in getattr(piece, "formed_outer_dimensions", (0.0, 0.0))
    )
    blank = tuple(
        float(v) for v in getattr(piece, "material_dimensions", (0.0, 0.0))
    )
    dimension_text = ""
    if len(formed) >= 2 and len(blank) >= 2:
        dimension_text = (
            f"\n成形：{formed[0]:g} × {formed[1]:g} mm"
            f"  展開：{blank[0]:g} × {blank[1]:g} mm"
        )

    warnings = tuple(getattr(render_data, "warnings", ()) or ())
    warning_text = (
        "\n⚠ " + "；".join(str(getattr(item, "message", item)) for item in warnings)
        if warnings
        else ""
    )

    canvas.create_text(
        25,
        25,
        anchor=tk.NW,
        text=(
            f"{label}展開預覽（箱身子板件）{dimension_text}"
            "\n外輪廓 (CUTTING): 綠色實線  折彎線 (BEND): 藍色虛線"
            f"\n雙擊畫布編輯此片開孔{warning_text}"
        ),
        fill=host.COLOR_TEXT_MUTED,
        font=("Microsoft JhengHei", 9),
        width=max(180, int(canvas.winfo_width() * 0.56)),
        tags=("phase6_preview_hint",),
    )
    annotation_drawer(canvas, render_data, transform, part_key=part_key)

    role = str(getattr(piece, "role", "") or "")
    host.last_box_body_face_overview = {
        "mode": "physical_piece",
        "piece_key": part_key,
        "role": role,
        "material_bounds": (minx, miny, maxx, maxy),
        "aggregate_piece_count": len(
            tuple(getattr(aggregate_render_data, "pieces", ()) or ())
        ),
    }
