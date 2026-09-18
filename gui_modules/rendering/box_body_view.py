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



def draw_box_body_aggregate_preview(
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
    canvas = host.canvas_z
    render_data = snapshot["render_data"]
    minx, miny, maxx, maxy = snapshot["bounds"]
    z_len = maxx - minx
    z_height = maxy - miny
    contexts = snapshot["contexts"]
    selected = snapshot["selected_face"]

    transform, _offset_x, _offset_y, _scale, _material_top = viewport(
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
    warnings = tuple(getattr(render_data, "warnings", ()) or ())
    warning_text = (
        "\n⚠ " + "；".join(str(getattr(item, "message", item)) for item in warnings)
        if warnings else ""
    )

    for face_key in ("left", "back", "right"):
        ctx = contexts[face_key]
        x1, y_bottom = transform.world_to_canvas(Vec2(ctx.unfolded_min_x, 0.0))
        x2, y_top = transform.world_to_canvas(Vec2(ctx.unfolded_max_x, z_height))
        bounds = (
            min(x1, x2),
            min(y_top, y_bottom),
            max(x1, x2),
            max(y_top, y_bottom),
        )
        host.box_body_face_bounds[face_key] = bounds
        canvas.create_rectangle(
            *bounds,
            outline=host.COLOR_ACCENT if face_key == selected else "",
            width=2 if face_key == selected else 1,
            dash=(4, 3),
            tags=("box_body_face_hit_zone", f"box_body_face_{face_key}"),
        )

    stock_hint = "  STOCK 母材外框: 青色虛線" if host.draw_stock_var.get() else ""
    canvas.create_text(
        25,
        25,
        anchor=tk.NW,
        text=(
            "箱身展開預覽 (Z-Body)\n"
            f"{snapshot['baseline_status']}\n"
            "外輪廓 (CUTTING): 綠色實線  折彎線 (BEND): 藍色虛線"
            f"{stock_hint}\n"
            f"雙擊左側/背面/右側完成面進入箱體定位編輯{warning_text}"
        ),
        fill=host.COLOR_TEXT_MUTED,
        font=("Microsoft JhengHei", 9),
        width=max(180, int(canvas_width * 0.48)),
        tags=("phase6_preview_hint",),
    )
    annotation_drawer(canvas, render_data, transform, part_key="box_body")
    host._draw_phase6_finished_dimension_summary(canvas, part_key="box_body")
    hint_drawer(canvas, canvas_width, endcap=False)

    host.last_box_body_face_overview = {
        "mode": "unfolded_with_face_hit_zones",
        "dimensions": snapshot["dimensions"],
        "unfolded_size": (z_len, z_height),
        "transform": transform,
        "contexts": contexts,
        "piece_keys": snapshot["piece_keys"],
        "baseline_status": snapshot["baseline_status"],
    }



def draw_end_cap_error(host, canvas, canvas_width, canvas_height, error, *, hint_drawer):
    canvas.create_text(
        canvas_width / 2,
        canvas_height / 2,
        text=f"封頭尾載入失敗: {error}",
        fill="#ff3333",
        font=("Microsoft JhengHei", 10, "bold"),
    )
    hint_drawer(canvas, canvas_width, endcap=True)


def draw_end_cap_preview(
    host,
    snapshot,
    canvas,
    canvas_width,
    canvas_height,
    *,
    viewport,
    scene_renderer,
    annotation_drawer,
    hint_drawer,
):
    render_data = snapshot["render_data"]
    minx, miny, maxx, maxy = snapshot["bounds"]
    transform, _offset_x, _offset_y, _scale, _material_top = viewport(
        (minx, miny, maxx, maxy), canvas_width, canvas_height
    )

    scene_renderer(
        canvas,
        render_data.scene,
        transform,
        skip_layers=("CHECK", "STOCK"),
    )

    if host.draw_stock_var.get():
        sx0, sy0 = transform.world_to_canvas(Vec2(minx, miny))
        sx1, sy1 = transform.world_to_canvas(Vec2(maxx, maxy))
        canvas.create_rectangle(
            sx0,
            sy0,
            sx1,
            sy1,
            outline="#00d4d4",
            width=1.5,
            dash=(8, 4),
        )

    stock_hint = "  STOCK: 青色虛線" if host.draw_stock_var.get() else ""
    tail_hint = "  [封尾]" if snapshot["is_tail"] else "  [封頭]"
    canvas.create_text(
        25,
        25,
        anchor=tk.NW,
        text=(
            f"{snapshot['part_label']}展開預覽{snapshot['baseline_hint']}\n"
            f"外輪廓: 綠色  折彎: 藍色  孔洞: 綠色{stock_hint}{tail_hint}"
        ),
        fill=host.COLOR_TEXT_MUTED,
        font=("Microsoft JhengHei", 9),
        width=max(180, int(canvas_width * 0.48)),
        tags=("phase6_preview_hint",),
    )

    part_key = "tail" if snapshot["is_tail"] else "head"
    annotation_drawer(canvas, render_data, transform, part_key=part_key)
    host._draw_phase6_finished_dimension_summary(canvas, part_key=part_key)
    hint_drawer(canvas, canvas_width, endcap=True)



def box_body_baseline_faces(host, val, *, ae_module):
    model = host._baseline_source_model()
    if not model or not ae_module.has_baseline_part(model, "箱身.dxf"):
        return {"left": [], "back": [], "right": []}

    head_policy, tail_policy = host._box_body_corner_policies(val["fw"])
    source_fp = ae_module.baseline_source_fingerprint(
        ae_module.baseline_expected_path(model, "箱身.dxf")
    )
    cache_key = (
        source_fp,
        model,
        val["w"],
        val["h"],
        val["d"],
        val["t"],
        val["fw"],
        val["zl1"],
        val["zl2"],
        val["zr1"],
        val["zr2"],
        val["z_comp"],
        head_policy,
        tail_policy,
    )
    if cache_key not in host._box_body_baseline_face_cache:
        host._box_body_baseline_face_cache[cache_key] = (
            ae_module.get_box_body_baseline_face_features(
                model,
                w=val["w"],
                h=val["h"],
                d=val["d"],
                t=val["t"],
                fw=val["fw"],
                zl1=val["zl1"],
                zl2=val["zl2"],
                zr1=val["zr1"],
                zr2=val["zr2"],
                z_comp=val["z_comp"],
                head_corner_policy=head_policy,
                tail_corner_policy=tail_policy,
            )
        )
    return host._box_body_baseline_face_cache[cache_key]
