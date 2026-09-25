"""Presentation-only reference, engineering annotation, and dimension overlays."""

import tkinter as tk

from ae_engine.engineering_drawing import build_engineering_drawing_projection
from ae_engine.sheetmetal_drawing import LinePrimitive, TextPrimitive
from phase6_corner_dimension_display import render_data_corner_dimension_text


def _rects_overlap(a, b, gap=0.0):
    return not (
        a[2] + gap <= b[0] or b[2] + gap <= a[0]
        or a[3] + gap <= b[1] or b[3] + gap <= a[1]
    )


def layout_reference_overlay_rects(
    canvas_w, canvas_h, *, crosshair, feature_rect, sizes, x_side, y_side,
    margin=8, gap=12, overlap_fn=_rects_overlap,
):
    """Lay out CAD reference controls without covering the selected feature."""
    cw, ch = float(canvas_w), float(canvas_h)
    cx, cy = map(float, crosshair)
    fl, ft, fr, fb = map(float, feature_rect)
    occupied = [(fl-gap, ft-gap, fr+gap, fb+gap)]
    result = {}

    def rect_for(center, size):
        x, y = center
        w, h = size
        return (x-w/2.0, y-h/2.0, x+w/2.0, y+h/2.0)

    def fits(rect):
        left, top, right, bottom = rect
        if left < margin or top < margin or right > cw-margin or bottom > ch-margin:
            return False
        return all(not overlap_fn(rect, other, gap=4) for other in occupied)

    def choose(name, candidates):
        size = sizes[name]
        for center in candidates:
            rect = rect_for(center, size)
            if fits(rect):
                result[name] = rect
                occupied.append(rect)
                return
        w, h = size
        fallback = [
            (margin+w/2, margin+h/2), (cw-margin-w/2, margin+h/2),
            (margin+w/2, ch-margin-h/2), (cw-margin-w/2, ch-margin-h/2),
            (cw/2, margin+h/2), (cw/2, ch-margin-h/2),
            (margin+w/2, ch/2), (cw-margin-w/2, ch/2),
        ]
        for center in fallback:
            rect = rect_for(center, size)
            if fits(rect):
                result[name] = rect
                occupied.append(rect)
                return
        x = min(max(cx, margin+w/2), cw-margin-w/2)
        y = min(max(cy, margin+h/2), ch-margin-h/2)
        rect = rect_for((x, y), size)
        result[name] = rect
        occupied.append(rect)

    x_pref_left = x_side == "left"
    left_near = fl - gap - sizes["x_edge"][0]/2
    right_near = fr + gap + sizes["x_edge"][0]/2
    left_far = left_near - gap - sizes["x_neighbor"][0]
    right_far = right_near + gap + sizes["x_neighbor"][0]
    if x_pref_left:
        choose("x_edge", [(left_near, cy), (right_near, cy)])
        choose("x_neighbor", [(left_far, cy), (right_far, cy), (right_near, cy)])
    else:
        choose("x_edge", [(right_near, cy), (left_near, cy)])
        choose("x_neighbor", [(right_far, cy), (left_far, cy), (left_near, cy)])

    y_pref_top = y_side == "top"
    top_near = ft - gap - sizes["y_edge"][1]/2
    bottom_near = fb + gap + sizes["y_edge"][1]/2
    top_far = top_near - gap - sizes["y_neighbor"][1]
    bottom_far = bottom_near + gap + sizes["y_neighbor"][1]
    if y_pref_top:
        choose("y_edge", [(cx, top_near), (cx, bottom_near)])
        choose("y_neighbor", [(cx, top_far), (cx, bottom_far), (cx, bottom_near)])
    else:
        choose("y_edge", [(cx, bottom_near), (cx, top_near)])
        choose("y_neighbor", [(cx, bottom_far), (cx, top_far), (cx, top_near)])

    pw, ph = sizes["panel"]
    choose("panel", [
        (fr + gap + pw/2, fb + gap + ph/2),
        (fl - gap - pw/2, fb + gap + ph/2),
        (fr + gap + pw/2, ft - gap - ph/2),
        (fl - gap - pw/2, ft - gap - ph/2),
    ])
    return result


def draw_phase6_annotation_projection(
    canvas, render_data, transform, *, part_key="", strict=False,
    projection_builder=build_engineering_drawing_projection,
):
    """Render annotation-only Engineering Drawing projection in 2D."""
    projection = projection_builder(
        render_data, part_key=str(part_key or ""), strict=bool(strict)
    )
    dimensions_by_semantic_id = {
        str(getattr(item, "semantic_id", "") or ""): str(item.axis).lower()
        for item in tuple(getattr(projection.annotation_plan, "overall_dimensions", ()) or ())
        if str(getattr(item, "semantic_id", "") or "")
    }
    for primitive in projection.primitives:
        layer = str(getattr(primitive, "layer", "") or "").upper()
        if isinstance(primitive, LinePrimitive):
            p1 = transform.world_to_canvas(primitive.p1)
            p2 = transform.world_to_canvas(primitive.p2)
            canvas.create_line(
                *p1, *p2,
                fill=("#30d158" if layer == "DIMENSION" else "#ffd60a"),
                width=1.2,
                tags=("phase6_engineering_annotation", layer.lower()),
            )
        elif isinstance(primitive, TextPrimitive):
            x, y = transform.world_to_canvas(primitive.insert)
            semantic_id = str(getattr(primitive, "semantic_id", "") or "")
            axis = dimensions_by_semantic_id.get(semantic_id)
            angle = 90 if layer == "DIMENSION" and axis == "y" else 0
            anchor_name = (
                tk.CENTER
                if int(getattr(primitive, "attachment_point", 1)) == 5
                else tk.SW
            )
            canvas.create_text(
                x, y, text=str(primitive.text),
                fill=("#30d158" if layer == "DIMENSION" else "#ffd60a"),
                font=("Consolas", 9, "bold"),
                anchor=anchor_name,
                angle=angle,
                tags=("phase6_engineering_annotation", layer.lower()),
            )
    return projection


def draw_phase6_corner_dimension_overlay(
    canvas, render_data, canvas_width, *,
    text_builder=render_data_corner_dimension_text,
):
    """Draw per-corner sizes measured from the PartRenderData used by 3D."""
    text = text_builder(render_data)
    canvas.create_text(
        max(25, float(canvas_width) - 25), 42,
        anchor=tk.NE,
        text=text,
        fill="#ffd60a",
        justify=tk.RIGHT,
        font=("Microsoft JhengHei", 9, "bold"),
        width=max(180, int(float(canvas_width) * 0.46)),
        tags=("phase6_corner_dimensions",),
    )
    return text
