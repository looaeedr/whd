# -*- coding: utf-8 -*-
"""#3317 bounded BEND and sharp-fold thickness-envelope V-miter witnesses.

The previous zero-radius plane intersection is infinite: an apparently valid
formed seam can lie *past the actual source BEND endpoint*.  Do not mistake
that mathematical intersection for available material.  This module checks
the finite crease spans, then examines the local t-thick slab intersection
in a bisector plane for candidate bevel work.

NOT production CUTTING, R/Hole relief, bend allowance, formed-radius/mesh
collision verification, or a manufacturing readiness token.  In particular
a BEND endpoint is not a verified CUTTING boundary; possible material
extensions require an independent source-material check.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .sheetmetal_drawing import DrawingScene, LinePrimitive
from .sheetmetal_geometry_core import GeometryError, Vec2
from .v_miter_corner_source import VMiterReliefMode
from .v_miter_ideal_mating import (
    VMiterIdealMatingCandidate,
    Vec3, _UNIT_Z, _EPS, _add, _cross, _dot, _outside_normal,
    _outward_bend_axis, _scale, _unit, project_ideal_v_miter_mating_candidate,
)


@dataclass(frozen=True)
class VMiterBendReachWitness:
    """How the ideal intersection fits the two original finite BEND spans."""

    ideal: VMiterIdealMatingCandidate
    first_axial_seam_reach_mm: float
    second_axial_seam_reach_mm: float
    first_bend_span_mm: float
    second_bend_span_mm: float
    first_outside_bend_span_mm: float
    second_outside_bend_span_mm: float
    needs_independent_material_extension_evidence: bool
    manufacturing_status: str = "V_MITER_BOUNDED_CONTACT_UNCERTIFIED"


@dataclass(frozen=True)
class VMiterSharpThicknessWitness:
    """Ideal, zero-radius t-slab bisector *preview*, not bevel certification."""

    bounded: VMiterBendReachWitness
    bisector_normal: Vec3
    inward_cross_section_direction: Vec3
    seam_midpoint: Vec3
    cross_section_tip: Vec3
    cross_section_width_mm: float
    thickness_mm: float
    geometry_model: str = "IDEAL_SHARP_BEND_FINITE_T_SLAB_BISECTOR"
    manufacturing_status: str = "V_MITER_SHARP_THICKNESS_UNCERTIFIED"


def _source_axis_span(bend: LinePrimitive, meet: Vec2) -> tuple[Vec3, float]:
    axis = _outward_bend_axis(bend, meet)
    length = math.hypot(
        bend.p2.x - bend.p1.x, bend.p2.y - bend.p1.y,
    )
    return axis, length


def _overrun_mm(axial: float, span: float) -> float:
    # A negative axial coordinate lies behind the original crease endpoint;
    # a positive coordinate beyond span lies beyond its far endpoint.
    return max(0.0, -axial, axial - span)


def diagnose_v_miter_bounded_bend_reach(
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
) -> VMiterBendReachWitness:
    """Expose missing span evidence instead of promising nonexistent seam."""
    ideal = project_ideal_v_miter_mating_candidate(
        scene, v_edge_bend, second_bend,
        thickness_mm=thickness_mm,
        first_flange_height_mm=first_flange_height_mm,
        second_flange_height_mm=second_flange_height_mm,
        second_fold_angle_deg=second_fold_angle_deg,
        relief_mode=relief_mode,
        relief_t_factor=relief_t_factor,
    )
    at = ideal.source.bend_intersection
    first_axis, first_length = _source_axis_span(v_edge_bend, at)
    second_axis, second_length = _source_axis_span(second_bend, at)
    seam = tuple(
        ideal.formed_seam_end[i] - ideal.formed_seam_start[i] for i in range(3)
    )
    first_axial = _dot(seam, first_axis)
    second_axial = _dot(seam, second_axis)
    first_outside = _overrun_mm(first_axial, first_length)
    second_outside = _overrun_mm(second_axial, second_length)
    tolerance = 1e-7
    return VMiterBendReachWitness(
        ideal=ideal,
        first_axial_seam_reach_mm=first_axial,
        second_axial_seam_reach_mm=second_axial,
        first_bend_span_mm=first_length,
        second_bend_span_mm=second_length,
        first_outside_bend_span_mm=first_outside,
        second_outside_bend_span_mm=second_outside,
        needs_independent_material_extension_evidence=(
            first_outside > tolerance or second_outside > tolerance
        ),
    )


def project_v_miter_sharp_thickness_witness(
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
) -> VMiterSharpThicknessWitness:
    """Find a local finite-t ideal bevel plane where BEND bounds permit it.

    A single bisector plane through the seam avoids treating two intersecting
    untrimmed t-thick slabs as already non-interfering.  The tip of this
    analytical cross-section is checked inside both finite flange domains.
    Real inner R, neutral axis, cut kerf, and actual material polygons are
    *not* described by this witness.
    """
    bounded = diagnose_v_miter_bounded_bend_reach(
        scene, v_edge_bend, second_bend,
        thickness_mm=thickness_mm,
        first_flange_height_mm=first_flange_height_mm,
        second_flange_height_mm=second_flange_height_mm,
        second_fold_angle_deg=second_fold_angle_deg,
        relief_mode=relief_mode,
        relief_t_factor=relief_t_factor,
    )
    source = bounded.ideal.source
    if bounded.needs_independent_material_extension_evidence:
        raise GeometryError("V-miter seam exceeds a source BEND span; material extension unverified")
    if source.thickness_mm >= min(
        source.first_flange_height_mm, source.second_flange_height_mm,
    ):
        raise GeometryError("V-miter T is not smaller than both flange heights")

    at = source.bend_intersection
    origin: Vec3 = (at.x, at.y, 0.0)
    e1, first_span = _source_axis_span(v_edge_bend, at)
    e2, second_span = _source_axis_span(second_bend, at)
    n1, n2 = _outside_normal(e1, e2), _outside_normal(e2, e1)
    theta = math.radians(source.second_fold_angle_deg)
    b1 = _UNIT_Z
    b2 = _add(_scale(n2, math.cos(theta)),
              _scale(_UNIT_Z, math.sin(theta)))
    N1 = _unit(_cross(e1, b1), label="first formed flange normal")
    N2 = _unit(_cross(e2, b2), label="second formed flange normal")
    bisector = _unit(_add(N1, N2), label="formed flange bisector")
    d = _unit(tuple(
        bounded.ideal.formed_seam_end[i] - bounded.ideal.formed_seam_start[i]
        for i in range(3)
    ), label="formed seam")
    inward = _unit(_cross(d, bisector), label="bevel cross section")
    if _dot(inward, e1) < 0 and _dot(inward, e2) < 0:
        inward = _scale(inward, -1)
    # No arbitrary material-side guess for ambiguous/wrong wedge orientation.
    if min(_dot(inward, e1), _dot(inward, e2)) <= _EPS:
        raise GeometryError("V-miter has no shared inward bisector in both finite flanges")

    slab_normal_rate = max(abs(_dot(inward, N1)), abs(_dot(inward, N2)))
    if slab_normal_rate <= _EPS:
        raise GeometryError("V-miter thickness bisector does not cross both slabs")
    width = source.thickness_mm / (2.0 * slab_normal_rate)
    if not math.isfinite(width) or width <= _EPS:
        raise GeometryError("V-miter finite thickness contact section is degenerate")
    midpoint = _add(bounded.ideal.formed_seam_start, _scale(d, bounded.ideal.formed_contact_length_mm / 2))
    tip = _add(midpoint, _scale(inward, width))

    # Stay strictly inside the bounded crease/material-side coordinate
    # domains for this local witness; boundaries here are NOT manufacturing
    # CUTTING boundaries and cannot replace full solid collision checks.
    tolerance = 1e-7
    for axis, height_axis, normal, bend_span, height in (
        (e1, b1, N1, first_span, source.first_flange_height_mm),
        (e2, b2, N2, second_span, source.second_flange_height_mm),
    ):
        for p in (midpoint, tip):
            v = tuple(p[i] - origin[i] for i in range(3))
            along_bend = _dot(v, axis)
            along_height = _dot(v, height_axis)
            along_normal = abs(_dot(v, normal))
            if (along_bend < -tolerance or along_bend > bend_span + tolerance
                    or along_height < -tolerance or along_height > height + tolerance
                    or along_normal > source.thickness_mm / 2 + tolerance):
                raise GeometryError("V-miter finite-t cross-section exceeds source flange bounds")

    return VMiterSharpThicknessWitness(
        bounded=bounded, bisector_normal=bisector,
        inward_cross_section_direction=inward,
        seam_midpoint=midpoint, cross_section_tip=tip,
        cross_section_width_mm=width, thickness_mm=source.thickness_mm,
    )
