# -*- coding: utf-8 -*-
"""#3317 sampled real T-thickness seam-section gap evidence, CHECK-only.

A zero noncoplanar triangle-crossing result is NOT a proof that two folded
flanges mate. Section *both actual true-thickness surfaces* on planes normal
to the source-derived ideal common contact ray; measure nearest physical
surface intersections at deterministic interior stations. Missing sections
are UNKNOWN (never zero gap). The values do not encode a factory gap limit,
bevel tolerance, welding fit or permission to issue production CUTTING.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import nearest_points

from .sheetmetal_geometry_core import GeometryError


Vec3 = tuple[float, float, float]
_STATIONS = (0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875)


@dataclass(frozen=True)
class VMiterSeamSectionGap:
    """One section through the *true T-solid* at a source seam station."""

    fraction: float
    station_mm: float
    section_origin_xyz: Vec3
    first_section_segment_count: int
    second_section_segment_count: int
    measured_gap_mm: float | None
    nearest_first_xyz: Vec3 | None
    nearest_second_xyz: Vec3 | None
    status: str  # MEASURED | FIRST_MISSING | SECOND_MISSING | BOTH_MISSING
    # The global nearest surface pair may be on unrelated remote stock.
    # Independent closest points to the ideal seam datum are only source-
    # anchored witnesses, NOT certified V-cut mating-face semantics.
    datum_anchored_gap_mm: float | None = None
    datum_first_xyz: Vec3 | None = None
    datum_second_xyz: Vec3 | None = None
    datum_first_reach_mm: float | None = None
    datum_second_reach_mm: float | None = None
    global_first_reach_mm: float | None = None
    global_second_reach_mm: float | None = None
    off_datum_shortcut: bool = False


@dataclass(frozen=True)
class VMiterSeamSectionGapTrial:
    """Observed physical section gaps, never a certified full seam or fit."""

    seam_length_mm: float
    sections: tuple[VMiterSeamSectionGap, ...]
    measured_section_count: int
    missing_section_count: int
    min_measured_gap_mm: float | None
    max_measured_gap_mm: float | None
    off_datum_shortcut_station_count: int = 0
    min_datum_anchored_gap_mm: float | None = None
    max_datum_anchored_gap_mm: float | None = None
    geometry_model: str = "TRUE_T_FOLDED_SECTION_NEAREST_SURFACE_SAMPLED_CHECK"
    manufacturing_status: str = "V_MITER_SEAM_GAP_UNCERTIFIED"


def _dot(a: Vec3, b: Vec3) -> float:
    return sum(a[i] * b[i] for i in range(3))


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return tuple(a[i] - b[i] for i in range(3))


def _add(a: Vec3, b: Vec3) -> Vec3:
    return tuple(a[i] + b[i] for i in range(3))


def _mul(a: Vec3, k: float) -> Vec3:
    return tuple(a[i] * k for i in range(3))


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _unit(a: Vec3) -> Vec3:
    length = math.sqrt(_dot(a, a))
    if not math.isfinite(length) or length <= 1e-12:
        raise GeometryError("V-miter seam-section direction must be nonzero and finite")
    return _mul(a, 1.0 / length)


def _point(a: object, name: str) -> Vec3:
    try:
        p = tuple(a)
        if len(p) != 3 or any(isinstance(x, bool) for x in p):
            raise ValueError("not a finite XYZ")
        result = tuple(float(x) for x in p)
    except (TypeError, ValueError, OverflowError):
        raise GeometryError(f"V-miter seam-section {name} needs finite XYZ") from None
    if not all(math.isfinite(v) for v in result):
        raise GeometryError(f"V-miter seam-section {name} needs finite XYZ")
    return result


def _mesh(triangles: object, name: str) -> tuple[tuple[Vec3, Vec3, Vec3], ...]:
    try:
        rows = tuple(triangles)
    except (TypeError, ValueError):
        raise GeometryError(f"V-miter seam-section {name} needs triangles") from None
    if not rows:
        raise GeometryError(f"V-miter seam-section {name} is empty")
    result = []
    for row in rows:
        try:
            points = tuple(row)
        except (TypeError, ValueError):
            raise GeometryError(f"V-miter seam-section {name} triangle is invalid") from None
        if len(points) != 3:
            raise GeometryError(f"V-miter seam-section {name} triangle needs three vertices")
        result.append(tuple(_point(p, name + " triangle") for p in points))
    return tuple(result)


def _section_segments(mesh, origin: Vec3, normal: Vec3, u: Vec3, v: Vec3, tol: float):
    """Intersect each real 3D solid-surface triangle with one physical plane.

    Coplanar faces contribute their real edges (not fictitious zero-distance
    contacts); zero-dimensional vertex touches provide no measurable section.
    This is a section of the existing 3D solid, never a new fold formula.
    """
    segments = []

    def uv(p):
        delta = _sub(p, origin)
        return (_dot(delta, u), _dot(delta, v))

    def add_segment(a, b):
        a2, b2 = uv(a), uv(b)
        if math.hypot(a2[0] - b2[0], a2[1] - b2[1]) > tol:
            segments.append((a2, b2))

    for tri in mesh:
        ds = tuple(_dot(_sub(p, origin), normal) for p in tri)
        if all(d > tol for d in ds) or all(d < -tol for d in ds):
            continue
        if all(abs(d) <= tol for d in ds):
            for i in range(3):
                add_segment(tri[i], tri[(i + 1) % 3])
            continue
        points = []
        for i in range(3):
            j = (i + 1) % 3
            da, db = ds[i], ds[j]
            a, b = tri[i], tri[j]
            if abs(da) <= tol and abs(db) <= tol:
                add_segment(a, b)
                continue
            if abs(da) <= tol:
                points.append(a)
            elif abs(db) <= tol:
                points.append(b)
            elif da * db < 0:
                t = da / (da - db)
                points.append(_add(a, _mul(_sub(b, a), t)))
        unique = []
        for p in points:
            if all(math.sqrt(_dot(_sub(p, q), _sub(p, q))) > tol for q in unique):
                unique.append(p)
        if len(unique) >= 2:
            a, b = max(
                ((a, b) for i, a in enumerate(unique) for b in unique[i + 1:]),
                key=lambda pair: _dot(_sub(pair[0], pair[1]), _sub(pair[0], pair[1])),
            )
            add_segment(a, b)
    return tuple(segments)


def project_v_miter_true_t_seam_section_gap_trial(
    first_thick_solid_triangles,
    second_thick_solid_triangles,
    *,
    formed_seam_start,
    formed_seam_end,
    station_fractions: tuple[float, ...] | None = None,
) -> VMiterSeamSectionGapTrial:
    """Sample actual solid-to-solid gap normal to the *ideal* finite 3D seam.

    Only section samples with material from BOTH flanges have a distance.
    The seam axis is the existing canonical source-backed ideal witness,
    NOT a derived answer from a current (possibly wrong) trim or a factory
    seam-gapping standard. In addition to the global nearest surface pair,
    measure each solid's independent nearest source seam datum point in
    the SAME true-3D section. Remote touching can yield global gap=0 while
    the two datum witnesses remain separated. Neither zero datum gap nor
    near-datum points identify certified V-cut mating-face semantics.
    """
    from .contracts import PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES

    first = _mesh(first_thick_solid_triangles, "first solid")
    second = _mesh(second_thick_solid_triangles, "second solid")
    start = _point(formed_seam_start, "start")
    end = _point(formed_seam_end, "end")
    direction = _sub(end, start)
    length = math.sqrt(_dot(direction, direction))
    n = _unit(direction)
    reference = (0.0, 0.0, 1.0) if abs(n[2]) < 0.9 else (1.0, 0.0, 0.0)
    u = _unit(_cross(n, reference))
    v = _unit(_cross(n, u))
    # Existing shared numerical geometry tolerance, NOT an allowed factory
    # seam gap or tool/kerf assumption.
    tol = float(PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance)
    if not math.isfinite(tol) or tol <= 0:
        raise GeometryError("V-miter seam-section numerical tolerance invalid")

    # Legacy public CHECK keeps its original seven physical sample stations.
    # The source-cut-face topology assessor may instead provide its exact
    # mesh-derived open-interval midpoints; no invented factory gap spacing.
    fractions = _STATIONS if station_fractions is None else station_fractions
    if not isinstance(fractions, (tuple, list)) or not fractions or len(fractions) > 4096:
        raise GeometryError("V-miter seam-section stations must be a finite bounded sequence")
    previous = -1.0
    for value in fractions:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not (0.0 < float(value) < 1.0)
            or float(value) <= previous
        ):
            raise GeometryError("V-miter seam-section stations must be strictly increasing inside seam")
        previous = float(value)

    sections = []
    for fraction in fractions:
        origin = _add(start, _mul(direction, fraction))
        a = _section_segments(first, origin, n, u, v, tol)
        b = _section_segments(second, origin, n, u, v, tol)
        status = (
            "MEASURED" if a and b else
            "FIRST_MISSING" if not a and b else
            "SECOND_MISSING" if a and not b else
            "BOTH_MISSING"
        )
        gap = None
        first_xyz = None
        second_xyz = None
        datum_gap = None
        datum_first_xyz = None
        datum_second_xyz = None
        datum_first_reach = None
        datum_second_reach = None
        global_first_reach = None
        global_second_reach = None
        off_datum = False
        if a and b:
            ga = LineString(a[0]) if len(a) == 1 else MultiLineString(a)
            gb = LineString(b[0]) if len(b) == 1 else MultiLineString(b)
            pa, pb = nearest_points(ga, gb)
            gap = float(pa.distance(pb))
            if not math.isfinite(gap) or gap < 0:
                raise GeometryError("V-miter seam-section nearest surface gap invalid")

            def world(point):
                return _add(
                    origin, _add(_mul(u, float(point.x)), _mul(v, float(point.y))),
                )

            first_xyz, second_xyz = world(pa), world(pb)
            if abs(math.sqrt(_dot(_sub(first_xyz, second_xyz), _sub(first_xyz, second_xyz))) - gap) > max(1e-6, tol * 10):
                raise GeometryError("V-miter seam-section XY and 3D witness disagree")

            # The actual source-backed ideal seam projects to (0,0) on
            # this section. Its two closest real solid-surface points are
            # picked independently, BEFORE comparing the two solids.
            datum = Point(0.0, 0.0)
            datum_first = nearest_points(datum, ga)[1]
            datum_second = nearest_points(datum, gb)[1]
            datum_first_reach = float(datum.distance(datum_first))
            datum_second_reach = float(datum.distance(datum_second))
            global_first_reach = float(datum.distance(pa))
            global_second_reach = float(datum.distance(pb))
            datum_gap = float(datum_first.distance(datum_second))
            datum_first_xyz, datum_second_xyz = (
                world(datum_first), world(datum_second),
            )
            if any(not math.isfinite(value) or value < 0 for value in (
                datum_gap, datum_first_reach, datum_second_reach,
                global_first_reach, global_second_reach,
            )):
                raise GeometryError("V-miter seam-section datum gap/reach is invalid")
            if abs(math.dist(datum_first_xyz, datum_second_xyz) - datum_gap) > max(1e-6, tol * 10):
                raise GeometryError("V-miter seam-section datum XY and 3D witness disagree")
            # A discrepancy between TWO real distances is not a factory
            # gap threshold. A shortcut is flagged only when BOTH global
            # witnesses are physically farther from the seam datum than
            # their independently nearest material point. Otherwise a
            # legitimate near-datum face may explain a different pair gap.
            off_datum = (
                datum_gap > gap + tol
                and global_first_reach > datum_first_reach + tol
                and global_second_reach > datum_second_reach + tol
            )
        sections.append(VMiterSeamSectionGap(
            fraction=fraction, station_mm=length * fraction,
            section_origin_xyz=origin,
            first_section_segment_count=len(a),
            second_section_segment_count=len(b),
            measured_gap_mm=gap,
            nearest_first_xyz=first_xyz,
            nearest_second_xyz=second_xyz,
            status=status,
            datum_anchored_gap_mm=datum_gap,
            datum_first_xyz=datum_first_xyz,
            datum_second_xyz=datum_second_xyz,
            datum_first_reach_mm=datum_first_reach,
            datum_second_reach_mm=datum_second_reach,
            global_first_reach_mm=global_first_reach,
            global_second_reach_mm=global_second_reach,
            off_datum_shortcut=off_datum,
        ))
    distances = tuple(x.measured_gap_mm for x in sections if x.measured_gap_mm is not None)
    datum_distances = tuple(
        x.datum_anchored_gap_mm for x in sections
        if x.datum_anchored_gap_mm is not None
    )
    return VMiterSeamSectionGapTrial(
        seam_length_mm=length, sections=tuple(sections),
        measured_section_count=len(distances),
        missing_section_count=len(sections) - len(distances),
        min_measured_gap_mm=min(distances) if distances else None,
        max_measured_gap_mm=max(distances) if distances else None,
        off_datum_shortcut_station_count=sum(
            1 for x in sections if x.off_datum_shortcut
        ),
        min_datum_anchored_gap_mm=min(datum_distances) if datum_distances else None,
        max_datum_anchored_gap_mm=max(datum_distances) if datum_distances else None,
    )
