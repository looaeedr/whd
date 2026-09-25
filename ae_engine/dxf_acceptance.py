# -*- coding: utf-8 -*-
"""Independent acceptance of already-saved manufacturing DXF files.

This module is deliberately downstream of serialization.  It reopens the
actual DXF bytes with ezdxf and reconstructs what was written; it never calls
AE's scene serializer to derive the actual side of the comparison.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import hypot
from pathlib import Path
from typing import Any, Mapping

import ezdxf
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import polygonize, unary_union

from .sheetmetal_drawing import (
    CirclePrimitive,
    LinePrimitive,
    PolylinePrimitive,
    TextPrimitive,
)


@dataclass(frozen=True)
class DxfAcceptanceIssue:
    category: str
    detail: str
    expected: Any = None
    actual: Any = None


@dataclass(frozen=True)
class DxfAcceptanceResult:
    ok: bool
    issues: tuple[DxfAcceptanceIssue, ...]


@dataclass(frozen=True)
class ResolvedDxfAcceptanceIssue:
    part_id: str
    category: str
    detail: str
    expected: Any = None
    actual: Any = None


@dataclass(frozen=True)
class ResolvedDxfAcceptanceResult:
    ok: bool
    issues: tuple[ResolvedDxfAcceptanceIssue, ...]
    part_results: Mapping[str, DxfAcceptanceResult]


def _entity_kind(entity) -> str | None:
    kind = entity.dxftype()
    if kind == "LWPOLYLINE":
        return "POLYLINE"
    if kind == "LINE":
        return "LINE"
    if kind == "CIRCLE":
        return "CIRCLE"
    if kind in {"MTEXT", "TEXT"}:
        return "TEXT"
    return None


def _expected_kind(primitive) -> str | None:
    if isinstance(primitive, PolylinePrimitive):
        return "POLYLINE"
    if isinstance(primitive, LinePrimitive):
        return "LINE"
    if isinstance(primitive, CirclePrimitive):
        return "CIRCLE"
    if isinstance(primitive, TextPrimitive):
        return "TEXT"
    return None


def _scene_counts(scene) -> Counter:
    counts = Counter()
    for primitive in getattr(scene, "primitives", ()):
        kind = _expected_kind(primitive)
        if kind is not None:
            counts[(str(getattr(primitive, "layer", "")).upper(), kind)] += 1
    return counts


def _dxf_counts(msp) -> Counter:
    counts = Counter()
    for entity in msp:
        kind = _entity_kind(entity)
        if kind is not None:
            counts[(str(entity.dxf.layer).upper(), kind)] += 1
    return counts


def _poly_from_points(points):
    poly = Polygon(points)
    if not poly.is_valid:
        poly = poly.buffer(0)
    return poly


def _polygonize_linework_with_tolerance(linework, tolerance: float):
    """Reconnect DXF CUTTING endpoints only inside verifier tolerance."""
    coords_by_line = []
    endpoints = []
    for line in tuple(linework or ()):
        coords = list(line.coords)
        if len(coords) < 2:
            continue
        coords_by_line.append(coords)
        endpoints.extend((
            tuple(map(float, coords[0])),
            tuple(map(float, coords[-1])),
        ))
    if not coords_by_line:
        return ()

    tolerance = max(0.0, float(tolerance))
    parent = list(range(len(endpoints)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left, right):
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for i, (x1, y1) in enumerate(endpoints):
        for j in range(i):
            x2, y2 = endpoints[j]
            if hypot(x1 - x2, y1 - y2) <= tolerance:
                union(i, j)

    groups = {}
    for index, point in enumerate(endpoints):
        groups.setdefault(find(index), []).append(point)

    snapped = {}
    for root, points in groups.items():
        snapped[root] = (
            sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points),
        )

    snapped_lines = []
    for line_index, coords in enumerate(coords_by_line):
        first = snapped[find(line_index * 2)]
        last = snapped[find(line_index * 2 + 1)]
        if first == last:
            continue
        mapped = [first]
        mapped.extend(tuple(map(float, point)) for point in coords[1:-1])
        mapped.append(last)
        snapped_lines.append(LineString(mapped))

    if not snapped_lines:
        return ()
    return tuple(
        poly
        for poly in polygonize(unary_union(snapped_lines))
        if float(poly.area) > 1e-9
    )


def _actual_material(msp, coordinate_tolerance: float):
    """Reconstruct saved CUTTING under the verifier's tolerance contract."""
    from .cutting_material import material_from_cutting_components

    primary = None
    secondary = []
    linework = []

    for entity in msp:
        if str(entity.dxf.layer).upper() != "CUTTING":
            continue
        kind = entity.dxftype()
        if kind == "LWPOLYLINE":
            pts = [(float(p[0]), float(p[1])) for p in entity.get_points()]
            if bool(entity.closed) and len(pts) >= 3:
                poly = _poly_from_points(pts)
                if poly.is_empty or float(poly.area) <= 1e-9:
                    continue
                if primary is None:
                    primary = poly
                else:
                    secondary.append(poly)
            elif len(pts) >= 2:
                linework.extend(
                    LineString((a, b)) for a, b in zip(pts, pts[1:]) if a != b
                )
        elif kind == "LINE":
            a = (float(entity.dxf.start.x), float(entity.dxf.start.y))
            b = (float(entity.dxf.end.x), float(entity.dxf.end.y))
            if a != b:
                linework.append(LineString((a, b)))
        elif kind == "CIRCLE" and float(entity.dxf.radius) > 0:
            secondary.append(
                Point(float(entity.dxf.center.x), float(entity.dxf.center.y)).buffer(
                    float(entity.dxf.radius), quad_segs=32
                )
            )

    linework_polygons = list(
        _polygonize_linework_with_tolerance(linework, coordinate_tolerance)
    )
    if primary is None and linework_polygons:
        primary = max(linework_polygons, key=lambda poly: float(poly.area))
        linework_polygons.remove(primary)
    secondary.extend(linework_polygons)

    return material_from_cutting_components(
        primary=primary,
        secondary=secondary,
        linework=(),
    )


