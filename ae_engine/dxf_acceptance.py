# -*- coding: utf-8 -*-
"""Independent acceptance of already-saved manufacturing DXF files.

This module is deliberately downstream of serialization.  It reopens the
actual DXF bytes with ezdxf and reconstructs what was written; it never calls
AE's scene serializer to derive the actual side of the comparison.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import hypot, isfinite
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
        if kind is None:
            # Foreign DXF primitives (ARC, SPLINE, INSERT, ...) are never
            # authorized by canonical DrawingScene. Count them explicitly
            # so the existing entity-count gate fails closed.
            kind = f"UNSUPPORTED:{entity.dxftype()}"
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


def _first_nonplanar_cutting_entity(msp):
    """Return the first supported CUTTING primitive outside the canonical XY frame."""
    for entity in msp:
        if str(entity.dxf.layer).upper() != "CUTTING":
            continue
        kind = entity.dxftype()
        if kind == "LINE":
            # DXF LINE stores endpoints directly in WCS, not OCS.
            if entity.dxf.start.z != 0.0 or entity.dxf.end.z != 0.0:
                return kind
        elif kind in {"LWPOLYLINE", "CIRCLE"}:
            z = (entity.dxf.elevation if kind == "LWPOLYLINE"
                 else entity.dxf.center.z)
            if z != 0.0 or tuple(entity.dxf.extrusion) != (0.0, 0.0, 1.0):
                return kind
    return None


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


def _one_to_one_tolerance_match(expected, actual, compatible) -> bool:
    """Require a COMPLETE unique matching, not greedy first-fit pairing.

    Sorted near-coincident BEND stations or CUTTING holes can overlap inside
    one coordinate tolerance. A first-fit choice may steal another row's only
    legal partner and falsely report a manufacturing DXF mismatch.
    """
    if len(expected) != len(actual):
        return False
    # Common case: canonical DXF sorting already aligns every entity.
    # Keep that original linear-time path; build the matching graph only
    # when near-equal numeric ordering has changed across serialization.
    if all(compatible(row, found) for row, found in zip(expected, actual)):
        return True
    edges = [
        tuple(index for index, found in enumerate(actual) if compatible(row, found))
        for row in expected
    ]
    if any(not options for options in edges):
        return False
    assigned = {}

    def augment(root):
        # Iterative augmenting path: a densely perforated DXF can need over
        # 1000 chained reassignments, exceeding Python's recursion limit.
        # The stack remembers the parent column used to reach each row.
        visited = set()
        stack = [(root, iter(edges[root]), None)]
        while stack:
            row, options, _incoming = stack[-1]
            col = next(options, None)
            if col is None:
                stack.pop()
                continue
            if col in visited:
                continue
            visited.add(col)
            displaced = assigned.get(col)
            if displaced is None:
                assigned[col] = row
                for depth in range(len(stack) - 1, 0, -1):
                    parent_row = stack[depth - 1][0]
                    parent_col = stack[depth][2]
                    assigned[parent_col] = parent_row
                return True
            stack.append((displaced, iter(edges[displaced]), col))
        return False

    # Preserve strict COMPLETE one-to-one matching; no tolerance widening
    # and no greedy acceptance of duplicated/missing manufactured holes.
    return all(
        augment(index)
        for index in sorted(range(len(edges)), key=lambda i: len(edges[i]))
    )


def _valid_nonnegative_tolerance(value) -> bool:
    # Acceptance tolerances are physically meaningful numeric limits, not
    # strings, bools or NaN/Inf capable of bypassing CUTTING comparison.
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return isfinite(value) and value >= 0.
    except OverflowError:
        # math.isfinite converts huge Python ints to float before checking.
        # A malformed tolerance must not escape the DXF fail-closed receipt.
        return False


def _rows_close(expected, actual, tolerance: float) -> bool:
    if not _valid_nonnegative_tolerance(tolerance):
        return False

    def same(erow, arow):
        if len(erow) != len(arow) or erow[0] != arow[0]:
            return False
        if any(isinstance(v, bool) for v in (*erow[1:], *arow[1:])):
            return False
        try:
            pairs = tuple((float(ev), float(av)) for ev, av in zip(erow[1:], arow[1:]))
        except (TypeError, ValueError, OverflowError):
            return False
        return all(isfinite(ev) and isfinite(av) and abs(ev - av) <= tolerance
                   for ev, av in pairs)

    return _one_to_one_tolerance_match(expected, actual, same)


def _expected_cutting_circles(scene):
    circles = []
    for p in getattr(scene, "primitives", ()):
        if not isinstance(p, CirclePrimitive) or str(getattr(p, "layer", "")).upper() != "CUTTING":
            continue
        raw = (p.center.x, p.center.y, p.radius)
        if any(isinstance(value, bool) for value in raw):
            raise ValueError("canonical CUTTING circle must have real physical coordinates")
        try:
            cx, cy, radius = (float(value) for value in raw)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("canonical CUTTING circle must have real physical coordinates") from exc
        if not all(isfinite(v) for v in (cx, cy, radius)) or radius <= 0:
            raise ValueError("canonical CUTTING circle must have finite positive radius")
        circles.append((cx, cy, radius))
    return tuple(sorted(circles))


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
    if not _valid_nonnegative_tolerance(tolerance):
        return False

    def same(erow, arow):
        if len(erow) != len(arow) or any(
            isinstance(v, bool) for v in (*erow, *arow)
        ):
            return False
        try:
            values = tuple((float(ev), float(av)) for ev, av in zip(erow, arow))
        except (TypeError, ValueError, OverflowError):
            return False
        return (len(erow) == len(arow) == 3
                and all(isfinite(ev) and isfinite(av) and abs(ev - av) <= tolerance
                        for ev, av in values))

    return _one_to_one_tolerance_match(expected, actual, same)


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


def _expected_marking_polylines(scene):
    """Canonical MARKING strokes, including every vertex and open/closed intent."""
    rows = []
    for primitive in getattr(scene, "primitives", ()):
        if (not isinstance(primitive, PolylinePrimitive)
                or str(primitive.layer).upper() != "MARKING"):
            continue
        vertices = []
        for point in primitive.points:
            raw = (point.x, point.y)
            if any(isinstance(value, bool) for value in raw):
                raise ValueError("canonical MARKING vertex must have real coordinates")
            try:
                x, y = (float(value) for value in raw)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("canonical MARKING vertex must have real coordinates") from exc
            if not all(isfinite(value) for value in (x, y)):
                raise ValueError("canonical MARKING vertex must have finite coordinates")
            vertices.append((x, y))
        color = primitive.color if primitive.color is not None else 211
        rows.append(("MARKING", bool(primitive.closed), color, tuple(vertices)))
    return tuple(rows)


def _actual_marking_polylines(msp):
    """Read saved MARKING vertices AND machining attributes; no serializer callback."""
    return tuple(
        (
            str(entity.dxf.layer).upper(),
            bool(entity.closed),
            entity.dxf.get("color", 256),
            str(entity.dxf.get("linetype", "BYLAYER")).upper(),
            float(entity.dxf.get("const_width", 0)),
            float(entity.dxf.get("elevation", 0)),
            tuple(map(float, entity.dxf.get("extrusion", (0, 0, 1)))),
            tuple(tuple(map(float, point)) for point in entity.get_points("xyseb")),
        )
        for entity in msp
        if entity.dxftype() == "LWPOLYLINE"
        and str(entity.dxf.layer).upper() == "MARKING"
    )


def _marking_rows_close(expected, actual, tolerance: float) -> bool:
    """One-to-one ink matching; never silently accept bulge or variable width."""
    def same(source, saved):
        layer, closed, color, points = source
        actual_layer, actual_closed, actual_color, linetype, width, elevation, extrusion, vertices = saved
        if (layer != actual_layer or closed != actual_closed
                or color != actual_color
                or linetype not in {"BYLAYER", "CONTINUOUS"}
                or width != 0.0 or elevation != 0.0
                or extrusion != (0.0, 0.0, 1.0)
                or len(points) != len(vertices)):
            return False
        return all(
            len(v) == 5
            and all(isfinite(n) for n in v)
            and abs(x - v[0]) <= tolerance
            and abs(y - v[1]) <= tolerance
            and v[2] == 0.0 and v[3] == 0.0 and v[4] == 0.0
            for (x, y), v in zip(points, vertices)
        )

    return _one_to_one_tolerance_match(expected, actual, same)


def _expected_marking_circles(scene):
    """Check circle ink only for the newly authorized manual-round source."""
    from .operator_manual_marking import is_manual_round_mark

    circles = tuple(
        row for row in scene.primitives
        if isinstance(row, CirclePrimitive) and str(row.layer).upper() == "MARKING"
    )
    if not any(is_manual_round_mark(row) for row in circles):
        return ()
    expected = tuple(
        (float(row.center.x), float(row.center.y), float(row.radius),
         row.color if row.color is not None else 211)
        for row in circles
    )
    if any(not all(isfinite(v) for v in row[:3]) or row[2] <= 0 for row in expected):
        raise ValueError("canonical MARKING circle must have finite centre and positive radius")
    return expected


def _actual_marking_circles(msp):
    return tuple(
        (tuple(map(float, row.dxf.center)), float(row.dxf.radius),
         row.dxf.get("color", 256), str(row.dxf.get("linetype", "BYLAYER")).upper(),
         float(row.dxf.get("thickness", 0)),
         tuple(map(float, row.dxf.get("extrusion", (0, 0, 1)))))
        for row in msp
        if row.dxftype() == "CIRCLE" and str(row.dxf.layer).upper() == "MARKING"
    )


def _marking_circles_close(expected, actual, tolerance):
    def same(source, saved):
        x, y, radius, color = source
        (u, v, z), r, ink_color, linetype, thickness, extrusion = saved
        return (
            all(isfinite(n) for n in (u, v, z, r)) and r > 0
            and color == ink_color and linetype in {"BYLAYER", "CONTINUOUS"}
            and z == 0 and thickness == 0 and extrusion == (0, 0, 1)
            and abs(u-x) <= tolerance and abs(v-y) <= tolerance
            and abs(r-radius) <= tolerance
        )

    return _one_to_one_tolerance_match(expected, actual, same)


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
    for name, tolerance in (
        ("coordinate_tolerance", coordinate_tolerance),
        ("area_tolerance", area_tolerance),
    ):
        if not _valid_nonnegative_tolerance(tolerance):
            return DxfAcceptanceResult(False, (
                DxfAcceptanceIssue(
                    "INVALID_TOLERANCE",
                    f"{name} must be a finite, nonnegative real measurement",
                ),
            ))
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
    # A geometrically identical sheet in meters is unsafe for millimeter CAM.
    # Inspect the independently reopened bytes, never the serializer intent.
    declared_units = doc.header.get("$INSUNITS", 0)
    if declared_units != ezdxf.units.MM:
        issues.append(DxfAcceptanceIssue(
            "UNIT_MISMATCH",
            "saved manufacturing DXF $INSUNITS must declare millimeters (4)",
            ezdxf.units.MM,
            declared_units,
        ))
    msp = doc.modelspace()

    # Fail closed BEFORE layer matching float-coerces a malformed source hole.
    # The reopened DXF must never certify a boolean/NaN physical CUTTING circle.
    try:
        expected_circles = _expected_cutting_circles(render_data.scene)
    except ValueError as exc:
        return DxfAcceptanceResult(False, (
            DxfAcceptanceIssue("INVALID_SOURCE", str(exc)),
        ))

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

    # The raw XY material reconstruction below assumes canonical WCS XY.
    # Do not pass matching object-space points as proof of flat world geometry.
    nonplanar_cutting = _first_nonplanar_cutting_entity(msp)
    if nonplanar_cutting is not None:
        issues.append(DxfAcceptanceIssue(
            "CUTTING_PLANE_MISMATCH",
            "saved CUTTING geometry must use the canonical XY plane",
            "Z=0; +Z normal for object-space geometry",
            nonplanar_cutting,
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

    actual_circles = _actual_cutting_circles(msp)
    if not _circle_rows_close(expected_circles, actual_circles, float(coordinate_tolerance)):
        issues.append(DxfAcceptanceIssue(
            "HOLE_MISMATCH",
            "saved CUTTING circles differ from canonical hole circles",
            expected_circles,
            actual_circles,
        ))

    # Neither entity counts nor CUTTING area detects an unchanged number
    # of MARKING strokes whose positions, widths or curve bulges were altered.
    # Read back each physical LWPOLYLINE from the staged DXF independently.
    try:
        expected_marks = _expected_marking_polylines(render_data.scene)
        expected_rings = _expected_marking_circles(render_data.scene)
        if expected_marks or expected_rings:
            try:
                marking_layer = doc.layers.get("MARKING")
                layer_ok = (
                    str(marking_layer.dxf.linetype).upper() == "CONTINUOUS"
                    and marking_layer.dxf.color == 211
                )
            except Exception:
                layer_ok = False
        if expected_marks:
            actual_marks = _actual_marking_polylines(msp)
            if (not layer_ok or not _marking_rows_close(
                    expected_marks, actual_marks, float(coordinate_tolerance))):
                issues.append(DxfAcceptanceIssue(
                    "MARKING_MISMATCH",
                    "saved MARKING LWPOLYLINE differs from canonical points/style",
                    expected_marks,
                    actual_marks,
                ))
        if expected_rings:
            actual_rings = _actual_marking_circles(msp)
            if (not layer_ok or not _marking_circles_close(
                    expected_rings, actual_rings, float(coordinate_tolerance))):
                issues.append(DxfAcceptanceIssue(
                    "MARKING_MISMATCH",
                    "saved MARKING CIRCLE differs from canonical centre/radius/plane/style",
                    expected_rings,
                    actual_rings,
                ))
    except ValueError as exc:
        issues.append(DxfAcceptanceIssue("INVALID_SOURCE", str(exc)))

    return DxfAcceptanceResult(ok=not issues, issues=tuple(issues))
