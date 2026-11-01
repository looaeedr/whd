# -*- coding: utf-8 -*-
"""Headless physical DrawingScene annotation paths for single-piece 3D.

Canonical Fold mapping from the already-resolved material/scene; no independent
manufacturing geometry, no DXF authoring and no Tk/Matplotlib ownership.
"""
from __future__ import annotations

import math

from .final_scene_box_body_bend_lines import _mappers, _map_point
from .sheetmetal_drawing import LinePrimitive, PolylinePrimitive, CirclePrimitive


def project_independent_scene_bend_segments(scene, x_profile, y_profile, fold_guides=()):
    """Only actual manufacturing BEND LinePrimitive, in local formed 3D."""
    bends = tuple(
        row for row in getattr(scene, "primitives", ())
        if isinstance(row, LinePrimitive) and str(row.layer).upper() == "BEND"
    )
    if not bends:
        return ()
    map_x, map_y = _mappers(x_profile, y_profile, fold_guides)
    return tuple((
        _map_point(row.p1, map_x, map_y),
        _map_point(row.p2, map_x, map_y),
    ) for row in bends)


def project_independent_scene_annotation_paths(
    scene, x_profile, y_profile, fold_guides=(),
):
    """Yield immutable (MARKING|BLIND_HOLE, points) from real DrawingScene only.

    The original 64-segment circle and closed-polyline behavior are retained
    exactly. Only display paths are returned, never new physical CUTTING.
    """
    primitives = tuple(
        (str(getattr(row, "layer", "") or "").upper(), row)
        for row in getattr(scene, "primitives", ())
    )
    eligible = tuple(
        (layer, row) for layer, row in primitives
        if layer in {"MARKING", "BLIND_HOLE"} and
        isinstance(row, (CirclePrimitive, LinePrimitive, PolylinePrimitive))
    )
    if not eligible:
        return ()
    map_x, map_y = _mappers(x_profile, y_profile, fold_guides)
    paths = []
    for layer, primitive in eligible:
        if isinstance(primitive, CirclePrimitive):
            pts = tuple(
                _map_point_xy(
                    float(primitive.center.x) + float(primitive.radius) * math.cos(2.0 * math.pi * i / 64.0),
                    float(primitive.center.y) + float(primitive.radius) * math.sin(2.0 * math.pi * i / 64.0),
                    map_x, map_y,
                )
                for i in range(65)
            )
        elif isinstance(primitive, LinePrimitive):
            pts = (
                _map_point(primitive.p1, map_x, map_y),
                _map_point(primitive.p2, map_x, map_y),
            )
        else:
            pts = tuple(_map_point(p, map_x, map_y) for p in primitive.points)
            if primitive.closed and pts:
                pts = pts + (pts[0],)
        if len(pts) >= 2:
            paths.append((layer, pts))
    return tuple(paths)


def _map_point_xy(x, y, map_x, map_y):
    ux, zx = map_x(float(x), float(y))
    uy, zy = map_y(float(y), float(x))
    return (ux, uy, zx + zy)
