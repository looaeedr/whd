# -*- coding: utf-8 -*-
"""#3317 V-miter tip relief shape experiments on canonical source material.

ROUND_R rounds the sharp removed V tip with a tangent circular arc.  A
RELIEF_HOLE unions a true circular drill-shaped relief centered at the V
intersection.  Both modify the *actual source-backed removed polygon* from
v_miter_material_trial, never a guessed stock rectangle.

Every dimension is an EXPLICIT positive multiple of source thickness T.
There is no certified default R/T or diameter/T; these read-only candidate
outlines do not prove developed bend allowance, finite-radius fold/solid
collision, kerf or factory acceptance and MUST NOT become CUTTING geometry.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import Point, Polygon

from .sheetmetal_drawing import DrawingScene, LinePrimitive, PolylinePrimitive
from .sheetmetal_geometry_core import GeometryError, Vec2
from .v_miter_corner_source import VMiterReliefMode
from .v_miter_material_trial import (
    VMiterMaterialOutlineTrial, _single_source_material,
    build_v_miter_trial_check_scene, project_v_miter_source_material_trial,
)

_AREA_TOL = 1e-6


@dataclass(frozen=True)
class VMiterReliefTrial:
    """A material-checked relief candidate, never a machine CUTTING result."""

    source_trial: VMiterMaterialOutlineTrial
    relief_mode: VMiterReliefMode
    relief_t_factor: float
    relief_dimension_mm: float  # R for ROUND_R; diameter for RELIEF_HOLE
    relief_radius_mm: float
    removed_material_area_mm2: float
    remaining_material_area_mm2: float
    trial_remaining_outline: tuple[Vec2, ...]
    cut_geometry_model: str = "IDEAL_SHARP_V_WITH_EXPLICIT_T_RELIEF_TRIAL"
    manufacturing_status: str = "V_MITER_RELIEF_CUTTING_UNCERTIFIED"


def _unit_vector_from(apex: Vec2, tip: Vec2) -> tuple[float, float, float]:
    dx, dy = tip.x - apex.x, tip.y - apex.y
    length = math.hypot(dx, dy)
    if not math.isfinite(length) or length <= _AREA_TOL:
        raise GeometryError("V-miter relief needs two positive V leg lengths")
    return dx / length, dy / length, length


def _round_v_tip(
    source: VMiterMaterialOutlineTrial,
    radius: float,
) -> Polygon:
    """Replace the sharp V cut tip with a tangent circular arc, not a hole.

    The arc is inside the removed V wedge, leaving a smoothly rounded
    material-facing notch tip.  It necessarily removes slightly less stock
    than the ideal sharp notch; it is NOT a substitute for a tear-out hole.
    """
    apex = source.ideal.source.bend_intersection
    first = source.ideal.first_flat_miter_ray[1]
    second = source.ideal.second_flat_miter_ray[1]
    ux, uy, first_len = _unit_vector_from(apex, first)
    vx, vy, second_len = _unit_vector_from(apex, second)
    dot = max(-1.0, min(1.0, ux * vx + uy * vy))
    interior = math.acos(dot)
    if not 1e-5 < interior < math.pi - 1e-5:
        raise GeometryError("V-miter relief tip has invalid included angle")
    tangent_length = radius / math.tan(interior / 2.0)
    if (not math.isfinite(tangent_length) or
            tangent_length >= min(first_len, second_len) - _AREA_TOL):
        raise GeometryError("V-miter rounded tip exceeds a V cut leg")

    bisector_x, bisector_y = ux + vx, uy + vy
    bisector_length = math.hypot(bisector_x, bisector_y)
    if bisector_length <= _AREA_TOL:
        raise GeometryError("V-miter relief cannot resolve a circular bisector")
    center_distance = radius / math.sin(interior / 2)
    cx = apex.x + bisector_x / bisector_length * center_distance
    cy = apex.y + bisector_y / bisector_length * center_distance
    p_first = (apex.x + ux * tangent_length, apex.y + uy * tangent_length)
    p_second = (apex.x + vx * tangent_length, apex.y + vy * tangent_length)

    # Walk from second tangency back to first along the MINOR arc, with
    # enough line segments for CHECK visualization (not a CNC arc command).
    start = math.atan2(p_second[1] - cy, p_second[0] - cx)
    stop = math.atan2(p_first[1] - cy, p_first[0] - cx)
    sweep = (stop - start + math.pi) % (2 * math.pi) - math.pi
    steps = max(32, math.ceil(abs(sweep) * radius / 0.25))
    if steps > 4096:
        raise GeometryError("V-miter round relief preview exceeds resolution limit")
    arc = [
        (cx + radius * math.cos(start + sweep * i / steps),
         cy + radius * math.sin(start + sweep * i / steps))
        for i in range(1, steps + 1)
    ]

    outer_arc = tuple(
        (p.x, p.y) for p in source.removed_corner_outline[1:-1]
    )
    if len(outer_arc) < 2:
        raise GeometryError("V-miter tip relief needs a source outside arc")
    rounded = Polygon((p_first, *outer_arc, p_second, *arc))
    sharp = Polygon((p.x, p.y) for p in source.removed_corner_outline)
    if rounded.difference(sharp).area > _AREA_TOL:
        raise GeometryError("V-miter rounded tip extends beyond original V wedge")
    return rounded


def project_v_miter_relief_trial(
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
) -> VMiterReliefTrial:
    """Apply explicit R/T or diameter/T to one validated CUTTING source.

    No numeric multiplier is assumed, and NONE of these choices certifies a
    new CornerType for CNC manufacture.  Categorical intent is checked using
    the SAME source qualifier as the trial, before touching any geometry.
    """
    source = project_v_miter_source_material_trial(
        scene, v_edge_bend, second_bend,
        thickness_mm=thickness_mm,
        first_flange_height_mm=first_flange_height_mm,
        second_flange_height_mm=second_flange_height_mm,
        second_fold_angle_deg=second_fold_angle_deg,
        relief_mode=relief_mode,
        relief_t_factor=relief_t_factor,
    )
    qualified = source.ideal.source
    if qualified.relief_t_factor is None:
        raise GeometryError("V-miter R/T or diameter/T requires an explicit trial factor")
    factor = qualified.relief_t_factor
    dimension = qualified.thickness_mm * factor
    if not math.isfinite(dimension) or dimension <= 0:
        raise GeometryError("V-miter trial relief dimension must be finite and positive")
    mode = qualified.relief_mode
    radius = dimension if mode is VMiterReliefMode.ROUND_R else dimension / 2
    material = _single_source_material(scene)
    sharp = Polygon((p.x, p.y) for p in source.removed_corner_outline)
    if mode is VMiterReliefMode.ROUND_R:
        removed = _round_v_tip(source, radius)
    elif mode is VMiterReliefMode.RELIEF_HOLE:
        apex = qualified.bend_intersection
        circle = Point(apex.x, apex.y).buffer(radius, resolution=48)
        if circle.difference(material).area > _AREA_TOL:
            raise GeometryError("V-miter relief hole exceeds source material boundary")
        removed = sharp.union(circle)
    else:
        raise GeometryError("V-miter unknown relief selection")

    if (removed.geom_type != "Polygon" or removed.is_empty or
            not removed.is_valid or removed.interiors or
            removed.area <= _AREA_TOL or
            removed.difference(material).area > _AREA_TOL):
        raise GeometryError("V-miter relief candidate is not a valid source material cut")
    remaining = material.difference(removed)
    if (remaining.geom_type != "Polygon" or remaining.is_empty or
            not remaining.is_valid or remaining.interiors or
            remaining.area <= _AREA_TOL):
        raise GeometryError("V-miter relief breaks the single sheet outline")
    if abs(material.area - removed.area - remaining.area) > max(
        1e-5, material.area * 1e-9,
    ):
        raise GeometryError("V-miter relief source material area does not balance")
    return VMiterReliefTrial(
        source_trial=source,
        relief_mode=mode,
        relief_t_factor=factor,
        relief_dimension_mm=dimension,
        relief_radius_mm=radius,
        removed_material_area_mm2=removed.area,
        remaining_material_area_mm2=remaining.area,
        trial_remaining_outline=tuple(
            Vec2(float(x), float(y)) for x, y in remaining.exterior.coords
        ),
    )


def build_v_miter_relief_trial_check_scene(
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
    """One CHECK-only 2D/DXF view; no CUTTING, BEND or MARKING entities."""
    parameters = dict(
        thickness_mm=thickness_mm,
        first_flange_height_mm=first_flange_height_mm,
        second_flange_height_mm=second_flange_height_mm,
        second_fold_angle_deg=second_fold_angle_deg,
        relief_mode=relief_mode,
        relief_t_factor=relief_t_factor,
    )
    preview = build_v_miter_trial_check_scene(
        scene, v_edge_bend, second_bend, **parameters,
    )
    relief = project_v_miter_relief_trial(
        scene, v_edge_bend, second_bend, **parameters,
    )
    result = DrawingScene(list(preview.primitives))
    if (len(result.primitives) != 4 or
            not isinstance(result.primitives[1], PolylinePrimitive) or
            result.primitives[1].layer != "CHECK"):
        raise GeometryError("V-miter CHECK source preview topology is unexpected")
    result.primitives[1] = PolylinePrimitive(
        points=relief.trial_remaining_outline,
        layer="CHECK", closed=True, color=2,
        semantic_id="v_miter_explicit_relief_trial_uncertified",
    )
    return result
