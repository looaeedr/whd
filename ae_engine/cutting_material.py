# -*- coding: utf-8 -*-
"""Canonical CUTTING reconstruction shared by manufacturing and DXF acceptance.

This module is production-owned geometry policy. Validation may call it to
interpret serialized CUTTING entities, but validation must never supply or
derive the policy constants used here.
"""
from __future__ import annotations

from collections import defaultdict
from math import floor, hypot

from shapely.geometry import LineString
from shapely.ops import polygonize, unary_union


def _snapped_linework_polygons(linework, primary):
    """Polygonize segmented CUTTING using canonical manufacturing endpoint tolerance."""
    minx0, miny0, maxx0, maxy0 = map(float, primary.bounds)
    span = max(maxx0 - minx0, maxy0 - miny0, 1.0)
    endpoint_tol = max(0.05, min(0.25, span * 2.0e-4))

    endpoints = []
    coords_by_line = []
    for line in tuple(linework or ()):
        coords = list(line.coords)
        if len(coords) < 2:
            continue
        coords_by_line.append(coords)
        endpoints.extend([
            tuple(map(float, coords[0])),
            tuple(map(float, coords[-1])),
        ])
    if not coords_by_line:
        return ()

    parent = list(range(len(endpoints)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    buckets = defaultdict(list)
    cell = endpoint_tol
    for i, (x, y) in enumerate(endpoints):
        gx, gy = int(floor(x / cell)), int(floor(y / cell))
        for nx in (gx - 1, gx, gx + 1):
            for ny in (gy - 1, gy, gy + 1):
                for j in buckets.get((nx, ny), ()):
                    qx, qy = endpoints[j]
                    if hypot(x - qx, y - qy) <= endpoint_tol:
                        union(i, j)
        buckets[(gx, gy)].append(i)

    grouped = defaultdict(list)
    for i, point in enumerate(endpoints):
        grouped[find(i)].append(point)

    snapped_point = {}
    for root, points in grouped.items():
        snapped_point[root] = (
            sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points),
        )

    snapped_lines = []
    for line_index, coords in enumerate(coords_by_line):
        a = snapped_point[find(line_index * 2)]
        b = snapped_point[find(line_index * 2 + 1)]
        if a == b:
            continue
        mapped = [a] + [
            tuple(map(float, point)) for point in coords[1:-1]
        ] + [b]
        snapped_lines.append(LineString(mapped))

    if not snapped_lines:
        return ()
    return tuple(
        polygon
        for polygon in polygonize(unary_union(snapped_lines))
        if float(polygon.area) > 1e-9
    )


def material_from_cutting_components(*, primary, secondary=(), linework=()):
    """Resolve Final Material from canonical CUTTING components.

    primary is the structural sheet outline when the scene owns one.
    secondary contains already-closed cutouts such as circles/profiles.
    linework contains segmented CUTTING profiles, including legacy LINE/ARC
    geometry flattened into line strings.
    """
    secondary = list(secondary or ())
    linework = list(linework or ())

    if primary is None:
        if linework:
            polygons = [
                polygon
                for polygon in polygonize(unary_union(linework))
                if float(polygon.area) > 1e-9
            ]
            if polygons:
                primary = max(polygons, key=lambda polygon: float(polygon.area))
                secondary.extend(
                    polygon for polygon in polygons if polygon is not primary
                )
        if primary is None:
            raise ValueError("CUTTING has no structural material contour")
    elif linework:
        secondary.extend(_snapped_linework_polygons(linework, primary))

    minx, miny, maxx, maxy = map(float, primary.bounds)
    sx, sy = max(1.0, maxx - minx), max(1.0, maxy - miny)
    tolx, toly = max(1e-6, sx * 1e-4), max(1e-6, sy * 1e-4)

    holes = []
    for candidate in secondary:
        if candidate.is_empty or float(candidate.area) <= 1e-9:
            continue
        cb = tuple(map(float, candidate.bounds))
        same_sheet_bounds = (
            abs(cb[0] - minx) <= tolx
            and abs(cb[1] - miny) <= toly
            and abs(cb[2] - maxx) <= tolx
            and abs(cb[3] - maxy) <= toly
        )
        if same_sheet_bounds:
            continue
        if primary.buffer(1e-7).covers(candidate.representative_point()):
            holes.append(candidate.intersection(primary))

    material = primary if not holes else primary.difference(unary_union(holes))
    if not material.is_valid:
        material = material.buffer(0)
    if material.is_empty:
        raise ValueError("final material is empty")
    return material