def _expected_bends(render_data):
    rows = []
    for guide in tuple(getattr(render_data, "fold_guides", ()) or ()):
        rows.append(
            (
                str(guide.axis).lower(),
                float(guide.position),
                min(float(guide.span_start), float(guide.span_end)),
                max(float(guide.span_start), float(guide.span_end)),
            )
        )
    return tuple(sorted(rows))


def _actual_bends(msp, tolerance: float):
    rows = []
    for entity in msp:
        if entity.dxftype() != "LINE" or str(entity.dxf.layer).upper() != "BEND":
            continue
        x1, y1 = float(entity.dxf.start.x), float(entity.dxf.start.y)
        x2, y2 = float(entity.dxf.end.x), float(entity.dxf.end.y)
        if abs(x1 - x2) <= tolerance and abs(y1 - y2) > tolerance:
            rows.append(("x", (x1 + x2) / 2.0, min(y1, y2), max(y1, y2)))
        elif abs(y1 - y2) <= tolerance and abs(x1 - x2) > tolerance:
            rows.append(("y", (y1 + y2) / 2.0, min(x1, x2), max(x1, x2)))
        else:
            rows.append(("angled", x1, y1, x2, y2))
    return tuple(sorted(rows))


def _rows_close(expected, actual, tolerance: float) -> bool:
    if len(expected) != len(actual):
        return False
    for erow, arow in zip(expected, actual):
        if len(erow) != len(arow) or erow[0] != arow[0]:
            return False
        for ev, av in zip(erow[1:], arow[1:]):
            if abs(float(ev) - float(av)) > tolerance:
                return False
    return True


def _expected_cutting_circles(scene):
    return tuple(sorted(
        (
            float(p.center.x),
            float(p.center.y),
            float(p.radius),
        )
        for p in getattr(scene, "primitives", ())
        if isinstance(p, CirclePrimitive)
        and str(getattr(p, "layer", "")).upper() == "CUTTING"
    ))


def _actual_cutting_circles(msp):
    return tuple(sorted(
        (
            float(e.dxf.center.x),
            float(e.dxf.center.y),
            float(e.dxf.radius),
        )
        for e in msp
        if e.dxftype() == "CIRCLE" and str(e.dxf.layer).upper() == "CUTTING"
    ))


def _circle_rows_close(expected, actual, tolerance: float) -> bool:
    if len(expected) != len(actual):
        return False
    return all(
        abs(ex - ax) <= tolerance
        and abs(ey - ay) <= tolerance
        and abs(er - ar) <= tolerance
        for (ex, ey, er), (ax, ay, ar) in zip(expected, actual)
    )


def _same_line_geometry(a, b, tolerance: float) -> bool:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    direct = (
        abs(ax1 - bx1) <= tolerance and abs(ay1 - by1) <= tolerance
        and abs(ax2 - bx2) <= tolerance and abs(ay2 - by2) <= tolerance
    )
    reverse = (
        abs(ax1 - bx2) <= tolerance and abs(ay1 - by2) <= tolerance
        and abs(ax2 - bx1) <= tolerance and abs(ay2 - by1) <= tolerance
    )
    return direct or reverse


