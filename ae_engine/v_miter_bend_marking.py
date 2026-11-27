# -*- coding: utf-8 -*-
"""Engine-owned physical MARKING for an already-resolved V-miter bend.

A slanted bend cannot rely on the press brake's parallel back gauge.  Project
actual 20 mm end strokes and intermediate 20 mm strokes separated by
approximately 50 mm of *unmarked* material along the verified BEND source.

This module does NOT infer the two-fold V-miter CUTTING shape, relief R/diameter,
sheet-metal bend allowance, or manufacturing certification.  Those require a
separately validated formed 3D/2D/Save->Reload rule.
"""
from __future__ import annotations

import math

from .sheetmetal_drawing import DrawingScene, LinePrimitive
from .sheetmetal_geometry_core import GeometryError, Vec2


def _finite_dimension(value: object, label: str) -> float:
    if isinstance(value, bool):
        raise GeometryError(f"{label} must be a finite number, not bool")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise GeometryError(f"{label} must be a finite number") from exc
    if not math.isfinite(number):
        raise GeometryError(f"{label} must be a finite number")
    return number


def project_v_miter_bend_markings(
    bend: LinePrimitive,
    *,
    stroke_mm: float = 20.0,
    clear_gap_mm: float = 50.0,
) -> tuple[LinePrimitive, ...]:
    """Turn canonical BEND linework into physical MARKING LINE segments.

    Two 20-mm end strokes remain intact whenever the bend is >= 40 mm.
    If too short, mark the entire bend once.  Intermediate strokes use the
    same length setting; remaining blank is distributed symmetrically.
    Unmarked distance is gap between stroke endpoints, not start-to-start.
    """
    if not isinstance(bend, LinePrimitive) or bend.layer != "BEND":
        raise GeometryError("V-miter marking requires a canonical BEND LinePrimitive")
    stroke = _finite_dimension(stroke_mm, "stroke_mm")
    gap = _finite_dimension(clear_gap_mm, "clear_gap_mm")
    if stroke <= 0 or gap <= 0:
        raise GeometryError("V-miter stroke and clear gap must be positive")
    x1 = _finite_dimension(bend.p1.x, "bend start x")
    y1 = _finite_dimension(bend.p1.y, "bend start y")
    x2 = _finite_dimension(bend.p2.x, "bend end x")
    y2 = _finite_dimension(bend.p2.y, "bend end y")
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if not math.isfinite(length) or length <= 0:
        raise GeometryError("V-miter BEND length must be finite and positive")
    unit_x, unit_y = dx / length, dy / length

    if length <= 2.0 * stroke:
        intervals = ((0.0, length),)
    else:
        # A middle stroke is placed only when BOTH of its adjacent blank
        # intervals can be at least clear_gap_mm.
        number_of_middle = max(
            0, math.floor((length - 2.0 * stroke - clear_gap_mm)
                              / (stroke + clear_gap_mm)),
        )
        if number_of_middle > 10000:
            raise GeometryError("V-miter bend marking would require too many strokes")
        strokes = number_of_middle + 2
        balanced_gap = (length - strokes * stroke) / (strokes - 1)
        intervals = tuple(
            (i * (stroke + balanced_gap), i * (stroke + balanced_gap) + stroke)
            for i in range(strokes)
        )

    def point(at: float) -> Vec2:
        return Vec2(x1 + unit_x * at, y1 + unit_y * at)

    return tuple(
        LinePrimitive(point(start), point(stop), layer="MARKING", color=211)
        for start, stop in intervals
    )


def with_v_miter_bend_markings(
    scene: DrawingScene,
    bend: LinePrimitive,
    *,
    stroke_mm: float = 20.0,
    clear_gap_mm: float = 50.0,
) -> DrawingScene:
    """Detached manufacturing DrawingScene with actual marking entities.

    The bend must already exist in this SAME authoritative scene.  This
    prevents callers from smuggling arbitrary guessed construction lines into
    manufacturing DXF.  CUTTING and BEND primitives remain unchanged.
    """
    if not isinstance(scene, DrawingScene):
        raise TypeError("scene must be a canonical DrawingScene")
    # Dataclass equality is not lineage. A detached BEND with identical
    # coordinates is not evidence of the scene's actual Fold source.
    if not any(row is bend for row in scene.primitives):
        raise GeometryError("V-miter marking BEND is not present in source scene")
    strokes = project_v_miter_bend_markings(
        bend, stroke_mm=stroke_mm, clear_gap_mm=clear_gap_mm,
    )

    def same_physical_marking(left, right):
        if not isinstance(left, LinePrimitive) or left.layer != "MARKING":
            return False
        return (
            (left.p1 == right.p1 and left.p2 == right.p2)
            or (left.p1 == right.p2 and left.p2 == right.p1)
        )

    already_present = tuple(
        any(same_physical_marking(existing, stroke)
            for existing in scene.primitives)
        for stroke in strokes
    )
    # Repeated projections cannot write the same engraving twice. If only
    # some strokes pre-existed, refuse instead of partially mixing material.
    if any(already_present) and not all(already_present):
        raise GeometryError("V-miter MARKING partially overlaps existing strokes")
    result = DrawingScene(list(scene.primitives))
    if not all(already_present):
        result.extend(strokes)
    return result
