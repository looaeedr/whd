# -*- coding: utf-8 -*-
"""Pure engineering-annotation planning from canonical manufacturing data.

This module is downstream of PartRenderData.  It measures already-resolved
material/features and creates annotation-only primitives; it never owns or
rebuilds CUTTING/BEND/manufacturing geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import atan2, hypot, pi

from .sheetmetal_drawing import CirclePrimitive, LinePrimitive, TextPrimitive
from .sheetmetal_geometry import Vec2


def _fmt(value: float) -> str:
    value = round(float(value), 6)
    if abs(value - round(value)) <= 1e-9:
        return str(int(round(value)))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def _fmt_radius(value: float) -> str:
    """Format a measured radius without exposing sub-micron fit noise."""
    raw = float(value)
    nearest = round(raw)
    if abs(raw - nearest) <= max(1e-4, abs(raw) * 1e-6):
        return str(int(nearest))
    return _fmt(raw)


def _semantic_number(value: float) -> str:
    return _fmt(float(value))


def _semantic_point(point: Vec2) -> str:
    return f"{_semantic_number(point.x)},{_semantic_number(point.y)}"


@dataclass(frozen=True)
class LinearDimensionAnnotation:
    axis: str
    value: float
    start: Vec2
    end: Vec2
    label: str

    @property
    def semantic_id(self) -> str:
        axis = str(self.axis).strip().lower()
        return (
            f"DIMENSION:{axis}:"
            f"{_semantic_point(self.start)}:{_semantic_point(self.end)}:"
            f"{_semantic_number(self.value)}"
        )


@dataclass(frozen=True)
class FeatureCallout:
    source_id: str
    source_type: str
    anchor: Vec2
    label: str

    @property
    def semantic_id(self) -> str:
        return (
            f"FEATURE:{self.source_type}:{self.source_id}:"
            f"{_semantic_point(self.anchor)}"
        )


@dataclass(frozen=True)
class CornerCallout:
    corner: str
    width: float
    height: float
    anchor: Vec2
    label: str

    @property
    def semantic_id(self) -> str:
        return (
            f"CORNER:{self.corner}:"
            f"{_semantic_number(self.width)}x{_semantic_number(self.height)}:"
            f"{_semantic_point(self.anchor)}"
        )


@dataclass(frozen=True)
class RadiusCallout:
    radius: float
    center: Vec2
    anchor: Vec2
    label: str

    @property
    def semantic_id(self) -> str:
        return (
            f"RADIUS:{_semantic_number(self.radius)}:"
            f"{_semantic_point(self.center)}:{_semantic_point(self.anchor)}"
        )


@dataclass(frozen=True)
class AnnotationPlan:
    overall_dimensions: tuple[LinearDimensionAnnotation, ...]
    feature_callouts: tuple[FeatureCallout, ...]
    corner_callouts: tuple[CornerCallout, ...]
    radius_callouts: tuple[RadiusCallout, ...]
    primitives: tuple[LinePrimitive | TextPrimitive, ...]
    diagnostics: tuple[str, ...] = ()


def _overall_dimensions(material) -> tuple[LinearDimensionAnnotation, ...]:
    minx, miny, maxx, maxy = map(float, material.bounds)
    return (
        LinearDimensionAnnotation(
            axis="x",
            value=maxx - minx,
            start=Vec2(minx, miny),
            end=Vec2(maxx, miny),
            label=_fmt(maxx - minx),
        ),
        LinearDimensionAnnotation(
            axis="y",
            value=maxy - miny,
            start=Vec2(minx, miny),
            end=Vec2(minx, maxy),
            label=_fmt(maxy - miny),
        ),
    )


def _feature_callouts(scene) -> tuple[FeatureCallout, ...]:
    rows = []
    for primitive in getattr(scene, "primitives", ()):
        if not isinstance(primitive, CirclePrimitive):
            continue
        if str(getattr(primitive, "layer", "")).upper() != "CUTTING":
            continue
        source_id = str(getattr(primitive, "source_id", "") or "")
        source_type = str(getattr(primitive, "source_type", "") or "")
        # Engineering callouts should be traceable to the authoritative feature.
        # Legacy anonymous circles remain drawable but are not silently assigned
        # a made-up manufacturing identity here.
        if not source_id and not source_type:
            continue
        rows.append(FeatureCallout(
            source_id=source_id,
            source_type=source_type,
            anchor=Vec2(float(primitive.center.x), float(primitive.center.y)),
            label=f"⌀{_fmt(float(primitive.radius) * 2.0)}",
        ))
    return tuple(sorted(
        rows,
        key=lambda item: (
            item.source_id,
            item.source_type,
            float(item.anchor.x),
            float(item.anchor.y),
            item.label,
        ),
    ))


def _boundary_extrema(material, tolerance: float):
    minx, miny, maxx, maxy = map(float, material.bounds)
    exterior = getattr(material, "exterior", None)
    if exterior is None:
        return None
    coords = [(float(x), float(y)) for x, y, *_ in exterior.coords]
    left = [p for p in coords if abs(p[0] - minx) <= tolerance]
    right = [p for p in coords if abs(p[0] - maxx) <= tolerance]
    bottom = [p for p in coords if abs(p[1] - miny) <= tolerance]
    top = [p for p in coords if abs(p[1] - maxy) <= tolerance]
    if not (left and right and bottom and top):
        return None
    return {
        "bounds": (minx, miny, maxx, maxy),
        "left_min_y": min(p[1] for p in left),
        "left_max_y": max(p[1] for p in left),
        "right_min_y": min(p[1] for p in right),
        "right_max_y": max(p[1] for p in right),
        "bottom_min_x": min(p[0] for p in bottom),
        "bottom_max_x": max(p[0] for p in bottom),
        "top_min_x": min(p[0] for p in top),
        "top_max_x": max(p[0] for p in top),
    }


def _corner_callouts(material) -> tuple[CornerCallout, ...]:
    minx, miny, maxx, maxy = map(float, material.bounds)
    span = max(maxx - minx, maxy - miny, 1.0)
    tol = max(1e-7, span * 1e-9)
    ex = _boundary_extrema(material, tol)
    if ex is None:
        return ()

    rows = []
    candidates = (
        (
            "BOTTOM_LEFT",
            float(ex["bottom_min_x"]) - minx,
            float(ex["left_min_y"]) - miny,
            Vec2(
                (float(ex["bottom_min_x"]) + minx) / 2.0,
                (float(ex["left_min_y"]) + miny) / 2.0,
            ),
        ),
        (
            "BOTTOM_RIGHT",
            maxx - float(ex["bottom_max_x"]),
            float(ex["right_min_y"]) - miny,
            Vec2(
                (float(ex["bottom_max_x"]) + maxx) / 2.0,
                (float(ex["right_min_y"]) + miny) / 2.0,
            ),
        ),
        (
            "TOP_LEFT",
            float(ex["top_min_x"]) - minx,
            maxy - float(ex["left_max_y"]),
            Vec2(
                (float(ex["top_min_x"]) + minx) / 2.0,
                (float(ex["left_max_y"]) + maxy) / 2.0,
            ),
        ),
        (
            "TOP_RIGHT",
            maxx - float(ex["top_max_x"]),
            maxy - float(ex["right_max_y"]),
            Vec2(
                (float(ex["top_max_x"]) + maxx) / 2.0,
                (float(ex["right_max_y"]) + maxy) / 2.0,
            ),
        ),
    )
    for corner, width, height, anchor in candidates:
        if width <= tol or height <= tol:
            continue
        rows.append(CornerCallout(
            corner=corner,
            width=float(width),
            height=float(height),
            anchor=anchor,
            label=f"{_fmt(width)}×{_fmt(height)}",
        ))
    return tuple(rows)


def _circumcircle(a, b, c):
    ax, ay = map(float, a)
    bx, by = map(float, b)
    cx, cy = map(float, c)
    denominator = 2.0 * (
        ax * (by - cy)
        + bx * (cy - ay)
        + cx * (ay - by)
    )
    scale = max(
        hypot(bx - ax, by - ay),
        hypot(cx - bx, cy - by),
        hypot(ax - cx, ay - cy),
        1.0,
    )
    if abs(denominator) <= 1e-12 * scale * scale:
        return None

    a2 = ax * ax + ay * ay
    b2 = bx * bx + by * by
    c2 = cx * cx + cy * cy
    ux = (
        a2 * (by - cy)
        + b2 * (cy - ay)
        + c2 * (ay - by)
    ) / denominator
    uy = (
        a2 * (cx - bx)
        + b2 * (ax - cx)
        + c2 * (bx - ax)
    ) / denominator
    radius = hypot(ax - ux, ay - uy)
    if radius <= 1e-9:
        return None
    return Vec2(float(ux), float(uy)), float(radius)


def _circle_fit_close(left, right, *, span: float) -> bool:
    if left is None or right is None:
        return False
    lc, lr = left
    rc, rr = right
    center_tol = max(1e-5, float(span) * 1e-5, max(lr, rr) * 2e-5)
    radius_tol = max(1e-5, float(span) * 1e-5, max(lr, rr) * 2e-5)
    return (
        hypot(float(lc.x) - float(rc.x), float(lc.y) - float(rc.y)) <= center_tol
        and abs(float(lr) - float(rr)) <= radius_tol
    )


def _arc_turn_angle(center: Vec2, points) -> float:
    total = 0.0
    for a, b in zip(points, points[1:]):
        av = (float(a[0]) - center.x, float(a[1]) - center.y)
        bv = (float(b[0]) - center.x, float(b[1]) - center.y)
        cross = av[0] * bv[1] - av[1] * bv[0]
        dot = av[0] * bv[0] + av[1] * bv[1]
        total += abs(atan2(cross, dot))
    return float(total)


def _radius_callouts(material) -> tuple[RadiusCallout, ...]:
    """Measure stable sampled circular runs from the final material exterior.

    Three points alone always define a circle, so a single triple is never
    enough evidence.  A callout requires at least two consecutive compatible
    circumcircle fits (four boundary points) plus a non-trivial swept angle.
    """
    exterior = getattr(material, "exterior", None)
    if exterior is None:
        return ()
    coords = [(float(x), float(y)) for x, y, *_ in exterior.coords]
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    n = len(coords)
    if n < 4:
        return ()

    minx, miny, maxx, maxy = map(float, material.bounds)
    span = max(maxx - minx, maxy - miny, 1.0)
    fits = [
        _circumcircle(
            coords[i],
            coords[(i + 1) % n],
            coords[(i + 2) % n],
        )
        for i in range(n)
    ]

    rows = []
    seen = set()
    for start in range(n):
        fit = fits[start]
        if fit is None:
            continue
        previous = fits[(start - 1) % n]
        if _circle_fit_close(previous, fit, span=span):
            continue

        run = [start]
        cursor = (start + 1) % n
        while cursor != start and len(run) < n:
            next_fit = fits[cursor]
            if not _circle_fit_close(fits[run[-1]], next_fit, span=span):
                break
            run.append(cursor)
            cursor = (cursor + 1) % n

        if len(run) < 2:
            continue

        centers = [fits[i][0] for i in run if fits[i] is not None]
        radii = [float(fits[i][1]) for i in run if fits[i] is not None]
        center = Vec2(
            sum(float(item.x) for item in centers) / len(centers),
            sum(float(item.y) for item in centers) / len(centers),
        )
        radius = sum(radii) / len(radii)

        point_count = len(run) + 2
        points = [coords[(start + i) % n] for i in range(point_count)]
        residual = max(
            abs(hypot(p[0] - center.x, p[1] - center.y) - radius)
            for p in points
        )
        residual_tol = max(1e-4, span * 2e-5, radius * 5e-5)
        if residual > residual_tol:
            continue

        swept = _arc_turn_angle(center, points)
        if swept < (10.0 * pi / 180.0):
            continue

        key = (
            round(float(center.x), 5),
            round(float(center.y), 5),
            round(float(radius), 5),
        )
        if key in seen:
            continue
        seen.add(key)
        mid = points[len(points) // 2]
        rows.append(RadiusCallout(
            radius=float(radius),
            center=center,
            anchor=Vec2(float(mid[0]), float(mid[1])),
            label=f"R{_fmt_radius(radius)}",
        ))

    return tuple(sorted(
        rows,
        key=lambda item: (
            float(item.center.x),
            float(item.center.y),
            float(item.radius),
        ),
    ))


def _annotation_primitives(
    material,
    dimensions: tuple[LinearDimensionAnnotation, ...],
    features: tuple[FeatureCallout, ...],
    corners: tuple[CornerCallout, ...],
    radii: tuple[RadiusCallout, ...],
    *,
    char_height: float,
    dimension_offset: float,
) -> tuple[LinePrimitive | TextPrimitive, ...]:
    minx, miny, maxx, maxy = map(float, material.bounds)
    primitives: list[LinePrimitive | TextPrimitive] = []

    xdim = next(item for item in dimensions if item.axis == "x")
    ydim = next(item for item in dimensions if item.axis == "y")
    x_y = miny - float(dimension_offset)
    y_x = minx - float(dimension_offset)

    primitives.extend((
        LinePrimitive(Vec2(minx, x_y), Vec2(maxx, x_y), "DIMENSION"),
        TextPrimitive(
            xdim.label,
            Vec2((minx + maxx) / 2.0, x_y),
            "DIMENSION",
            float(char_height),
            5,
            semantic_id=xdim.semantic_id,
        ),
        LinePrimitive(Vec2(y_x, miny), Vec2(y_x, maxy), "DIMENSION"),
        TextPrimitive(
            ydim.label,
            Vec2(y_x, (miny + maxy) / 2.0),
            "DIMENSION",
            float(char_height),
            5,
            semantic_id=ydim.semantic_id,
        ),
    ))

    callout_shift = max(float(char_height) * 2.0, 4.0)
    for item in features:
        primitives.append(TextPrimitive(
            item.label,
            Vec2(item.anchor.x + callout_shift, item.anchor.y + callout_shift),
            "TEXT",
            float(char_height),
            1,
            semantic_id=item.semantic_id,
        ))
    for item in corners:
        primitives.append(TextPrimitive(
            item.label,
            Vec2(item.anchor.x + callout_shift, item.anchor.y + callout_shift),
            "TEXT",
            float(char_height),
            1,
            semantic_id=item.semantic_id,
        ))
    for item in radii:
        primitives.append(TextPrimitive(
            item.label,
            Vec2(item.anchor.x + callout_shift, item.anchor.y + callout_shift),
            "TEXT",
            float(char_height),
            1,
            semantic_id=item.semantic_id,
        ))
    return tuple(primitives)


def plan_part_annotations(
    render_data,
    *,
    char_height: float = 5.0,
    dimension_offset: float = 15.0,
) -> AnnotationPlan:
    """Measure canonical PartRenderData and return an annotation-only plan."""
    material = getattr(render_data, "material", None)
    scene = getattr(render_data, "scene", None)
    if material is None or bool(getattr(material, "is_empty", True)):
        raise ValueError("canonical final material is required for annotations")
    if scene is None:
        raise ValueError("canonical DrawingScene is required for feature annotations")

    dimensions = _overall_dimensions(material)
    features = _feature_callouts(scene)
    corners = _corner_callouts(material)
    radii = _radius_callouts(material)
    primitives = _annotation_primitives(
        material,
        dimensions,
        features,
        corners,
        radii,
        char_height=float(char_height),
        dimension_offset=float(dimension_offset),
    )
    return AnnotationPlan(
        overall_dimensions=dimensions,
        feature_callouts=features,
        corner_callouts=corners,
        radius_callouts=radii,
        primitives=primitives,
        diagnostics=(),
    )
