# -*- coding: utf-8 -*-
"""Deterministic annotation-only layout/collision resolution.

This module is downstream of AnnotationPlan.  It may move annotation
primitives, but it never owns or mutates manufacturing CUTTING/BEND/material.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from .sheetmetal_drawing import CirclePrimitive, LinePrimitive, PolylinePrimitive, TextPrimitive
from .sheetmetal_geometry import Vec2


@dataclass(frozen=True)
class AnnotationRegion:
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    kind: str = "RESERVED"

    def __post_init__(self):
        if float(self.max_x) < float(self.min_x) or float(self.max_y) < float(self.min_y):
            raise ValueError("invalid annotation region bounds")

    def contains_point(self, point: Vec2) -> bool:
        return (
            float(self.min_x) <= float(point.x) <= float(self.max_x)
            and float(self.min_y) <= float(point.y) <= float(self.max_y)
        )

    def intersects(self, other: "AnnotationRegion") -> bool:
        return not (
            float(self.max_x) < float(other.min_x)
            or float(other.max_x) < float(self.min_x)
            or float(self.max_y) < float(other.min_y)
            or float(other.max_y) < float(self.min_y)
        )


@dataclass(frozen=True)
class AnnotationCollision:
    primitive_index: int
    category: str
    detail: str


@dataclass(frozen=True)
class AnnotationLayoutResult:
    primitives: tuple[object, ...]
    diagnostics: tuple[str, ...] = ()
    unresolved_collisions: tuple[AnnotationCollision, ...] = ()


def _text_region(text: TextPrimitive) -> AnnotationRegion:
    # Deterministic engineering-text approximation.  This is layout geometry,
    # not manufacturing geometry.  Attachment 5 is center/center in current
    # annotation planner; other attachments use insertion as lower-left.
    height = max(float(text.char_height), 1e-9)
    width = max(height * 0.6 * max(len(str(text.text)), 1), height * 0.6)
    x = float(text.insert.x)
    y = float(text.insert.y)
    if int(text.attachment_point) == 5:
        return AnnotationRegion(
            x - width / 2.0,
            y - height / 2.0,
            x + width / 2.0,
            y + height / 2.0,
            "ANNOTATION_TEXT",
        )
    return AnnotationRegion(x, y, x + width, y + height, "ANNOTATION_TEXT")


def _collides(text: TextPrimitive, regions: tuple[AnnotationRegion, ...]) -> bool:
    box = _text_region(text)
    return any(box.intersects(region) for region in regions)


def _line_region(p1: Vec2, p2: Vec2, padding: float, kind: str) -> AnnotationRegion:
    pad = max(float(padding), 0.0)
    return AnnotationRegion(
        min(float(p1.x), float(p2.x)) - pad,
        min(float(p1.y), float(p2.y)) - pad,
        max(float(p1.x), float(p2.x)) + pad,
        max(float(p1.y), float(p2.y)) + pad,
        kind,
    )


def _polyline_regions(primitive: PolylinePrimitive, padding: float):
    points = tuple(primitive.points)
    if len(points) < 2:
        return ()
    pairs = list(zip(points, points[1:]))
    if bool(primitive.closed) and points[-1] != points[0]:
        pairs.append((points[-1], points[0]))
    return tuple(
        _line_region(a, b, padding, str(primitive.layer).upper())
        for a, b in pairs
    )


def _manufacturing_obstacle_regions(scene, *, clearance: float):
    if scene is None:
        return ()
    rows = []
    for primitive in tuple(getattr(scene, "primitives", ()) or ()):
        layer = str(getattr(primitive, "layer", "") or "").upper()
        if isinstance(primitive, LinePrimitive) and layer in {"CUTTING", "BEND"}:
            rows.append(_line_region(
                primitive.p1, primitive.p2, clearance, layer
            ))
        elif isinstance(primitive, PolylinePrimitive) and layer == "CUTTING":
            rows.extend(_polyline_regions(primitive, clearance))
        elif isinstance(primitive, CirclePrimitive) and layer == "CUTTING":
            pad = max(float(clearance), 0.0)
            r = float(primitive.radius) + pad
            rows.append(AnnotationRegion(
                float(primitive.center.x) - r,
                float(primitive.center.y) - r,
                float(primitive.center.x) + r,
                float(primitive.center.y) + r,
                "HOLE",
            ))
    return tuple(rows)


def _dimension_line_orientation(line: LinePrimitive, tolerance: float = 1e-9) -> str | None:
    dx = abs(float(line.p2.x) - float(line.p1.x))
    dy = abs(float(line.p2.y) - float(line.p1.y))
    if dy <= tolerance and dx > tolerance:
        return "x"
    if dx <= tolerance and dy > tolerance:
        return "y"
    return None


def _own_dimension_line_index(primitives, text: TextPrimitive, axis: str) -> int | None:
    candidates = []
    for index, primitive in enumerate(tuple(primitives)):
        if not isinstance(primitive, LinePrimitive):
            continue
        if str(primitive.layer).upper() != "DIMENSION":
            continue
        if _dimension_line_orientation(primitive) != axis:
            continue
        mx = (float(primitive.p1.x) + float(primitive.p2.x)) / 2.0
        my = (float(primitive.p1.y) + float(primitive.p2.y)) / 2.0
        if axis == "x":
            normal = abs(float(text.insert.y) - my)
            along = abs(float(text.insert.x) - mx)
        else:
            normal = abs(float(text.insert.x) - mx)
            along = abs(float(text.insert.y) - my)
        candidates.append((normal, along, index))
    if not candidates:
        return None
    candidates.sort()
    return int(candidates[0][2])


def _annotation_dimension_line_regions(
    primitives,
    *,
    own_line_index: int | None,
    clearance: float,
):
    rows = []
    for index, primitive in enumerate(tuple(primitives)):
        if index == own_line_index:
            continue
        if not isinstance(primitive, LinePrimitive):
            continue
        if str(primitive.layer).upper() != "DIMENSION":
            continue
        rows.append(_line_region(
            primitive.p1,
            primitive.p2,
            max(float(clearance), 0.0),
            "DIMENSION",
        ))
    return tuple(rows)


def _annotation_text_regions(primitives, *, exclude_index: int):
    rows = []
    for index, primitive in enumerate(tuple(primitives)):
        if index == int(exclude_index):
            continue
        if isinstance(primitive, TextPrimitive):
            rows.append(_text_region(primitive))
    return tuple(rows)


def _candidate_offsets(step: float, max_steps: int):
    yield 0.0
    for index in range(1, int(max_steps) + 1):
        amount = float(step) * index
        yield amount
        yield -amount


def _dimension_axis_for_text(plan, primitive: TextPrimitive) -> str | None:
    matches = [
        dim for dim in getattr(plan, "overall_dimensions", ())
        if str(getattr(dim, "label", "")) == str(primitive.text)
    ]
    if len(matches) == 1:
        return str(matches[0].axis).lower()
    if not matches:
        return None

    # Duplicate labels are resolved deterministically by distance to the
    # dimension midpoint in the axis-normal direction.
    scored = []
    for dim in matches:
        mx = (float(dim.start.x) + float(dim.end.x)) / 2.0
        my = (float(dim.start.y) + float(dim.end.y)) / 2.0
        scored.append((
            abs(float(primitive.insert.x) - mx) + abs(float(primitive.insert.y) - my),
            str(dim.axis).lower(),
        ))
    scored.sort()
    return scored[0][1]


def resolve_annotation_collisions(
    plan,
    *,
    reserved_regions=(),
    manufacturing_scene=None,
    clearance: float = 1.0,
    step: float = 5.0,
    max_steps: int = 40,
    strict: bool = False,
) -> AnnotationLayoutResult:
    """Resolve annotation collisions without moving manufacturing geometry."""
    regions = (
        tuple(reserved_regions or ())
        + _manufacturing_obstacle_regions(
            manufacturing_scene,
            clearance=float(clearance),
        )
    )
    primitives = list(tuple(getattr(plan, "primitives", ()) or ()))
    unresolved = []

    for index, primitive in enumerate(tuple(primitives)):
        if not isinstance(primitive, TextPrimitive):
            continue
        if str(primitive.layer).upper() != "DIMENSION":
            continue
        axis = _dimension_axis_for_text(plan, primitive)
        if axis not in {"x", "y"}:
            if _collides(
                primitive,
                regions + _annotation_text_regions(primitives, exclude_index=index),
            ):
                unresolved.append(AnnotationCollision(
                    index,
                    "UNRESOLVED_DIMENSION_AXIS",
                    f"cannot resolve dimension axis for text: {primitive.text}",
                ))
            continue

        own_line_index = _own_dimension_line_index(primitives, primitive, axis)
        annotation_line_regions = _annotation_dimension_line_regions(
            primitives,
            own_line_index=own_line_index,
            clearance=float(clearance),
        )
        active_regions = (
            regions
            + _annotation_text_regions(primitives, exclude_index=index)
            + annotation_line_regions
        )
        if not _collides(primitive, active_regions):
            continue

        moved = None
        for offset in _candidate_offsets(float(step), int(max_steps)):
            if offset == 0:
                continue
            if axis == "x":
                candidate = replace(
                    primitive,
                    insert=Vec2(float(primitive.insert.x) + offset, float(primitive.insert.y)),
                )
            else:
                candidate = replace(
                    primitive,
                    insert=Vec2(float(primitive.insert.x), float(primitive.insert.y) + offset),
                )
            candidate_regions = (
                regions
                + _annotation_text_regions(primitives, exclude_index=index)
                + annotation_line_regions
            )
            if not _collides(candidate, candidate_regions):
                moved = candidate
                break

        if moved is None:
            unresolved.append(AnnotationCollision(
                index,
                "UNRESOLVED_COLLISION",
                f"no legal axis-constrained position for dimension text: {primitive.text}",
            ))
        else:
            primitives[index] = moved

    result = AnnotationLayoutResult(
        primitives=tuple(primitives),
        diagnostics=tuple(c.detail for c in unresolved),
        unresolved_collisions=tuple(unresolved),
    )
    if strict and result.unresolved_collisions:
        raise ValueError(
            "unresolved annotation collisions: "
            + "; ".join(c.detail for c in result.unresolved_collisions)
        )
    return result
