# -*- coding: utf-8 -*-
"""Headless physical DrawingScene annotation paths for single-piece 3D.

Canonical Fold mapping from the already-resolved material/scene; no independent
manufacturing geometry, no DXF authoring and no Tk/Matplotlib ownership.
"""
from __future__ import annotations

import math

from .final_scene_box_body_bend_lines import _mappers, _map_point
from .assembly_geometry_primitives import place_assembly_points
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


def _manual_ink_fold_fractions(start, end, fold_guides):
    """Find actual *finite* BEND intersections on this one ink segment.

    The same Fold guides are used by the formed-material mapper.  Crossing a
    station outside its physically finite span cannot introduce a kink.
    """
    x0, y0 = float(start.x), float(start.y)
    dx, dy = float(end.x) - x0, float(end.y) - y0
    fractions = []
    for guide in fold_guides:
        axis = str(getattr(guide, "axis", "") or "")
        if axis == "x" and abs(dx) > 1e-12:
            t = (float(guide.position) - x0) / dx
            cross = y0 + t * dy
        elif axis == "y" and abs(dy) > 1e-12:
            t = (float(guide.position) - y0) / dy
            cross = x0 + t * dx
        else:
            continue
        if (1e-12 < t < 1.0 - 1e-12
                and float(guide.span_start) - 1e-8 <= cross
                <= float(guide.span_end) + 1e-8):
            fractions.append(t)
    return tuple(fractions)


def _round_ink_display_angles(primitive, fold_guides):
    """Include exact finite BEND crossings in a display-only circle path."""
    x, y, r = primitive.center.x, primitive.center.y, primitive.radius
    angles = [2.0 * math.pi * i / 64.0 for i in range(65)]
    for guide in fold_guides:
        axis = guide.axis
        if axis not in {"x", "y"}:
            continue
        is_x = axis == "x"
        coord = (guide.position - (x if is_x else y)) / r
        if not -1.0 <= coord <= 1.0:
            continue
        angle = math.acos(coord) if is_x else math.asin(coord)
        for theta in (angle, -angle if is_x else math.pi - angle):
            cross = y + r * math.sin(theta) if is_x else x + r * math.cos(theta)
            if guide.span_start - 1e-8 <= cross <= guide.span_end + 1e-8:
                angles.append(theta % (2.0 * math.pi))
    unique = []
    for theta in sorted(angles):
        if not unique or theta - unique[-1] > 1e-12:
            unique.append(theta)
    return tuple(unique)


def project_independent_scene_annotation_paths(
    scene, x_profile, y_profile, fold_guides=(),
):
    """Yield immutable (MARKING|BLIND_HOLE, points) from real DrawingScene only.

    Other circles retain their original 64-segment display. Manual marking
    circles add real fold crossings. Display only, never physical CUTTING.
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
            from .operator_manual_marking import is_manual_round_mark
            angles = (_round_ink_display_angles(primitive, fold_guides)
                      if is_manual_round_mark(primitive)
                      else tuple(2.0 * math.pi * i / 64.0 for i in range(65)))
            pts = tuple(
                _map_point_xy(
                    float(primitive.center.x) + float(primitive.radius) * math.cos(theta),
                    float(primitive.center.y) + float(primitive.radius) * math.sin(theta),
                    map_x, map_y,
                )
                for theta in angles
            )
        elif isinstance(primitive, LinePrimitive):
            pts = (
                _map_point(primitive.p1, map_x, map_y),
                _map_point(primitive.p2, map_x, map_y),
            )
        else:
            if (layer == "MARKING" and
                    getattr(primitive, "semantic_id", None) == "WHD_MANUAL_MARKING_V1"):
                # A midpoint-only/endpoint-only world projection cuts through
                # folded faces when the real source stroke crosses a finite BEND.
                # Insert exact physical finite-BEND crossings in *each actual
                # ink segment*, even when a 1-mm grid misses the hinge.
                # This preserves the formed surface without drawing through it.
                # 2D/DXF ink and dash gaps remain unchanged.
                flat = tuple(primitive.points)
                sampled = []
                for start, end in zip(flat, flat[1:]):
                    distance = math.hypot(end.x - start.x, end.y - start.y)
                    steps = max(1, min(8192, math.ceil(distance)))
                    fractions = sorted(
                        tuple(index / steps for index in range(steps + 1))
                        + _manual_ink_fold_fractions(
                            start, end, fold_guides,
                        )
                    )
                    unique = []
                    for frac in fractions:
                        if not unique or abs(frac - unique[-1]) > 1e-12:
                            unique.append(frac)
                    for frac in unique:
                        if sampled and frac == 0.0:
                            continue
                        sampled.append(_map_point_xy(
                            float(start.x) + (float(end.x) - float(start.x)) * frac,
                            float(start.y) + (float(end.y) - float(start.y)) * frac,
                            map_x, map_y,
                        ))
                pts = tuple(sampled)
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


def project_independent_cutting_hole_rim_segments(
    material, x_profile, y_profile, fold_guides=(), *,
    local_reference=None, placement=None, dimensions=None,
    offset=(0.0, 0.0, 0.0),
):
    """Only true material CUTTING inner rings; never a tessellation/BLIND_HOLE."""
    polygons = (
        (material,) if getattr(material, "geom_type", "") == "Polygon"
        else tuple(getattr(material, "geoms", ()) or ())
    )
    rings = tuple(
        ring for polygon in polygons
        if getattr(polygon, "geom_type", "") == "Polygon"
        for ring in polygon.interiors
    )
    if not rings:
        return ()
    map_x, map_y = _mappers(x_profile, y_profile, fold_guides)
    segments = []
    for ring in rings:
        local = tuple(
            _map_point_xy(x, y, map_x, map_y) for x, y in ring.coords
        )
        points = (
            place_assembly_points(
                local, local_reference, placement, dimensions, offset,
            ) if local_reference is not None else local
        )
        segments.extend(
            (u, v) for u, v in zip(points, points[1:])
            if any(abs(u[i] - v[i]) > 1e-9 for i in range(3))
        )
    return tuple(segments)


def project_independent_fixed_plate_hinge_segment(render_data, view_mesh):
    """MID-skin 3D hinge from verified Engine view; never replace DXF BEND23."""
    hinge_y = getattr(view_mesh, "fixed_plate_hinge_y", None)
    if hinge_y is None:
        return ()
    metadata = getattr(render_data, "metadata", None) or {}
    source_width = float(metadata["source_flat_dimensions"][0])
    map_x, map_y = _mappers(
        view_mesh.x_profile, view_mesh.y_profile, view_mesh.fold_guides,
    )
    return (
        _map_point_xy(0.0, float(hinge_y), map_x, map_y),
        _map_point_xy(source_width, float(hinge_y), map_x, map_y),
    )
