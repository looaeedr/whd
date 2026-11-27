# -*- coding: utf-8 -*-
"""#3317 source-backed visible fold strokes for the single-sheet V trial.

Only pre-existing physical BEND line segments in the SAME original
FinalScene may produce CHECK witness strokes. Intersect those lines with
the proposed post-V remaining material; never extend a crease across the
missing corner or put physical MARKING into an uncertified DXF.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import LineString, Polygon

from .sheetmetal_drawing import DrawingScene, LinePrimitive
from .sheetmetal_geometry_core import GeometryError, Vec2
from .v_miter_bend_marking import project_v_miter_bend_markings
from .v_miter_material_trial import (
    VMiterSourceBoundSharpCheck, _single_source_material,
)


@dataclass(frozen=True)
class VMiterSourceBendMarkingCheck:
    """Actual BEND source and material overlap, never machine authorization."""

    first_source_span_mm: float
    second_source_span_mm: float
    first_surviving_crease_mm: float
    second_surviving_crease_mm: float
    first_source_stroke_count: int
    second_source_stroke_count: int
    check_strokes: tuple[LinePrimitive, ...]
    geometry_model: str = "ACTUAL_BEND_INTERSECT_POST_V_MATERIAL_20_50_MARK_CHECK"
    manufacturing_status: str = "V_MITER_SOURCE_BEND_MARKING_UNCERTIFIED"


def _real_bend_survival_segments(
    source: LinePrimitive, remaining: Polygon,
) -> tuple[LineString, ...]:
    """Only real portions of the source crease *inside* surviving sheet.

    Removing the narrow numerical neighborhood of CUTTING is NOT a shop
    marking clearance or an added bend: it avoids inventing a physical mark
    exactly along a cut edge when the real material has zero side width.
    """
    physical = LineString((
        (source.p1.x, source.p1.y),
        (source.p2.x, source.p2.y),
    ))
    if not math.isfinite(physical.length) or physical.length <= 1e-7:
        raise GeometryError("V_MITER_MARKING_PHYSICAL_BEND_INVALID")
    interior = physical.intersection(remaining).difference(
        remaining.boundary.buffer(1e-7)
    )
    result = []
    parts = (interior,) if interior.geom_type == "LineString" else tuple(
        getattr(interior, "geoms", ())
    )
    for part in parts:
        if part.geom_type != "LineString" or part.length <= 1e-7:
            continue
        if (not math.isfinite(part.length)
                or part.difference(physical.buffer(1e-7)).length > 1e-7
                or part.difference(remaining.buffer(1e-7)).length > 1e-7):
            raise GeometryError("V_MITER_MARKING_SOURCE_BEND_LINEAGE_MISMATCH")
        result.append(part)
    if len(result) > 32:
        raise GeometryError("V_MITER_MARKING_TOO_MANY_SOURCE_SEGMENTS")
    return tuple(result)


def project_v_miter_source_bend_marking_check(
    original_scene: DrawingScene,
    first_physical_bend: LinePrimitive,
    second_physical_bend: LinePrimitive,
    source_check: VMiterSourceBoundSharpCheck,
) -> VMiterSourceBendMarkingCheck:
    """Project 20-mm end strokes, 20/50 middle strokes on genuine BEND only.

    A CHECK may show how to aim the actual press strokes; NO output from this
    function can be accepted as certified MARKING, BEND, or DXF manufacture.
    Missing original BEND spans remain visibly *missing*, even if the V
    candidate contains enough metal to hypothetically extend one.
    """
    if (not isinstance(original_scene, DrawingScene)
            or not isinstance(source_check, VMiterSourceBoundSharpCheck)
            or first_physical_bend is second_physical_bend):
        raise GeometryError("V_MITER_MARKING_SOURCE_TYPE_OR_IDENTITY_INVALID")
    _single_source_material(original_scene)
    for bend in (first_physical_bend, second_physical_bend):
        if not isinstance(bend, LinePrimitive) or bend.layer != "BEND":
            raise GeometryError("V_MITER_MARKING_PHYSICAL_BEND_REQUIRED")
        if not any(row is bend for row in original_scene.primitives):
            raise GeometryError("V_MITER_MARKING_ORIGINAL_BEND_IDENTITY_REQUIRED")
    candidate = Polygon(((p.x, p.y) for p in source_check.remaining_outline))
    if (candidate.geom_type != "Polygon" or candidate.is_empty
            or not candidate.is_valid or candidate.interiors
            or candidate.area <= 0
            or abs(candidate.area - source_check.remaining_material_area_mm2) > 1e-6):
        raise GeometryError("V_MITER_MARKING_REMAINING_SOURCE_INVALID")

    strokes = []
    lengths = []
    counts = []
    source_lengths = []
    for physical_bend in (first_physical_bend, second_physical_bend):
        source_len = math.hypot(
            physical_bend.p2.x - physical_bend.p1.x,
            physical_bend.p2.y - physical_bend.p1.y,
        )
        source_lengths.append(source_len)
        segments = _real_bend_survival_segments(physical_bend, candidate)
        coverage = sum(row.length for row in segments)
        if coverage > source_len + 1e-6:
            raise GeometryError("V_MITER_MARKING_SURVIVAL_EXCEEDS_ORIGINAL_BEND")
        lengths.append(coverage)
        before = len(strokes)
        for segment in segments:
            x1, y1 = segment.coords[0]
            x2, y2 = segment.coords[-1]
            physically_clipped = LinePrimitive(
                Vec2(float(x1), float(y1)),
                Vec2(float(x2), float(y2)), layer="BEND",
            )
            for source_mark in project_v_miter_bend_markings(
                physically_clipped, stroke_mm=20.0, clear_gap_mm=50.0,
            ):
                # No numerical manufacturing formula in the GUI; CHECK-only
                # segment retains the same physical coordinate as Engine
                # MARKING projector but is never an approved MARKING layer.
                strokes.append(LinePrimitive(
                    source_mark.p1, source_mark.p2, "CHECK", color=4,
                ))
        counts.append(len(strokes) - before)
    return VMiterSourceBendMarkingCheck(
        first_source_span_mm=source_lengths[0],
        second_source_span_mm=source_lengths[1],
        first_surviving_crease_mm=lengths[0],
        second_surviving_crease_mm=lengths[1],
        first_source_stroke_count=counts[0],
        second_source_stroke_count=counts[1],
        check_strokes=tuple(strokes),
    )
