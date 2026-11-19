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

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from .v_miter_material_trial import _single_source_material
from .v_miter_relief_trial import project_v_miter_relief_trial
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


@dataclass(frozen=True)
class VMiterOriginalStockCreaseExtensionWitness:
    """Real CUTTING coverage of a MISSING BEND segment; CHECK evidence only.

    A crease drawn past an existing BEND endpoint has no fold identity even
    if the *uncut* sheet contains material underneath the hypothetical
    extension. `stock_covers` proves only a necessary 2D fact, never that a
    crease exists, that the flange retains enough material after V relief,
    or that R/BA/T mating and machine parameters are safe.
    """

    bounded: VMiterBendReachWitness
    first_missing_bend_extension: tuple[Vec2, Vec2] | None
    second_missing_bend_extension: tuple[Vec2, Vec2] | None
    first_original_stock_covers_extension: bool | None
    second_original_stock_covers_extension: bool | None
    manufacturing_status: str = "V_MITER_SOURCE_BEND_EXTENSION_UNCERTIFIED"


def diagnose_v_miter_original_stock_crease_extension(
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
) -> VMiterOriginalStockCreaseExtensionWitness:
    """Check exact missing finite BEND segments against ORIGINAL CUTTING.

    This is a narrow independent stock-availability *necessary condition*
    for an operator/source-model correction, not a method of authorizing
    a virtual crease. A missing BEND stays missing even if its extension
    lies inside the original sheet: true-T and R/BA solvers MUST still
    fail closed until actual source BEND geometry is independently present.
    Do not use an inferred/preview V CUTTING polygon as the source.
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
    # This owner requires exactly one pre-existing, closed original stock
    # CUTTING. A BEND-only candidate cannot furnish missing material proof.
    material = _single_source_material(scene)
    apex = bounded.ideal.source.bend_intersection

    def missing_segment(bend, axial_reach, source_span, overrun):
        if overrun <= 1e-7:
            return None, None
        axis, actual_span = _source_axis_span(bend, apex)
        if not math.isclose(actual_span, source_span, abs_tol=1e-9):
            raise GeometryError("V-miter original BEND span changed during source check")
        # The closest real crease endpoint is either the common V corner
        # or the far end of its finite, verified original source BEND.
        nearest = max(0.0, min(axial_reach, source_span))
        a = Vec2(apex.x + axis[0] * nearest, apex.y + axis[1] * nearest)
        b = Vec2(apex.x + axis[0] * axial_reach, apex.y + axis[1] * axial_reach)
        line = LineString(((a.x, a.y), (b.x, b.y)))
        if not math.isfinite(line.length) or line.length <= 0:
            raise GeometryError("V-miter source missing BEND extension is degenerate")
        # An original CUTTING *boundary line* alone is not stock to fold:
        # require the actual missing interval's midpoint to be in the
        # positive-area interior, not just a coincident perimeter edge.
        # This remains necessary, never sufficient: a line has no width.
        covered = bool(
            material.covers(line)
            and material.contains(Point((a.x + b.x) * 0.5, (a.y + b.y) * 0.5))
        )
        return (a, b), covered

    f_segment, f_stock = missing_segment(
        v_edge_bend,
        bounded.first_axial_seam_reach_mm,
        bounded.first_bend_span_mm,
        bounded.first_outside_bend_span_mm,
    )
    s_segment, s_stock = missing_segment(
        second_bend,
        bounded.second_axial_seam_reach_mm,
        bounded.second_bend_span_mm,
        bounded.second_outside_bend_span_mm,
    )
    if (f_segment is not None or s_segment is not None) != (
        bounded.needs_independent_material_extension_evidence
    ):
        raise GeometryError("V-miter missing crease coverage disagrees with finite BEND reach")
    return VMiterOriginalStockCreaseExtensionWitness(
        bounded=bounded,
        first_missing_bend_extension=f_segment,
        second_missing_bend_extension=s_segment,
        first_original_stock_covers_extension=f_stock,
        second_original_stock_covers_extension=s_stock,
    )



@dataclass(frozen=True)
class VMiterPhysicalCreaseAfterReliefWitness:
    """Source BEND and post-V-cut material independently checked, NOT safe to bend.

    All reported crease segments come from the actual source seam demand.
    Even when an additional original BEND covers a missing segment and that
    interval survives the trial R/hole cut, its full-width flange topology,
    true-T/real-R/BA collision, tolerance and shop process remain unverified.
    """

    original_stock: VMiterOriginalStockCreaseExtensionWitness
    first_original_bend_continuation_covers: bool | None
    second_original_bend_continuation_covers: bool | None
    first_remaining_material_interior_covers: bool | None
    second_remaining_material_interior_covers: bool | None
    first_remaining_interior_crease_length_mm: float | None
    second_remaining_interior_crease_length_mm: float | None
    manufacturing_status: str = "V_MITER_POST_RELIEF_CREASE_UNCERTIFIED"


def diagnose_v_miter_physical_crease_after_relief(
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
) -> VMiterPhysicalCreaseAfterReliefWitness:
    """Check real extra BEND ownership AND material after the actual R/hole V.

    A 60-degree ideal seam may extend past a source BEND endpoint even when
    its *original* CUTTING contains metal. Additional genuine, collinear BEND
    primitives must cover that entire extension; more importantly, the same
    physical interval must not be removed or turn into a boundary-only line
    by the V relief itself. A material boundary is not a foldable interior.

    The V subtraction comes only from the existing Engine trial source, not
    a synthesized square or second relief formula. A positive result is
    diagnostic, NEVER a certificate or a way to skip bounded true-T/R/BA.
    """
    arguments = dict(
        thickness_mm=thickness_mm,
        first_flange_height_mm=first_flange_height_mm,
        second_flange_height_mm=second_flange_height_mm,
        second_fold_angle_deg=second_fold_angle_deg,
        relief_mode=relief_mode,
        relief_t_factor=relief_t_factor,
    )
    stock = diagnose_v_miter_original_stock_crease_extension(
        scene, v_edge_bend, second_bend, **arguments,
    )
    relief = project_v_miter_relief_trial(
        scene, v_edge_bend, second_bend, **arguments,
    )
    remaining = Polygon((
        (p.x, p.y) for p in relief.trial_remaining_outline
    ))
    if (remaining.is_empty or remaining.geom_type != "Polygon"
            or not remaining.is_valid or remaining.interiors
            or remaining.area <= 0):
        raise GeometryError("V-miter post-relief crease has no valid single remaining sheet")

    # Only pre-existing canonical BEND primitives can prove an extension.
    # A CHECK, DATUM, MARKING or virtual seam ray never does. Reusing the
    # selected first/second BEND would mask their *known* missing span.
    extra_bends = tuple(
        LineString(((item.p1.x, item.p1.y), (item.p2.x, item.p2.y)))
        for item in scene.primitives
        if isinstance(item, LinePrimitive) and item.layer == "BEND"
        and item is not v_edge_bend and item is not second_bend
    )

    def examine(extension):
        if extension is None:
            return None, None, None
        start, end = extension
        missing = LineString(((start.x, start.y), (end.x, end.y)))
        if not math.isfinite(missing.length) or missing.length <= 0:
            raise GeometryError("V-miter post-relief missing crease is degenerate")
        # A point crossing or a parallel-but-offset BEND provides zero
        # coincident length and cannot contribute to crease ownership.
        real_overlaps = tuple(
            bend.intersection(missing) for bend in extra_bends
            if bend.intersection(missing).length > 0
        )
        # No gap tolerated in the actual continuous source crease. Union
        # of genuine segments allows a multi-segment, reversed-direction
        # source, but an unbridged gap must never be inferred as a BEND.
        source_covered = bool(
            real_overlaps and missing.difference(unary_union(real_overlaps)).is_empty
        )
        # Count exactly how much of the demanded crease occupies actual
        # remaining material INTERIOR, excluding boundary-coincident lines.
        # Endpoint touches are fine; any positive-length overlap with the
        # new cutting perimeter is NOT foldable full-width material.
        surviving = missing.intersection(remaining)
        interior = float(surviving.difference(remaining.boundary).length)
        if not math.isfinite(interior) or interior < 0 or interior > missing.length + 1e-7:
            raise GeometryError("V-miter post-relief crease interval length is invalid")
        interior_full = bool(
            remaining.covers(missing)
            and remaining.contains(missing.interpolate(0.5, normalized=True))
            and missing.intersection(remaining.boundary).length == 0.0
        )
        return source_covered, interior_full, interior

    first = examine(stock.first_missing_bend_extension)
    second = examine(stock.second_missing_bend_extension)
    return VMiterPhysicalCreaseAfterReliefWitness(
        original_stock=stock,
        first_original_bend_continuation_covers=first[0],
        second_original_bend_continuation_covers=second[0],
        first_remaining_material_interior_covers=first[1],
        second_remaining_material_interior_covers=second[1],
        first_remaining_interior_crease_length_mm=first[2],
        second_remaining_interior_crease_length_mm=second[2],
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
