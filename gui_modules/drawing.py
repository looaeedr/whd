"""Stateless Canvas presentation helpers extracted from the legacy GUI host."""

from ae_engine.sheetmetal_drawing import CirclePrimitive, LinePrimitive, PolylinePrimitive


def _corner_preview_canvas_point(point, *, ox, oy, scale, span, flip_y=True):
    """Map semantic preview coordinates to the operator-facing canvas."""
    canvas_y = oy - (span - point.y) * scale if flip_y else oy - point.y * scale
    return (
        ox + point.x * scale,
        canvas_y,
    )


def _corner_preview_flip_y_for_target(target_key):
    """Top thumbnails stay flipped; bottom thumbnails use their original orientation."""
    return str(target_key or "").strip() not in {"bottom", "bottom_left", "bottom_right"}


def render_drawing_scene(canvas, scene, transform, *, skip_layers=()):
    skip = set(skip_layers)
    for primitive in scene.primitives:
        if primitive.layer in skip:
            continue
        if isinstance(primitive, PolylinePrimitive):
            coords = []
            for point in primitive.points:
                coords.extend(transform.world_to_canvas(point))
            if len(coords) < 4:
                continue
            color = {"MARKING":"#8e8e93", "BLIND_HOLE":"#ff453a", "DATUM":"#bf5af2"}.get(primitive.layer, "#30d158")
            if primitive.layer == "BEND":
                color = "#0a84ff"
            if primitive.closed and len(coords) >= 6:
                canvas.create_polygon(*coords, outline=color, fill="", width=2 if primitive.layer == "CUTTING" else 1.5)
            else:
                kwargs = {"fill": color, "width": 1.5}
                if primitive.layer == "BEND":
                    kwargs["dash"] = (6, 4)
                canvas.create_line(*coords, **kwargs)
        elif isinstance(primitive, LinePrimitive):
            p1 = transform.world_to_canvas(primitive.p1)
            p2 = transform.world_to_canvas(primitive.p2)
            color = "#0a84ff" if primitive.layer == "BEND" else {"MARKING":"#8e8e93", "BLIND_HOLE":"#ff453a", "DATUM":"#bf5af2"}.get(primitive.layer, "#30d158")
            kwargs = {"fill": color, "width": 1.5}
            if primitive.layer == "BEND":
                kwargs["dash"] = (6, 4)
            canvas.create_line(*p1, *p2, **kwargs)
        elif isinstance(primitive, CirclePrimitive):
            cx, cy = transform.world_to_canvas(primitive.center)
            r_px = primitive.radius * transform.scale
            color = {"CUTTING":"#30d158", "BLIND_HOLE":"#ff453a", "MARKING":"#8e8e93", "DATUM":"#bf5af2"}.get(primitive.layer, "#8e8e93")
            canvas.create_oval(cx-r_px, cy-r_px, cx+r_px, cy+r_px, outline=color, width=1.5)
