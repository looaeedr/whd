# -*- coding: utf-8 -*-
"""#3317 V-miter source qualification before any material is cut.

This is the typed *input* seam for a future certified V-miter solver.  It uses
the SAME canonical BEND lines that the existing manufacturing renderer and
physical MARKING projector consume.  The first V-edge fold is 90 degrees;
the second fold angle and two flange heights are independent operator inputs.

The two photographs do not certify a CUTTING shape, bend allowance or a
relief R/diameter T ratio.  An accepted source is therefore NOT a certified
manufacturing result: it must not appear in the editable CornerType catalog
until 2D CUTTING, formed 3D contact, and Save->Reload/DXF are verified.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

from .sheetmetal_drawing import DrawingScene, LinePrimitive
from .sheetmetal_geometry import BendLine, GeometryError, Vec2, line_intersection


class VMiterReliefMode(str, Enum):
    """The two approved *choices*, not certified relief dimensions."""

    ROUND_R = "ROUND_R"
    RELIEF_HOLE = "RELIEF_HOLE"


@dataclass(frozen=True)
class VMiterSourceQualification:
    """Validated fold-source facts; never a CUTTING or DXF release token."""

    bend_intersection: Vec2
    flat_bend_line_angle_deg: float
    first_fold_angle_deg: float
    second_fold_angle_deg: float
    first_flange_height_mm: float
    second_flange_height_mm: float
    thickness_mm: float
    relief_mode: VMiterReliefMode
    relief_t_factor: float | None
    manufacturing_status: str = "V_MITER_CUTTING_UNCERTIFIED"


def _finite(value: object, name: str, *, positive: bool = False) -> float:
    if isinstance(value, bool):
        raise GeometryError(f"{name} must be a finite number, not bool")
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise GeometryError(f"{name} must be a finite number") from exc
    if not math.isfinite(result) or (positive and result <= 0):
        raise GeometryError(f"{name} must be finite and positive" if positive
                            else f"{name} must be finite")
    return result


def qualify_v_miter_corner_source(
    scene: DrawingScene,
    v_edge_bend: LinePrimitive,
    second_bend: LinePrimitive,
    *,
    thickness_mm: float,
    first_flange_height_mm: float,
    second_flange_height_mm: float,
    second_fold_angle_deg: float,
    relief_mode: VMiterReliefMode | str,
    relief_t_factor: float | None = None,
) -> VMiterSourceQualification:
    """Check source identity, geometry, fold order and unfinished relief inputs.

    This does not derive the V CUTTING contour: that depends on true formed
    3D contact (including bend radius/allowance) and certified relief.  It
    deliberately refuses parallel/coincident/zero-length fold-line sources.
    """
    if not isinstance(scene, DrawingScene):
        raise TypeError("V-miter source must be a canonical DrawingScene")
    for role, bend in (("first", v_edge_bend), ("second", second_bend)):
        if not isinstance(bend, LinePrimitive) or bend.layer != "BEND":
            raise GeometryError(f"V-miter {role} line must be a BEND LinePrimitive")
        if not any(row is bend for row in scene.primitives):
            raise GeometryError(f"V-miter {role} BEND is not in original scene")
    if v_edge_bend is second_bend:
        raise GeometryError("V-miter needs two distinct source BEND lines")

    first_height = _finite(
        first_flange_height_mm, "first_flange_height_mm", positive=True,
    )
    second_height = _finite(
        second_flange_height_mm, "second_flange_height_mm", positive=True,
    )
    t = _finite(thickness_mm, "thickness_mm", positive=True)
    second_angle = _finite(second_fold_angle_deg, "second_fold_angle_deg")
    if not 0 < second_angle < 180:
        raise GeometryError("second_fold_angle_deg must be between 0 and 180")
    try:
        mode = VMiterReliefMode(relief_mode)
    except (ValueError, TypeError) as exc:
        raise GeometryError("V-miter relief_mode must be ROUND_R or RELIEF_HOLE") from exc
    factor = (
        None if relief_t_factor is None else
        _finite(relief_t_factor, "relief_t_factor", positive=True)
    )
    lines = []
    for role, bend in (("first", v_edge_bend), ("second", second_bend)):
        x1 = _finite(bend.p1.x, f"{role} bend start x")
        y1 = _finite(bend.p1.y, f"{role} bend start y")
        x2 = _finite(bend.p2.x, f"{role} bend end x")
        y2 = _finite(bend.p2.y, f"{role} bend end y")
        if not (math.hypot(x2 - x1, y2 - y1) > 0):
            raise GeometryError(f"{role} bend must have positive length")
        lines.append(BendLine(role, Vec2(x1, y1), Vec2(x2, y2)))

    # Reuse the existing Engine Fold topology's intersection operation:
    # the meeting point is a source fact, never a projected V cutter.
    meet = line_intersection(lines[0], lines[1])
    if not math.isfinite(meet.x) or not math.isfinite(meet.y):
        raise GeometryError("V-miter bend intersection must be finite")
    a = lines[0].p2 - lines[0].p1
    b = lines[1].p2 - lines[1].p1
    cross = abs(a.x * b.y - a.y * b.x)
    dot = a.x * b.x + a.y * b.y
    flat_angle = math.degrees(math.atan2(cross, dot))
    if not math.isfinite(flat_angle) or flat_angle <= 0 or flat_angle >= 180:
        raise GeometryError("V-miter needs two nonparallel bend lines")

    return VMiterSourceQualification(
        bend_intersection=meet,
        flat_bend_line_angle_deg=flat_angle,
        first_fold_angle_deg=90.0,
        second_fold_angle_deg=second_angle,
        first_flange_height_mm=first_height,
        second_flange_height_mm=second_height,
        thickness_mm=t,
        relief_mode=mode,
        relief_t_factor=factor,
    )
