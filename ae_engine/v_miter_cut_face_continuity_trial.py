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

from .contracts import PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES
from .sheetmetal_geometry_core import GeometryError
from .v_miter_seam_gap_trial import (
    VMiterSeamSectionGap,
    _dot, _mesh, _point, _sub, _unit,
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
    geometry_model: str = "SOURCE_TRUE_T_V_CUT_FACE_OPEN_INTERVAL_TOPOLOGY_CHECK"
    manufacturing_status: str = "V_MITER_CUT_FACE_CONTINUITY_UNCERTIFIED"


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
        spans.append(VMiterCutFaceOpenIntervalTrial(
            start_fraction=lo, end_fraction=hi,
            start_mm=lo * length, end_mm=hi * length,
            length_mm=span_length, midpoint_section=section,
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
    )
