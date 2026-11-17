# -*- coding: utf-8 -*-
"""#3317 V-miter *trial-only* material subtraction from true CUTTING source.

Unlike infinite plane intersections, this boundary check uses the actual
single-piece canonical closed CUTTING polygon in the SAME DrawingScene as
the two BENDs.  The ideal V legs must end on that existing perimeter, and
only the shorter exterior corner arc may be replaced by their two rays.

This is NOT a certified operator CUTTING polygon.  The ideal zero-radius
bend model lacks actual sheet-neutral-axis compensation, real inside R,
relief R/Hole drill diameter / tangency and formed solid collision proof.
Return only immutable trial outline coordinates, never a CUTTING primitive
or a manufacturing authorization.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring

from .sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive
from .sheetmetal_geometry_core import GeometryError, Vec2
from .v_miter_corner_source import VMiterReliefMode
from .v_miter_ideal_mating import (
    VMiterIdealMatingCandidate, _dot, _outward_bend_axis, _outside_normal,
    project_ideal_v_miter_mating_candidate,
)

_TOL = 1e-6


@dataclass(frozen=True)
class VMiterMaterialOutlineTrial:
    """Source-backed polygon subtraction, with no manufacturing capability."""

    ideal: VMiterIdealMatingCandidate
    source_material_area_mm2: float
    removed_material_area_mm2: float
    remaining_material_area_mm2: float
    removed_corner_outline: tuple[Vec2, ...]
    trial_remaining_outline: tuple[Vec2, ...]
    cut_geometry_model: str = "IDEAL_ZERO_R_SOURCE_MATERIAL_TRIAL_ONLY"
    manufacturing_status: str = "V_MITER_TRIAL_CUTTING_UNCERTIFIED"


def _single_source_material(scene: DrawingScene) -> Polygon:
    cuts = tuple(
        row for row in scene.primitives
        if str(getattr(row, "layer", "")).upper() == "CUTTING"
    )
    if len(cuts) != 1 or not isinstance(cuts[0], PolylinePrimitive):
        raise GeometryError("V-miter trial needs exactly one canonical closed CUTTING polyline")
    primitive = cuts[0]
    if not primitive.closed and (
        not primitive.points or primitive.points[0] != primitive.points[-1]
    ):
        raise GeometryError("V-miter source CUTTING must be closed")
    if len(primitive.points) < 3:
        raise GeometryError("V-miter source CUTTING has too few vertices")
    if any(
        not (math.isfinite(point.x) and math.isfinite(point.y))
        for point in primitive.points
    ):
        raise GeometryError("V-miter source CUTTING has non-finite vertices")
    material = Polygon([(p.x, p.y) for p in primitive.points])
    if (material.is_empty or not material.is_valid or material.geom_type != "Polygon"
            or material.area <= _TOL or material.interiors):
        raise GeometryError("V-miter source CUTTING must be one valid solid material polygon")
    return material


def _arc_from_to(ring: LineString, start: float, end: float) -> tuple[tuple[float, float], ...]:
    length = ring.length
    if end >= start:
        return tuple((float(x), float(y)) for x, y in substring(ring, start, end).coords)
    tail = tuple(substring(ring, start, length).coords)
    head = tuple(substring(ring, 0.0, end).coords)
    return tuple((float(x), float(y)) for x, y in tail + head[1:])


def _short_outer_arc(
    material: Polygon,
    first_tip: Vec2,
    second_tip: Vec2,
) -> tuple[tuple[float, float], ...]:
    ring = LineString(material.exterior.coords)
    a = Point(first_tip.x, first_tip.y)
    b = Point(second_tip.x, second_tip.y)
    if ring.distance(a) > _TOL or ring.distance(b) > _TOL:
        raise GeometryError("V-miter trial V leg endpoint is not on source CUTTING perimeter")
    if a.distance(b) <= _TOL:
        raise GeometryError("V-miter trial requires distinct perimeter endpoints")
    start = ring.project(a)
    end = ring.project(b)
    perimeter = ring.length
    forward_distance = (end - start) % perimeter
    backward_distance = (start - end) % perimeter
    if min(forward_distance, backward_distance) <= _TOL or abs(forward_distance - backward_distance) <= _TOL:
        raise GeometryError("V-miter trial outer corner arc cannot be unambiguously chosen")
    if forward_distance < backward_distance:
        result = _arc_from_to(ring, start, end)
    else:
        result = tuple(reversed(_arc_from_to(ring, end, start)))
    if len(result) < 2:
        raise GeometryError("V-miter trial source outer arc has no length")
    return result


def project_v_miter_source_material_trial(
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
) -> VMiterMaterialOutlineTrial:
    """Trial V notch bounded by an existing cutting perimeter, not made-up stock."""
    ideal = project_ideal_v_miter_mating_candidate(
        scene, v_edge_bend, second_bend, thickness_mm=thickness_mm,
        first_flange_height_mm=first_flange_height_mm,
        second_flange_height_mm=second_flange_height_mm,
        second_fold_angle_deg=second_fold_angle_deg,
        relief_mode=relief_mode,
        relief_t_factor=relief_t_factor,
    )
    material = _single_source_material(scene)
    apex = ideal.source.bend_intersection
    apex_point = Point(apex.x, apex.y)
    if not material.contains(apex_point):
        raise GeometryError("V-miter trial bend intersection must be inside source material")
    first_tip = ideal.first_flat_miter_ray[1]
    second_tip = ideal.second_flat_miter_ray[1]
    outer_arc = _short_outer_arc(material, first_tip, second_tip)

    # Outward wedge side is determined from the two source BEND axes, not
    # guessed from a canvas quadrant or user-facing corner name.
    e1 = _outward_bend_axis(v_edge_bend, apex)
    e2 = _outward_bend_axis(second_bend, apex)
    n1 = _outside_normal(e1, e2)
    n2 = _outside_normal(e2, e1)
    # Use the TWO ACTUAL unfolded V rays, not the original fold axes, as
    # the angular bounds. At a 120-degree second fold a legitimate unequal
    # V cut crosses the original orthogonal crease wedge; testing that
    # fixed wedge would wrongly reject it. A concave source perimeter can
    # still overhang *outside the true V-cut sector* while its midpoint
    # looks correct. The sector is convex (two ray half-planes), so checking
    # every straight arc vertex proves every connecting segment is inside.
    first_dx, first_dy = first_tip.x - apex.x, first_tip.y - apex.y
    second_dx, second_dy = second_tip.x - apex.x, second_tip.y - apex.y
    first_len, second_len = math.hypot(first_dx, first_dy), math.hypot(second_dx, second_dy)
    if not (math.isfinite(first_len) and math.isfinite(second_len)
            and min(first_len, second_len) > _TOL):
        raise GeometryError("V-miter trial cut sector has invalid ray lengths")
    ux, uy = first_dx / first_len, first_dy / first_len
    vx, vy = second_dx / second_len, second_dy / second_len
    sector_cross = ux * vy - uy * vx
    if abs(sector_cross) <= _TOL:
        raise GeometryError("V-miter trial cut sector is degenerate")
    orientation = 1.0 if sector_cross > 0 else -1.0
    for x, y in outer_arc:
        relative_x, relative_y = x - apex.x, y - apex.y
        first_side = orientation * (ux * relative_y - uy * relative_x)
        second_side = orientation * (relative_x * vy - relative_y * vx)
        if min(first_side, second_side) < -_TOL:
            raise GeometryError(
                "V-miter trial exterior arc leaves the actual V cut sector"
            )
    middle_arc_point = LineString(outer_arc).interpolate(LineString(outer_arc).length / 2)
    arc_relative = (
        middle_arc_point.x - apex.x, middle_arc_point.y - apex.y, 0.0,
    )
    if min(_dot(arc_relative, n1), _dot(arc_relative, n2)) <= _TOL:
        raise GeometryError("V-miter trial exterior arc is not on the physical outside wedge")

    cut = Polygon([(apex.x, apex.y)] + list(outer_arc))
    if not cut.is_valid or cut.is_empty or cut.area <= _TOL:
        raise GeometryError("V-miter trial removed material polygon is invalid")
    if cut.difference(material).area > _TOL:
        raise GeometryError("V-miter trial removal runs outside source material")
    remaining = material.difference(cut)
    if (remaining.geom_type != "Polygon" or remaining.is_empty or
            not remaining.is_valid or remaining.interiors or
            remaining.area <= _TOL or
            material.area - remaining.area <= _TOL):
        raise GeometryError("V-miter trial would break single-piece CUTTING topology")
    if abs(material.area - remaining.area - cut.area) > max(1e-5, material.area * 1e-9):
        raise GeometryError("V-miter trial removal area does not balance")

    return VMiterMaterialOutlineTrial(
        ideal=ideal,
        source_material_area_mm2=material.area,
        removed_material_area_mm2=cut.area,
        remaining_material_area_mm2=remaining.area,
        removed_corner_outline=tuple(Vec2(x, y) for x, y in cut.exterior.coords),
        trial_remaining_outline=tuple(
            Vec2(x, y) for x, y in remaining.exterior.coords
        ),
    )



def build_v_miter_trial_check_scene(
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
) -> DrawingScene:
    """Read-only 2D/DXF *CHECK* preview, never a manufacture-able CUTTING.

    The real source CUTTING perimeter is shown as a DATUM reference; the
    ideal trial remaining perimeter is CHECK.  Source BENDs are displayed
    as DATUM too, so saving this *preview* cannot create CNC BEND actions,
    CUTTING paths, or MARKING toolpaths from uncertified V-miter geometry.
    No GUI-owned copy of the V-cut algorithm is permitted.
    """
    trial = project_v_miter_source_material_trial(
        scene, v_edge_bend, second_bend,
        thickness_mm=thickness_mm,
        first_flange_height_mm=first_flange_height_mm,
        second_flange_height_mm=second_flange_height_mm,
        second_fold_angle_deg=second_fold_angle_deg,
        relief_mode=relief_mode,
        relief_t_factor=relief_t_factor,
    )
    material = _single_source_material(scene)
    result = DrawingScene()
    result.add(PolylinePrimitive(
        points=tuple(Vec2(x, y) for x, y in material.exterior.coords),
        layer="DATUM", closed=True, color=6,
        semantic_id="v_miter_source_reference_only",
    ))
    result.add(PolylinePrimitive(
        points=trial.trial_remaining_outline,
        layer="CHECK", closed=True, color=2,
        semantic_id="v_miter_uncertified_trial_only",
    ))
    for source_bend in (v_edge_bend, second_bend):
        result.add(LinePrimitive(
            p1=source_bend.p1, p2=source_bend.p2,
            layer="DATUM", color=6,
        ))
    return result