def _find_layer_mismatches(scene, msp, tolerance: float):
    issues = []
    actual_lines = []
    actual_circles = []
    for entity in msp:
        layer = str(entity.dxf.layer).upper()
        if entity.dxftype() == "LINE":
            actual_lines.append((
                layer,
                (
                    float(entity.dxf.start.x), float(entity.dxf.start.y),
                    float(entity.dxf.end.x), float(entity.dxf.end.y),
                ),
            ))
        elif entity.dxftype() == "CIRCLE":
            actual_circles.append((
                layer,
                (
                    float(entity.dxf.center.x), float(entity.dxf.center.y),
                    float(entity.dxf.radius),
                ),
            ))

    for primitive in getattr(scene, "primitives", ()):
        expected_layer = str(getattr(primitive, "layer", "")).upper()
        if isinstance(primitive, LinePrimitive):
            geom = (
                float(primitive.p1.x), float(primitive.p1.y),
                float(primitive.p2.x), float(primitive.p2.y),
            )
            same = [
                layer for layer, actual in actual_lines
                if _same_line_geometry(geom, actual, tolerance)
            ]
            if same and expected_layer not in same:
                issues.append(DxfAcceptanceIssue(
                    "LAYER_MISMATCH",
                    f"line expected on {expected_layer} was saved on {sorted(set(same))}",
                    expected_layer,
                    tuple(sorted(set(same))),
                ))
        elif isinstance(primitive, CirclePrimitive):
            geom = (
                float(primitive.center.x), float(primitive.center.y), float(primitive.radius)
            )
            same = [
                layer for layer, actual in actual_circles
                if all(abs(a - b) <= tolerance for a, b in zip(geom, actual))
            ]
            if same and expected_layer not in same:
                issues.append(DxfAcceptanceIssue(
                    "LAYER_MISMATCH",
                    f"circle expected on {expected_layer} was saved on {sorted(set(same))}",
                    expected_layer,
                    tuple(sorted(set(same))),
                ))
    return tuple(issues)


def verify_saved_part_render_data_dxf(
    render_data,
    output_path,
    *,
    coordinate_tolerance: float = 1e-6,
    area_tolerance: float = 1e-6,
) -> DxfAcceptanceResult:
    """Reopen one saved DXF and compare it with canonical PartRenderData."""
    path = Path(output_path)
    issues: list[DxfAcceptanceIssue] = []
    if not path.is_file():
        return DxfAcceptanceResult(
            False,
            (DxfAcceptanceIssue("MISSING_FILE", f"DXF does not exist: {path}"),),
        )

    try:
        doc = ezdxf.readfile(path)
    except Exception as exc:
        return DxfAcceptanceResult(
            False,
            (DxfAcceptanceIssue("SERIALIZATION_ERROR", f"DXF reopen failed: {exc}"),),
        )
    msp = doc.modelspace()

    issues.extend(_find_layer_mismatches(
        render_data.scene, msp, float(coordinate_tolerance)
    ))

    expected_counts = _scene_counts(render_data.scene)
    actual_counts = _dxf_counts(msp)
    if expected_counts != actual_counts:
        issues.append(DxfAcceptanceIssue(
            "ENTITY_COUNT_MISMATCH",
            "saved DXF entity type/layer counts differ from canonical scene",
            dict(expected_counts),
            dict(actual_counts),
        ))

    try:
        actual_material = _actual_material(msp, float(coordinate_tolerance))
        expected_material = render_data.material
        diff_area = float(expected_material.symmetric_difference(actual_material).area)
        if diff_area > float(area_tolerance):
            issues.append(DxfAcceptanceIssue(
                "CUTTING_MISMATCH",
                f"CUTTING symmetric difference area {diff_area:.9g} exceeds {area_tolerance}",
                tuple(map(float, expected_material.bounds)),
                tuple(map(float, actual_material.bounds)),
            ))
    except Exception as exc:
        issues.append(DxfAcceptanceIssue(
            "UNCLOSED_CONTOUR",
            f"cannot reconstruct saved CUTTING material: {exc}",
        ))

    expected_bends = _expected_bends(render_data)
    actual_bends = _actual_bends(msp, float(coordinate_tolerance))
    if not _rows_close(expected_bends, actual_bends, float(coordinate_tolerance)):
        issues.append(DxfAcceptanceIssue(
            "BEND_MISMATCH",
            "saved BEND guides differ from canonical fold guides",
            expected_bends,
            actual_bends,
        ))

    expected_circles = _expected_cutting_circles(render_data.scene)
    actual_circles = _actual_cutting_circles(msp)
    if not _circle_rows_close(expected_circles, actual_circles, float(coordinate_tolerance)):
        issues.append(DxfAcceptanceIssue(
            "HOLE_MISMATCH",
            "saved CUTTING circles differ from canonical hole circles",
            expected_circles,
            actual_circles,
        ))

    return DxfAcceptanceResult(ok=not issues, issues=tuple(issues))
