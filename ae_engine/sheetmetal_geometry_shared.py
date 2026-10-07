# -*- coding: utf-8 -*-
"""Shared sheet-metal polygon placement, clipping, and ring helpers."""
from __future__ import annotations

import math
from typing import Iterable

try:
    from shapely.geometry import Polygon, box, LineString, Point
    from shapely.ops import unary_union
except Exception:  # pragma: no cover
    Polygon = None
    box = None
    LineString = None
    Point = None
    unary_union = None

from .sheetmetal_geometry_core import (
    DEFAULT_TOLERANCE,
    GeometryError,
    Vec2,
    BendLine,
    ResolvedCornerRelief,
)

def _local_cross_slot_polygon(relief: ResolvedCornerRelief):
    """Build an optional rounded-end slot in canonical +U/+V corner coordinates."""
    if relief.slot_width is None:
        return None
    if relief.slot_straight_depth is None or relief.slot_radius is None:
        raise GeometryError("十字截角槽參數不完整")
    width = float(relief.slot_width)
    straight = float(relief.slot_straight_depth)
    radius = float(relief.slot_radius)
    u0 = float(relief.primary_u) - width
    u1 = float(relief.primary_u)
    tangent_v = float(relief.primary_v) + straight
    if u0 < -DEFAULT_TOLERANCE:
        raise GeometryError("十字截角槽超出主截角U範圍")
    rectangle = box(max(0.0, u0), float(relief.primary_v), u1, tangent_v)
    axis_left = u0 + radius
    axis_right = u1 - radius
    if axis_right < axis_left - DEFAULT_TOLERANCE:
        raise GeometryError("十字截角槽R與槽寬不相容")
    if abs(axis_right - axis_left) <= DEFAULT_TOLERANCE:
        cap = Point(((axis_left + axis_right) / 2.0, tangent_v)).buffer(radius)
    else:
        cap = LineString(((axis_left, tangent_v), (axis_right, tangent_v))).buffer(
            radius, cap_style=1, join_style=1
        )
    cap = cap.intersection(box(u0, tangent_v, u1, tangent_v + radius + DEFAULT_TOLERANCE))
    return unary_union((rectangle, cap))

def _mirror_local_corner_polygon(poly, *, corner_name: str, width: float, height: float):
    from shapely.affinity import scale, translate
    if corner_name == "bottom_left":
        return poly
    if corner_name == "bottom_right":
        return translate(scale(poly, xfact=-1.0, yfact=1.0, origin=(0.0, 0.0)), xoff=float(width))
    if corner_name == "top_left":
        return translate(scale(poly, xfact=1.0, yfact=-1.0, origin=(0.0, 0.0)), yoff=float(height))
    if corner_name == "top_right":
        mirrored = scale(poly, xfact=-1.0, yfact=-1.0, origin=(0.0, 0.0))
        return translate(mirrored, xoff=float(width), yoff=float(height))
    raise GeometryError(f"unknown physical corner: {corner_name}")

def _placed_corner_cut_polygons(
    *,
    corner_name: str,
    relief: ResolvedCornerRelief,
    width: float,
    height: float,
):
    """Place a canonical inward +U/+V corner cut at one physical blank corner."""
    pu, pv = relief.primary_u, relief.primary_v
    if corner_name == "bottom_left":
        primary = box(0.0, 0.0, pu, pv)
        secondary = (
            None if relief.secondary_u is None or relief.secondary_depth is None
            else box(0.0, pv, relief.secondary_u, pv + relief.secondary_depth)
        )
    elif corner_name == "bottom_right":
        primary = box(width - pu, 0.0, width, pv)
        secondary = (
            None if relief.secondary_u is None or relief.secondary_depth is None
            else box(width - relief.secondary_u, pv, width, pv + relief.secondary_depth)
        )
    elif corner_name == "top_left":
        primary = box(0.0, height - pv, pu, height)
        secondary = (
            None if relief.secondary_u is None or relief.secondary_depth is None
            else box(0.0, height - pv - relief.secondary_depth, relief.secondary_u, height - pv)
        )
    elif corner_name == "top_right":
        primary = box(width - pu, height - pv, width, height)
        secondary = (
            None if relief.secondary_u is None or relief.secondary_depth is None
            else box(
                width - relief.secondary_u,
                height - pv - relief.secondary_depth,
                width,
                height - pv,
            )
        )
    else:
        raise GeometryError(f"unknown physical corner: {corner_name}")
    slot_local = _local_cross_slot_polygon(relief)
    slot = (
        None if slot_local is None
        else _mirror_local_corner_polygon(
            slot_local, corner_name=corner_name, width=width, height=height
        )
    )
    return [
        poly for poly in (primary, secondary, slot)
        if poly is not None and not poly.is_empty
    ]

def placed_corner_cut_polygons(
    *,
    corner_name: str,
    relief: ResolvedCornerRelief,
    width: float,
    height: float,
):
    """Public geometry seam for placing one already-resolved CornerType cut."""
    return _placed_corner_cut_polygons(
        corner_name=corner_name, relief=relief, width=width, height=height
    )

def _clip_axis_bend(name: str, line: LineString, material, vertical: bool) -> BendLine:
    clipped = material.intersection(line)
    if clipped.is_empty:
        raise GeometryError(f"bend {name} does not intersect material")
    if clipped.geom_type == "MultiLineString":
        clipped = max(clipped.geoms, key=lambda geom: geom.length)
    if clipped.geom_type != "LineString":
        raise GeometryError(f"bend {name} did not clip to a line")
    coords = list(clipped.coords)
    a = Vec2(float(coords[0][0]), float(coords[0][1]))
    b = Vec2(float(coords[-1][0]), float(coords[-1][1]))
    if vertical:
        if a.y > b.y:
            a, b = b, a
    elif a.x > b.x:
        a, b = b, a
    return BendLine(name, a, b)

def _require_shapely() -> None:
    if Polygon is None or box is None or unary_union is None:
        raise GeometryError(
            "Shapely is required for boolean outline generation in this build"
        )

def _normalize_ring(points: Iterable[tuple[float, float]]) -> list[Vec2]:
    coords = [Vec2(float(x), float(y)) for x, y in points]
    if len(coords) < 4:
        raise GeometryError("outline exterior has too few points")
    if coords[0] == coords[-1]:
        coords = coords[:-1]

    # Deterministic start: left-most surviving point on the bottom edge.
    min_y = min(p.y for p in coords)
    bottom_indices = [
        i for i, p in enumerate(coords) if math.isclose(p.y, min_y, abs_tol=DEFAULT_TOLERANCE)
    ]
    start = min(bottom_indices, key=lambda i: coords[i].x)

    rotated = coords[start:] + coords[:start]
    rotated.append(rotated[0])
    return rotated
