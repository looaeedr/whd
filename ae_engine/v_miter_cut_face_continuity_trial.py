# -*- coding: utf-8 -*-
"""#3317 source-proven V-cut face topology intervals, CHECK only.

The legacy seven seam samples can miss a short, real break between stations.
True-T source-tagged V-cut triangles have LINEAR projection on the source
seam axis. Their vertex projections divide that finite seam into maximal
open intervals on which triangle-presence topology cannot change. Inspect
each interval's interior rather than inventing a spacing in millimetres.

This is exact *interval coverage topology* for the supplied triangle mesh,
not an analytic maximum gap, continuous 3D face contact, safe bevel/toolpath,
permissible factory tolerance or manufacturing certification.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import LineString, MultiLineString
from shapely.ops import nearest_points

from .contracts import PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES
from .sheetmetal_geometry_core import GeometryError
from .v_miter_seam_gap_trial import (
    VMiterSeamSectionGap,
    _cross, _dot, _mesh, _mul, _point, _section_segments, _sub, _unit,
    project_v_miter_true_t_seam_section_gap_trial,
)


_MAX_OPEN_INTERVALS = 4096


@dataclass(frozen=True)
class VMiterCutFaceOpenIntervalTrial:
    """One source-mesh event-to-event OPEN span, not a factory seam tolerance."""

    start_fraction: float
    end_fraction: float
    start_mm: float
    end_mm: float
    length_mm: float
    midpoint_section: VMiterSeamSectionGap
    # Bounding the *true geometric mesh* section gap over the WHOLE open
    # interval uses triangle-edge transverse speed, not a factory gap.
    # None is intentional if a numerical source event cannot be resolved.
    max_gap_lower_bound_mm: float | None = None
    max_gap_upper_bound_mm: float | None = None
    min_gap_lower_bound_mm: float | None = None
    min_gap_upper_bound_mm: float | None = None
    combined_transverse_speed: float | None = None
    transverse_bounding_box_cap_mm: float | None = None
    gap_bound_status: str = "NOT_EVALUATED"

    @property
    def has_both_cut_faces(self) -> bool:
        return self.midpoint_section.status == "MEASURED"


@dataclass(frozen=True)
class VMiterCutFaceContinuityTrial:
    """Interval-complete source-face coverage evidence, non-certified mating."""

    seam_length_mm: float
    intervals: tuple[VMiterCutFaceOpenIntervalTrial, ...]
    both_face_interval_count: int
    missing_face_interval_count: int
    both_face_span_mm: float
    first_missing_span_mm: float
    second_missing_span_mm: float
    both_missing_span_mm: float
    min_sampled_cut_face_gap_mm: float | None
    max_sampled_cut_face_gap_mm: float | None
    min_sampled_datum_gap_mm: float | None
    max_sampled_datum_gap_mm: float | None
    numerically_unresolved_vertex_event_count: int
    coverage_status: str  # FACE_COVERAGE_INCOMPLETE | FACE_COVERAGE_SAMPLED_ONLY
    max_gap_lower_bound_mm: float | None = None
    max_gap_upper_bound_mm: float | None = None
    min_gap_lower_bound_mm: float | None = None
    min_gap_upper_bound_mm: float | None = None
    gap_bound_status: str = "UNRESOLVED_OR_PARTIAL_SOURCE_COVERAGE"
    geometry_model: str = "SOURCE_TRUE_T_V_CUT_FACE_OPEN_INTERVAL_TOPOLOGY_CHECK"
    manufacturing_status: str = "V_MITER_CUT_FACE_CONTINUITY_UNCERTIFIED"



def _section_transverse_speed_bound(mesh, start, direction, lo_mm, hi_mm):
    """Finite Lipschitz speed of actual *planar triangle* section geometry.

    Inside an open interval between EVERY vertex projection event, each
    contributing triangle intersects every section in a line segment.
    Its endpoints slide *linearly* along two original triangle edges.
    For an edge e with axial delta a and perpendicular delta p, the
    section-endpoint transverse speed is exactly |p|/|a| (mm/mm).
    A segment's whole geometry moves no faster than its fastest endpoint.
    Thus its per-triangle Hausdorff speed is bounded by this maximum, and
    the union of all contributing triangle sections is bounded by the
    maximum speed over its contributing triangles.
    """
    mid = (lo_mm + hi_mm) * 0.5
    max_speed = 0.0
    active = False
    for triangle in mesh:
        axial = tuple(_dot(_sub(point, start), direction) for point in triangle)
        if max(axial) <= mid or min(axial) >= mid:
            continue
        active = True
        # Because all original mesh-vertex stations define our interval
        # endpoints, this triangle must cover the ENTIRE open interval.
        # A missed vertex event or grouped near-vertex invalidates the
        # mathematical speed certificate instead of silently shrinking it.
        # Stations were first projected as fractions and later converted
        # back to millimetres. That multiplication can shift an otherwise
        # identical mesh-vertex station by a few IEEE-754 ulps. Do not turn
        # those roundoff bits into a false geometric topology violation.
        # A missed physical vertex beyond float roundoff STILL fails closed.
        arithmetic_roundoff = 16.0 * math.ulp(
            max(1.0, abs(lo_mm), abs(hi_mm))
        )
        if (min(axial) > lo_mm + arithmetic_roundoff or
                max(axial) < hi_mm - arithmetic_roundoff):
            raise GeometryError(
                "V-miter cut-face speed interval crosses an untracked mesh vertex"
            )
        crossing = 0
        for i in range(3):
            j = (i + 1) % 3
            ai, aj = axial[i], axial[j]
            if not (min(ai, aj) < mid < max(ai, aj)):
                continue
            diff = _sub(triangle[j], triangle[i])
            longitudinal = aj - ai
            perpendicular = _sub(diff, _mul(direction, longitudinal))
            speed = math.sqrt(max(0.0, _dot(perpendicular, perpendicular))) / abs(longitudinal)
            if not math.isfinite(speed):
                raise GeometryError("V-miter cut-face transverse speed is nonfinite")
            max_speed = max(max_speed, speed)
            crossing += 1
        if not crossing:
            raise GeometryError("V-miter cut-face interval has no moving source edge")
    return max_speed if active else None



def _perpendicular_cut_face_bbox_gap_cap(
    first, second, start, direction, lo_mm, hi_mm,
):
    """Second INDEPENDENT, conservative envelope from actual world vertices.

    Every physical triangle section point is a convex combination of the
    triangle's genuine 3D vertices. For the whole open vertex-event
    interval its participating triangles are fixed, so projecting all
    contributing *real vertices* onto the plane perpendicular to the
    source seam yields two enclosing 2D boxes. The farthest distance
    between these boxes bounds the separation of ANY pair of physical
    section points; in particular it bounds the nearest-point gap.
    Unlike the slope envelope this can be tight even when a triangulation
    diagonal 'moves' rapidly but its combined physical surface is static.
    It is still NOT a continuous contact proof or a factory tolerance.
    """
    reference = (0.0, 0.0, 1.0) if abs(direction[2]) < 0.9 else (1.0, 0.0, 0.0)
    u = _unit(_cross(direction, reference))
    v = _unit(_cross(direction, u))
    mid = (lo_mm + hi_mm) * 0.5

    def bounds(mesh):
        xy = []
        for tri in mesh:
            axial = tuple(_dot(_sub(p, start), direction) for p in tri)
            if max(axial) <= mid or min(axial) >= mid:
                continue
            for p in tri:
                delta = _sub(p, start)
                xy.append((_dot(delta, u), _dot(delta, v)))
        if not xy:
            return None
        return (
            min(x for x, y in xy), max(x for x, y in xy),
            min(y for x, y in xy), max(y for x, y in xy),
        )

    a, b = bounds(first), bounds(second)
    if a is None or b is None:
        return None
    dx = max(abs(a[1] - b[0]), abs(b[1] - a[0]))
    dy = max(abs(a[3] - b[2]), abs(b[3] - a[2]))
    cap = math.hypot(dx, dy)
    if not math.isfinite(cap) or cap < 0:
        raise GeometryError("V-miter cut-face 3D projected bounding cap invalid")
    return cap


def _midpoint_exact_cut_face_gap(first, second, start, direction, station_mm):
    """Independent *zero-clipping-epsilon* physical mesh section witness.

    The public CHECK sampler has a numerical clipping tolerance and may
    omit tiny, valid physical segments. Do NOT use an overestimated sampled
    gap as a rigorous lower bound. Reuse its SAME triangle-plane section
    owner at zero geometric clipping epsilon for this bound's anchor.
    If this and the existing CHECK witness differ beyond shared numerical
    uncertainty, the conservative bound remains UNKNOWN (never fake zero).
    """
    reference = (0.0, 0.0, 1.0) if abs(direction[2]) < 0.9 else (1.0, 0.0, 0.0)
    u = _unit(_cross(direction, reference))
    v = _unit(_cross(direction, u))
    origin = tuple(start[i] + direction[i] * station_mm for i in range(3))
    a = _section_segments(first, origin, direction, u, v, 0.0)
    b = _section_segments(second, origin, direction, u, v, 0.0)
    if not a or not b:
        return None
    ga = LineString(a[0]) if len(a) == 1 else MultiLineString(a)
    gb = LineString(b[0]) if len(b) == 1 else MultiLineString(b)
    pa, pb = nearest_points(ga, gb)
    gap = float(pa.distance(pb))
    if not math.isfinite(gap) or gap < 0:
        raise GeometryError("V-miter exact cut-face section gap is invalid")
    return gap


def _conservative_open_interval_gap_bounds(
    first, second, start, direction, lo_mm, hi_mm,
    section: VMiterSeamSectionGap, tolerance: float, *,
    unresolved_events: int,
):
    """Proof envelope for continuous world triangle-mesh section distance.

    For d(s) = minimum distance between two genuine cut-face section sets:
    |d(s)-d(mid)| <= (L_first + L_second) * |s-mid|,
    because both triangle-section unions are Hausdorff-Lipschitz within
    this vertex-event-free open interval. Bounds are widened by Engine's
    existing NUMERICAL tolerance (not an acceptable manufacturing gap).
    Values are NOT exact extrema, nor bounds for springback, kerf or tools.
    """
    width = hi_mm - lo_mm
    if section.status != "MEASURED":
        return None, "MISSING_PHYSICAL_CUT_FACE"
    if unresolved_events or width <= 4.0 * tolerance:
        return None, "NUMERICALLY_UNRESOLVED_VERTEX_EVENT"
    speed1 = _section_transverse_speed_bound(first, start, direction, lo_mm, hi_mm)
    speed2 = _section_transverse_speed_bound(second, start, direction, lo_mm, hi_mm)
    if speed1 is None or speed2 is None:
        return None, "MISSING_PHYSICAL_CUT_FACE"
    exact = _midpoint_exact_cut_face_gap(
        first, second, start, direction, (lo_mm + hi_mm) * 0.5,
    )
    if exact is None or section.measured_gap_mm is None:
        return None, "NUMERICALLY_UNRESOLVED_SECTION"
    # Rejected numerical mismatch must not be converted to a fictitious
    # factory tolerance or a falsely precise gap upper/lower certificate.
    margin = max(1e-9, 10 * tolerance)
    if abs(exact - section.measured_gap_mm) > margin:
        return None, "NUMERICALLY_UNRESOLVED_SECTION"
    speed = speed1 + speed2
    variation = speed * width * 0.5
    if not math.isfinite(variation):
        return None, "NUMERICALLY_UNRESOLVED_SECTION"
    bbox_cap = _perpendicular_cut_face_bbox_gap_cap(
        first, second, start, direction, lo_mm, hi_mm,
    )
    if bbox_cap is None:
        return None, "NUMERICALLY_UNRESOLVED_SECTION"
    # BOTH bounds hold for the same actual physical triangle section sets.
    # Taking the smaller remains conservative; no welding fit tolerance
    # or false exact extrema is introduced.
    return (
        (
            max(0.0, exact - margin),              # sup gap >= actual midpoint
            min(exact + variation, bbox_cap) + margin, # sup gap <= both caps
            max(0.0, exact - variation - margin), # inf gap >= speed envelope
            exact + margin,                        # inf gap <= midpoint
            speed,
            bbox_cap,
        ),
        "CONSERVATIVE_SOURCE_MESH_ENVELOPE_CHECK",
    )


def project_v_miter_true_cut_face_continuity_trial(
    first_source_cut_face_triangles,
    second_source_cut_face_triangles,
    *,
    formed_seam_start,
    formed_seam_end,
) -> VMiterCutFaceContinuityTrial:
    """Inspect all *open* source-face projection intervals in true world 3D.

    Caller MUST pass the previously verified 2D-CUTTING-tagged true T-thick
    sidewalls from the current R/BA solver. Empty/malformed cut-face meshes
    must fail closed; no original-stock or whole-solid fallback is allowed.
    The section solver computes actual nearest-world-XYZ and datum evidence
    for each open interval's midpoint. A geometric vertex event is only an
    interval boundary, not a promise of pointwise contact at that event.
    """
    first = _mesh(first_source_cut_face_triangles, "first V-cut face")
    second = _mesh(second_source_cut_face_triangles, "second V-cut face")
    start = _point(formed_seam_start, "V-cut seam start")
    end = _point(formed_seam_end, "V-cut seam end")
    axis = _sub(end, start)
    length = math.sqrt(_dot(axis, axis))
    direction = _unit(axis)
    tol = float(
        PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance
    )
    if not math.isfinite(tol) or tol <= 0 or length <= tol:
        raise GeometryError("V-miter cut-face interval seam/numerical tolerance invalid")

    fractions = [0.0, 1.0]
    for triangle in first + second:
        for vertex in triangle:
            fraction = _dot(_sub(vertex, start), direction) / length
            if not math.isfinite(fraction):
                raise GeometryError("V-miter cut-face has non-finite projected seam station")
            if 0.0 < fraction < 1.0:
                fractions.append(fraction)
    fractions.sort()
    # Distinct projected vertices which lie closer than the ENGINE numerical
    # tolerance are not arbitrarily resolved as separate physical spans.
    # Record the ambiguity rather than claiming geometry-continuity proof.
    station_tol = tol / length
    stations = [fractions[0]]
    unresolved = 0
    for fraction in fractions[1:]:
        if fraction - stations[-1] <= station_tol:
            if fraction != stations[-1]:
                unresolved += 1
            continue
        stations.append(fraction)
    if stations[-1] != 1.0:
        # A floating-point cluster near endpoint is not permission to omit
        # a real final seam interval: preserve the exact source endpoint.
        if 1.0 - stations[-1] <= station_tol:
            unresolved += 1
            stations[-1] = 1.0
        else:
            stations.append(1.0)
    if len(stations) < 2 or len(stations) - 1 > _MAX_OPEN_INTERVALS:
        raise GeometryError("V-miter cut-face source topology exceeds safe interval budget")
    midpoints = []
    for lo, hi in zip(stations, stations[1:]):
        mid = (lo + hi) * 0.5
        if not lo < mid < hi:
            raise GeometryError("V-miter cut-face open interval is numerically unresolved")
        midpoints.append(mid)

    checked = project_v_miter_true_t_seam_section_gap_trial(
        first, second,
        formed_seam_start=start, formed_seam_end=end,
        station_fractions=tuple(midpoints),
    )
    if len(checked.sections) != len(midpoints):
        raise GeometryError("V-miter cut-face interval sample count disagrees with source")
    spans = []
    lengths = {"MEASURED": 0.0, "FIRST_MISSING": 0.0,
               "SECOND_MISSING": 0.0, "BOTH_MISSING": 0.0}
    for lo, hi, section in zip(stations, stations[1:], checked.sections):
        span_length = length * (hi - lo)
        if span_length <= 0 or section.status not in lengths:
            raise GeometryError("V-miter cut-face source interval is invalid")
        lengths[section.status] += span_length
        bounds, bound_status = _conservative_open_interval_gap_bounds(
            first, second, start, direction,
            lo * length, hi * length, section, tol,
            unresolved_events=unresolved,
        )
        spans.append(VMiterCutFaceOpenIntervalTrial(
            start_fraction=lo, end_fraction=hi,
            start_mm=lo * length, end_mm=hi * length,
            length_mm=span_length, midpoint_section=section,
            max_gap_lower_bound_mm=bounds[0] if bounds else None,
            max_gap_upper_bound_mm=bounds[1] if bounds else None,
            min_gap_lower_bound_mm=bounds[2] if bounds else None,
            min_gap_upper_bound_mm=bounds[3] if bounds else None,
            combined_transverse_speed=bounds[4] if bounds else None,
            transverse_bounding_box_cap_mm=bounds[5] if bounds else None,
            gap_bound_status=bound_status,
        ))
    if abs(sum(lengths.values()) - length) > max(1e-6, tol * 10):
        raise GeometryError("V-miter cut-face interval source seam coverage does not balance")
    measured = tuple(
        p.midpoint_section for p in spans
        if p.midpoint_section.status == "MEASURED"
    )
    datum = tuple(p.datum_anchored_gap_mm for p in measured)
    gaps = tuple(p.measured_gap_mm for p in measured)
    missing = len(spans) - len(measured)
    has_complete_bounds = (
        not missing and not unresolved
        and all(
            p.gap_bound_status == "CONSERVATIVE_SOURCE_MESH_ENVELOPE_CHECK"
            for p in spans
        )
    )
    # A global finite-seam envelope is NOT valid if even one span lacks
    # physically identified mating faces or its numerical evidence failed.
    return VMiterCutFaceContinuityTrial(
        seam_length_mm=length,
        intervals=tuple(spans),
        both_face_interval_count=len(measured),
        missing_face_interval_count=missing,
        both_face_span_mm=lengths["MEASURED"],
        first_missing_span_mm=lengths["FIRST_MISSING"],
        second_missing_span_mm=lengths["SECOND_MISSING"],
        both_missing_span_mm=lengths["BOTH_MISSING"],
        min_sampled_cut_face_gap_mm=min(gaps) if gaps else None,
        max_sampled_cut_face_gap_mm=max(gaps) if gaps else None,
        min_sampled_datum_gap_mm=min(datum) if datum else None,
        max_sampled_datum_gap_mm=max(datum) if datum else None,
        numerically_unresolved_vertex_event_count=unresolved,
        coverage_status=(
            "FACE_COVERAGE_INCOMPLETE"
            if missing or unresolved else "FACE_COVERAGE_SAMPLED_ONLY"
        ),
        max_gap_lower_bound_mm=(
            max(p.max_gap_lower_bound_mm for p in spans)
            if has_complete_bounds else None
        ),
        max_gap_upper_bound_mm=(
            max(p.max_gap_upper_bound_mm for p in spans)
            if has_complete_bounds else None
        ),
        min_gap_lower_bound_mm=(
            min(p.min_gap_lower_bound_mm for p in spans)
            if has_complete_bounds else None
        ),
        min_gap_upper_bound_mm=(
            min(p.min_gap_upper_bound_mm for p in spans)
            if has_complete_bounds else None
        ),
        gap_bound_status=(
            "CONSERVATIVE_SOURCE_MESH_ENVELOPE_CHECK"
            if has_complete_bounds else "UNRESOLVED_OR_PARTIAL_SOURCE_COVERAGE"
        ),
    )
