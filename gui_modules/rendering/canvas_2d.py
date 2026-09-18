"""Stateless rendering of already-resolved 2D material/features."""

import ae_engine.ae as ae

from ae_engine.sheetmetal_drawing import DrawingScene, PolylinePrimitive
from ae_engine.sheetmetal_features import (
    ResolvedCircle,
    ResolvedProfile,
    ResolvedRect,
    resolve_surface_features,
)
from gui_modules.drawing import render_drawing_scene


def render_structural_result(canvas, result, transform, tags=None):
    polygon_coords = []
    for point in result.outline:
        cx, cy = transform.world_to_canvas(point)
        polygon_coords.extend([cx, cy])
    polygon_kwargs = {"outline": "#30d158", "fill": "", "width": 2}
    if tags is not None:
        polygon_kwargs["tags"] = tags
    if len(polygon_coords) >= 6:
        canvas.create_polygon(*polygon_coords, **polygon_kwargs)

    for bend in result.bends:
        p1 = transform.world_to_canvas(bend.p1)
        p2 = transform.world_to_canvas(bend.p2)
        line_kwargs = {"fill": "#0a84ff", "width": 1.5, "dash": (6, 4)}
        if tags is not None:
            line_kwargs["tags"] = tags
        canvas.create_line(*p1, *p2, **line_kwargs)


def render_secondary_scene(canvas, scene, transform, *, scene_renderer=render_drawing_scene):
    """Render baseline secondary geometry without structural outline/BEND duplication."""
    secondary = DrawingScene()
    skipped_primary_outline = False
    for primitive in scene.primitives:
        if primitive.layer == "BEND":
            continue
        if (
            not skipped_primary_outline
            and isinstance(primitive, PolylinePrimitive)
            and primitive.layer == "CUTTING"
        ):
            skipped_primary_outline = True
            continue
        secondary.add(primitive)
    scene_renderer(canvas, secondary, transform)


def render_resolved_features(canvas, features, transform, *, color="#ff9f0a"):
    """Render already-resolved world-space features; never derive manufacturing coordinates."""
    for feature in features:
        layer = getattr(feature, "layer", "CUTTING")
        draw_color = {
            "MARKING": "#8e8e93",
            "BLIND_HOLE": "#ff453a",
            "DATUM": "#bf5af2",
        }.get(layer, color)
        if isinstance(feature, ResolvedCircle):
            cx, cy = transform.world_to_canvas(feature.center)
            r_px = feature.radius * transform.scale
            canvas.create_oval(
                cx-r_px, cy-r_px, cx+r_px, cy+r_px,
                outline=draw_color, width=2,
            )
            if feature.add_centerline:
                canvas.create_line(
                    cx-r_px, cy, cx+r_px, cy,
                    fill="#bf5af2", width=1,
                )
        elif isinstance(feature, ResolvedProfile) and getattr(feature, "layered_profiles", ()):
            for sub_layer, points, closed in feature.layered_profiles:
                sub_color = {
                    "MARKING": "#8e8e93",
                    "BLIND_HOLE": "#ff453a",
                    "DATUM": "#bf5af2",
                }.get(sub_layer, color)
                coords = []
                for point in points:
                    coords.extend(transform.world_to_canvas(point))
                if len(coords) >= 4:
                    if closed and len(coords) >= 6:
                        canvas.create_polygon(
                            *coords, outline=sub_color, fill="", width=2
                        )
                    else:
                        canvas.create_line(*coords, fill=sub_color, width=2)
        elif isinstance(feature, (ResolvedRect, ResolvedProfile)):
            coords = []
            for point in feature.points:
                coords.extend(transform.world_to_canvas(point))
            if len(coords) >= 6:
                canvas.create_polygon(
                    *coords, outline=draw_color, fill="", width=2
                )


def render_surface_user_features(
    canvas, surface, features, width, height, transform, *,
    resolver=resolve_surface_features, feature_renderer=render_resolved_features,
):
    if not features:
        return
    resolved = resolver(surface, features, width, height)
    feature_renderer(canvas, resolved, transform, color="#ff9f0a")


def feature_surface_from_drawing_scene(surface_id, scene, *, ae_module=ae):
    """Delegate CUTTING-outline authority to AE; renderer owns no geometry resolver."""
    return ae_module.feature_surface_from_drawing_scene(surface_id, scene)
