# -*- coding: utf-8 -*-
"""Pure engineering-annotation planning from canonical manufacturing data.

This module is downstream of PartRenderData.  It measures already-resolved
material/features and creates annotation-only primitives; it never owns or
rebuilds CUTTING/BEND/manufacturing geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .sheetmetal_drawing import CirclePrimitive, LinePrimitive, TextPrimitive
from .sheetmetal_geometry import Vec2


def _fmt(value: float) -> str:
    value = round(float(value), 6)
    if abs(value - round(value)) <= 1e-9:
        return str(int(round(value)))
    return f"{value:.6f}".rstrip("0").rstrip(".")


@dataclass(frozen=True)
class LinearDimensionAnnotation:
    axis: str
    value: float
    start: Vec2
    end: Vec2
    label: str


@dataclass(frozen=True)
class FeatureCallout:
    source_id: str
    source_type: str
    anchor: Vec2
    label: str


@dataclass(frozen=True)
class CornerCallout:
    corner: str
    width: float
    height: float
    anchor: Vec2
    label: str


@dataclass(frozen=True)
class AnnotationPlan:
    overall_dimensions: tuple[LinearDimensionAnnotation, ...]
    feature_callouts: tuple[FeatureCallout, ...]
    corner_callouts: tuple[CornerCallout, ...]
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


def _annotation_primitives(
    material,
    dimensions: tuple[LinearDimensionAnnotation, ...],
    features: tuple[FeatureCallout, ...],
    corners: tuple[CornerCallout, ...],
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
        ),
        LinePrimitive(Vec2(y_x, miny), Vec2(y_x, maxy), "DIMENSION"),
        TextPrimitive(
            ydim.label,
            Vec2(y_x, (miny + maxy) / 2.0),
            "DIMENSION",
            float(char_height),
            5,
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
        ))
    for item in corners:
        primitives.append(TextPrimitive(
            item.label,
            Vec2(item.anchor.x + callout_shift, item.anchor.y + callout_shift),
            "TEXT",
            float(char_height),
            1,
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
    primitives = _annotation_primitives(
        material,
        dimensions,
        features,
        corners,
        char_height=float(char_height),
        dimension_offset=float(dimension_offset),
    )
    return AnnotationPlan(
        overall_dimensions=dimensions,
        feature_callouts=features,
        corner_callouts=corners,
        primitives=primitives,
        diagnostics=(),
    )
