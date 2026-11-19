# -*- coding: utf-8 -*-
"""#3317 calibrated bend-radius/allowance V-interface *trial*, not manufacture.

A real sheet does not fold about an infinitely sharp centre line.  On each
source BEND, its supplied inside R and independently supplied bend allowance
determine a cylindrical neutral-axis development.  Use those measurements to
fold actual source-clipped flange triangles (not a GUI cut), then search for
a one-sided flat V-edge trim that removes detected non-coplanar T-thick
surface crossings.  The other, possibly taller flange is NEVER shortened.

This is an engineering CHECK/shadow only. A zero mesh crossing count does
not prove absence of coplanar/interior penetration or a proper closed single
sheet CUTTING contour; a one-sided square edge is not a certified bevel.
Kerf, machine relief R/diameter ratio, actual bend tooling/springback,
assembly and factory dimensional acceptance are still required. No CUTTING,
BEND, MARKING, CornerType or Registry is changed by this API.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import LineString, Point, Polygon

from .assembly_geometry import (
    detect_world_mesh_surface_interference,
    detect_world_mesh_enclosed_volume_witness,
    diagnose_world_mesh_triangle_edge_incidence,
)
from .assembly_geometry_primitives import thicken_triangle_surface
from .sheetmetal_drawing import DrawingScene, LinePrimitive
from .sheetmetal_geometry_core import GeometryError, Vec2
from .v_miter_corner_source import VMiterReliefMode, _finite
from .v_miter_ideal_mating import _UNIT_Z, _add, _dot, _outside_normal, _outward_bend_axis, _scale
from .v_miter_true_t_collision import _flange_footprint, _source_triangulation
from .v_miter_relief_trial import (
    project_v_miter_relief_mating_trial, _rounded_v_notch_polygon,
)
from .v_miter_material_trial import _short_outer_arc, _single_source_material
from .v_miter_bounded_contact import diagnose_v_miter_bounded_bend_reach
from .v_miter_seam_gap_trial import (
    VMiterSeamSectionGapTrial,
    project_v_miter_true_t_seam_section_gap_trial,
)
from .v_miter_source_cut_face_trial import (
    VMiterSourceCutFaceTrial,
    trace_v_miter_source_true_t_cut_faces,
)
from .v_miter_cut_face_continuity_trial import (
    VMiterCutFaceContinuityTrial,
    project_v_miter_true_cut_face_continuity_trial,
)

_EPS = 1e-7
_ARC_SEGMENTS = 16
_BINARY_STEPS = 12


@dataclass(frozen=True)
class VMiterRadiusCompensatedInterfaceTrial:
    """Uncertified source-backed R/BA/T shadow after a bounded V-edge trim."""

    first_inner_radius_mm: float
    second_inner_radius_mm: float
    first_bend_allowance_mm: float
    second_bend_allowance_mm: float
    first_neutral_axis_k: float
    second_neutral_axis_k: float
    first_edge_trim_mm: float
    max_permitted_edge_trim_mm: float
    untrimmed_surface_interference_pairs: int
    trimmed_surface_interference_pairs: int
    first_flat_source_area_mm2: float
    first_flat_source_outline: tuple[Vec2, ...]
    full_source_remaining_outline: tuple[Vec2, ...]
    first_flat_trimmed_area_mm2: float
    second_flat_source_area_mm2: float
    first_trimmed_check_outline: tuple[Vec2, ...]
    first_formed_skin_triangles: tuple
    second_formed_skin_triangles: tuple
    first_thick_solid_triangles: tuple
    second_thick_solid_triangles: tuple
    untrimmed_enclosed_volume_witness_count: int = 0
    trimmed_enclosed_volume_witness_count: int = 0
    formed_volume_containment_meshes_closed: bool = False
    first_thick_solid_boundary_edge_count: int = 0
    second_thick_solid_boundary_edge_count: int = 0
    first_thick_solid_nonmanifold_edge_count: int = 0
    second_thick_solid_nonmanifold_edge_count: int = 0
    first_thick_solid_degenerate_triangle_count: int = 0
    second_thick_solid_degenerate_triangle_count: int = 0
    first_thick_solid_boundary_edge_examples_xyz: tuple = ()
    second_thick_solid_boundary_edge_examples_xyz: tuple = ()
    true_t_volume_check_status: str = "V_MITER_TRUE_T_VOLUME_UNKNOWN_NOT_EVALUATED"
    first_edge_transition_span_mm: float = 0.0
    full_corrected_check_outline: tuple[Vec2, ...] = ()
    seam_section_gap_trial: VMiterSeamSectionGapTrial | None = None
    first_source_cut_face: VMiterSourceCutFaceTrial | None = None
    second_source_cut_face: VMiterSourceCutFaceTrial | None = None
    source_cut_face_section_gap_trial: VMiterSeamSectionGapTrial | None = None
    source_cut_face_continuity_trial: VMiterCutFaceContinuityTrial | None = None
    geometry_model: str = "SOURCE_R_BA_CYLINDRICAL_FOLD_ONE_SIDED_V_TRIM_TRIAL"
    manufacturing_status: str = "V_MITER_RADIUS_BA_INTERFACE_UNCERTIFIED"

    @property
    def no_detected_noncoplanar_crossings(self) -> bool:
        """Diagnostics ONLY: not a solid-volume or production clearance proof."""
        return self.trimmed_surface_interference_pairs == 0


class VMiterRadiusBAContactError(GeometryError):
    """Source-backed rejection evidence from the existing 3D surface detector.

    Segments are non-coplanar intersections, NOT a complete volumetric
    penetration, mating tolerance or certified toolpath result.
    """

    def __init__(
        self, message: str, *, original_pairs: int, attempted_pairs: int,
        attempted_segments: tuple, attempted_trim_mm: float,
        attempted_containment_points: tuple = (),
    ):
        super().__init__(message)
        self.original_noncoplanar_pairs = original_pairs
        self.attempted_noncoplanar_pairs = attempted_pairs
        self.attempted_intersection_segments = tuple(attempted_segments)
        self.attempted_trim_mm = attempted_trim_mm
        self.attempted_containment_points = tuple(attempted_containment_points)
        self.manufacturing_status = "V_MITER_RADIUS_BA_INTERFACE_UNCERTIFIED"


def _bend_measurement(radius: object, allowance: object, angle: float, t: float, name: str):
    """Check explicit R/BA agree with a possible neutral-axis location.

    BA = angle_rad * (inner_R + K*T). Neither K nor BA is silently
    invented from common generic bend tables. A measured BA outside the
    sheet thickness cannot represent this cylindrical bending model.
    """
    r = _finite(radius, name + "_inner_radius_mm", positive=True)
    ba = _finite(allowance, name + "_bend_allowance_mm", positive=True)
    neutral_r = ba / angle
    k = (neutral_r - r) / t
    if not math.isfinite(k) or k < -1e-8 or k > 1 + 1e-8:
        raise GeometryError("V-miter measured bend allowance is inconsistent with inside R/T")
    return r, ba, max(0.0, min(1.0, k))


def _flat_point(apex: Vec2, axis, outside, along: float, height: float):
    return (apex.x + axis[0] * along + outside[0] * height,
            apex.y + axis[1] * along + outside[1] * height)


def _formed_curved_skin(
    patch: Polygon, apex: Vec2, axis, outside, *,
    angle_rad: float, inner_r: float, allowance: float, thickness: float,
    axial_span: float, flange_height: float,
    return_flat_pairs: bool = False,
):
    """Develop flat neutral-axis u into a cylindrical mid-surface in 3D.

    Source BEND is the neutral-axis arc start.  Divide each source polygon
    at exact material u-stations before triangulation; merely bending the
    polygon's original vertices would turn the arc back into one sharp fold.
    """
    if allowance >= flange_height - _EPS:
        raise GeometryError("V-miter bend allowance consumes the source flange height")
    stations = [allowance * i / _ARC_SEGMENTS for i in range(_ARC_SEGMENTS + 1)]
    stations.append(flange_height)
    mid_r = inner_r + thickness / 2.0
    neutral_r = allowance / angle_rad
    result, flat_pairs, planar_area = [], [], 0.0
    for lo, hi in zip(stations, stations[1:]):
        if hi - lo <= _EPS:
            raise GeometryError("V-miter curved bend strip is degenerate")
        # The true source is already clipped to 0..span. The extra margin
        # affects only the temporary clipping domain, not source material.
        domain = Polygon((
            _flat_point(apex, axis, outside, -1, lo),
            _flat_point(apex, axis, outside, axial_span + 1, lo),
            _flat_point(apex, axis, outside, axial_span + 1, hi),
            _flat_point(apex, axis, outside, -1, hi),
        ))
        pieces = patch.intersection(domain)
        candidates = (pieces,) if pieces.geom_type == "Polygon" else tuple(
            part for part in getattr(pieces, "geoms", ())
            if part.geom_type == "Polygon"
        )
        for piece in candidates:
            if piece.area <= _EPS:
                continue
            if not piece.is_valid or piece.interiors:
                raise GeometryError("V-miter radius trial has invalid clipped material")
            planar_area += piece.area
            for triangle in _source_triangulation(piece):
                formed = []
                for x, y in triangle:
                    delta = (x - apex.x, y - apex.y, 0.0)
                    axial = _dot(delta, axis)
                    u = _dot(delta, outside)
                    # u is the physical flat (neutral-axis) material distance.
                    if u < -1e-6 or u > flange_height + 1e-6:
                        raise GeometryError("V-miter R/BA source material leaves its flange domain")
                    arc_u = max(0.0, min(allowance, u))
                    phi = arc_u / neutral_r
                    linear = max(0.0, u - allowance)
                    out = mid_r * math.sin(phi) + linear * math.cos(angle_rad)
                    z = mid_r * (1.0 - math.cos(phi)) + linear * math.sin(angle_rad)
                    formed.append((
                        apex.x + axis[0] * axial + outside[0] * out,
                        apex.y + axis[1] * axial + outside[1] * out,
                        z,
                    ))
                if not all(math.isfinite(v) for point in formed for v in point):
                    raise GeometryError("V-miter physical curved skin contains non-finite geometry")
                result.append(tuple(formed))
                if return_flat_pairs:
                    flat_pairs.append(tuple((float(x), float(y)) for x, y in triangle))
    if not result or abs(planar_area - patch.area) > max(1e-5, patch.area * 1e-6):
        raise GeometryError("V-miter R/BA surface loses original source material")
    return (tuple(result), tuple(flat_pairs)) if return_flat_pairs else tuple(result)


def _trim_one_v_edge(
    patch: Polygon, apex: Vec2, tip: Vec2, amount: float,
    *, relief_open_length_mm: float,
    transition_run_mm: float | None = None,
):
    """Keep the physical R/hole root while progressively offsetting one V edge.

    A single parallel *infinite* offset clipped the tip even within its
    source-qualified open relief. That disconnected the ROUND_R source sheet
    when the local flange delta was backprojected into the one-piece CUTTING
    source. Start the offset at the original relief's actual *flat* cutback,
    then transition from zero to the requested offset. The original
    diagnostic uses a one-to-one offset/run in unfolded material space;
    a source-R-scaled alternate is separately checked when the original
    rounded tip fails. Neither is a certified factory bevel policy.

    Coordinates s are along the ORIGINAL ideal V ray from its true apex,
    n are towards actual flange material, rather than GUI XY quadrants.
    Preserve every source point with s <= source relief contact start.
    """
    dx, dy = tip.x - apex.x, tip.y - apex.y
    length = math.hypot(dx, dy)
    if not math.isfinite(length) or length <= _EPS:
        raise GeometryError("V-miter V trim ray is degenerate")
    cutback = _finite(relief_open_length_mm, "relief_open_length_mm", positive=True)
    if cutback >= length - _EPS:
        raise GeometryError("V-miter relief cutback exhausts the source V ray")
    offset = _finite(amount, "first_edge_trim_mm")
    if offset < 0:
        raise GeometryError("V-miter relief edge trim must not be negative")
    if offset == 0:
        return patch
    run = offset if transition_run_mm is None else _finite(
        transition_run_mm, "transition_run_mm", positive=True,
    )
    if run > offset + _EPS:
        raise GeometryError("V-miter transition run cannot exceed trial edge offset")
    ux, uy = dx / length, dy / length
    interior = patch.representative_point()
    signed = ux * (interior.y - apex.y) - uy * (interior.x - apex.x)
    if abs(signed) <= _EPS:
        raise GeometryError("V-miter V edge has no demonstrable source material side")
    side = 1 if signed > 0 else -1
    nx, ny = -uy * side, ux * side
    # Reach covers every physical source vertex along both local axes, plus
    # contact-start and offset. The domain does not add material: intersection
    # with patch is always a strict subset of its original source.
    reach = max(10.0, length, cutback, offset,
                *(math.hypot(x - apex.x, y - apex.y)
                  for x, y in patch.exterior.coords)) * 4 + 10
    def point(s: float, n: float) -> tuple[float, float]:
        return (apex.x + ux * s + nx * n,
                apex.y + uy * s + ny * n)

    # Material-side polygon with zero additional trim throughout original
    # open R/hole region, followed by a source-bound trial transition
    # to the uniform V-edge correction. The legacy run equals the offset;
    # the alternate R-tip trial run is capped by the actual rounded-source
    # cutback. Neither creates a factory bevel rule or acceptance gap.
    # No disconnected near-tip island is reattached or replaced.
    cut_domain = Polygon((
        point(-reach, -reach),
        point(cutback, -reach),
        point(cutback, 0.0),
        point(cutback + run, offset),
        point(reach, offset),
        point(reach, reach),
        point(-reach, reach),
    ))
    if not cut_domain.is_valid:
        raise GeometryError("V-miter physical tip-preserving trim domain is invalid")
    clipped = patch.intersection(cut_domain)
    if (clipped.geom_type != "Polygon" or clipped.is_empty or
            not clipped.is_valid or clipped.interiors or clipped.area <= _EPS):
        raise GeometryError("V-miter trial trim destroys the single source flange patch")
    if clipped.difference(patch).area > _EPS:
        raise GeometryError("V-miter trial trim invents stock")
    return clipped


def _checked_full_source_from_trim(
    source: Polygon, first_source: Polygon, first_corrected: Polygon,
    unchanged_second: Polygon,
) -> tuple[Polygon, Polygon]:
    """Enforce one real sheet BEFORE exposing a locally collision-free trial.

    A local 3D flange may show zero noncoplanar crossings only because the
    clipping removed a separate island or altered the other physical flange.
    Its *whole source sheet* must remain one closed material polygon. Apply
    the exact local removed delta to the original V-relieved sheet; never
    replace an interior island by convex hull/buffer(0)/largest component.
    Both public local solver and CHECK-only whole-sheet projector consume
    this one Engine gate, without authorising manufacturing.
    """
    for label, polygon in (
        ("original full sheet", source),
        ("original first flange", first_source),
        ("corrected first flange", first_corrected),
        ("unchanged second flange", unchanged_second),
    ):
        if (polygon.geom_type != "Polygon" or polygon.is_empty or
                not polygon.is_valid or polygon.interiors or
                polygon.area <= _EPS):
            raise GeometryError(f"V-miter {label} is not single valid material")
    tolerance = max(1e-5, source.area * 1e-9)
    if (first_source.difference(source).area > tolerance or
            first_corrected.difference(first_source).area > tolerance or
            unchanged_second.difference(source).area > tolerance):
        raise GeometryError("V-miter R/BA trial cannot project detached or added material")
    removed = first_source.difference(first_corrected)
    if removed.difference(source).area > tolerance:
        raise GeometryError("V-miter R/BA correction lies outside original physical stock")
    whole = source.difference(removed)
    if (whole.geom_type != "Polygon" or whole.is_empty or
            not whole.is_valid or whole.interiors or whole.area <= _EPS):
        raise GeometryError("V-miter R/BA correction cannot keep one closed sheet")
    if (abs(source.area - whole.area - removed.area) > tolerance or
            whole.difference(source).area > tolerance):
        raise GeometryError("V-miter R/BA full-sheet removal area does not balance")
    if whole.intersection(first_source).symmetric_difference(first_corrected).area > tolerance:
        raise GeometryError("V-miter R/BA corrected first flange disagrees with 3D source")
    if (removed.intersection(unchanged_second).area > tolerance or
            abs(whole.intersection(unchanged_second).area -
                unchanged_second.area) > tolerance):
        raise GeometryError("V-miter correction would shorten the unmodified second flange")
    return whole, removed


def _retarget_round_r_first_v_edge(
    material: Polygon, original_remaining: Polygon, first_patch: Polygon,
    apex: Vec2, first_tip: Vec2, second_tip: Vec2, *,
    radius: float, offset: float,
) -> Polygon:
    """Translate only the first V cut line and recompute its *same-R* fillet.

    Unlike changing a post-R 2D taper, this reconstructs the circular
    tangencies around the new asymmetric V line intersection. The second V
    line and its real source-perimeter endpoint stay fixed. No material is
    added to the original source-backed rounded relief and the new sheet
    must remain one polygon. This remains a CHECK-only cutting hypothesis.
    """
    amount = _finite(offset, "first_edge_trim_mm")
    if amount < 0:
        raise GeometryError("V-miter R edge offset must not be negative")
    if amount == 0:
        return original_remaining

    dx, dy = first_tip.x - apex.x, first_tip.y - apex.y
    vx, vy = second_tip.x - apex.x, second_tip.y - apex.y
    first_len, second_len = math.hypot(dx, dy), math.hypot(vx, vy)
    if min(first_len, second_len) <= _EPS:
        raise GeometryError("V-miter rounded offset V rays have no length")
    ux, uy, vx, vy = dx / first_len, dy / first_len, vx / second_len, vy / second_len
    denominator = ux * vy - uy * vx
    if abs(denominator) <= _EPS:
        raise GeometryError("V-miter offset V rays have no unique intersection")

    witness = first_patch.representative_point()
    signed = ux * (witness.y - apex.y) - uy * (witness.x - apex.x)
    if abs(signed) <= _EPS:
        raise GeometryError("V-miter offset first cut has no source material side")
    side = 1 if signed > 0 else -1
    nx, ny = -uy * side, ux * side
    shifted = (apex.x + nx * amount, apex.y + ny * amount)

    # Intersect two *actual* V-cut lines. The virtual rounded-notch apex
    # need not coincide with either unchanged physical BEND intersection.
    delta_x, delta_y = apex.x - shifted[0], apex.y - shifted[1]
    along = (delta_x * vy - delta_y * vx) / denominator
    v_apex = Vec2(shifted[0] + ux * along, shifted[1] + uy * along)
    if not material.covers(Point(v_apex.x, v_apex.y)):
        raise GeometryError("V-miter shifted rounded apex lies outside source material")

    # Follow the shifted first ray to its real, unique CUTTING perimeter hit.
    # A concave/multiple-hit source cannot silently choose an unrelated tip.
    minx, miny, maxx, maxy = material.bounds
    reach = 4.0 * max(
        10.0, maxx - minx, maxy - miny,
        first_len, second_len, amount,
    ) + 10.0
    ray = LineString((
        (v_apex.x, v_apex.y),
        (v_apex.x + ux * reach, v_apex.y + uy * reach),
    ))
    hits = material.exterior.intersection(ray)
    if hits.geom_type == "Point":
        points = (hits,)
    elif hits.geom_type == "MultiPoint":
        points = tuple(hits.geoms)
    else:
        # An intersection overlapping the CUTTING contour or an ambiguous
        # GeometryCollection is not an authoritative first V endpoint.
        raise GeometryError("V-miter shifted first V ray has ambiguous source endpoint")
    points = tuple(
        p for p in points
        if ((p.x - v_apex.x) * ux + (p.y - v_apex.y) * uy) > _EPS
    )
    if len(points) != 1:
        raise GeometryError("V-miter shifted first V ray needs one positive source endpoint")
    shifted_tip = Vec2(float(points[0].x), float(points[0].y))
    outer_arc = _short_outer_arc(material, shifted_tip, second_tip)
    new_cut, _ = _rounded_v_notch_polygon(
        v_apex, shifted_tip, second_tip, outer_arc, radius,
    )
    area_tol = max(1e-5, material.area * 1e-9)
    if (new_cut.geom_type != "Polygon" or new_cut.is_empty or
            not new_cut.is_valid or new_cut.interiors or
            new_cut.difference(material).area > area_tol):
        raise GeometryError("V-miter asymmetric rounded notch leaves original source")
    new_whole = material.difference(new_cut)
    if (new_whole.geom_type != "Polygon" or new_whole.is_empty or
            not new_whole.is_valid or new_whole.interiors or
            new_whole.area <= _EPS):
        raise GeometryError("V-miter asymmetric rounded notch breaks the single sheet")
    # A shifted, same-R notch can remove MORE source stock, never fill in a
    # portion of the original R/relief opening just to hide interference.
    if new_whole.difference(original_remaining).area > area_tol:
        raise GeometryError("V-miter shifted R-tip cannot add back original cut material")
    if original_remaining.area - new_whole.area <= _EPS:
        raise GeometryError("V-miter shifted R-tip removes no additional physical stock")
    return new_whole


def _checked_full_source_profile(
    source: Polygon, corrected_full: Polygon, first_source: Polygon,
    first_corrected: Polygon, unchanged_second: Polygon,
) -> tuple[Polygon, Polygon]:
    """Verify one explicit physical CHECK source after a changed R-root shape.

    The delta may include the rounded removed wedge outside the rectangular
    first-flange footprint, so the original flange-only subtraction is not
    sufficient. This exact sheet is used for both real formed 3D and 2D
    projector; no convex-hull repair or disconnected material fallback.
    """
    for label, poly in (
        ("original full sheet", source),
        ("corrected full sheet", corrected_full),
        ("original first flange", first_source),
        ("corrected first flange", first_corrected),
        ("unchanged second flange", unchanged_second),
    ):
        if (poly.geom_type != "Polygon" or poly.is_empty or
                not poly.is_valid or poly.interiors or poly.area <= _EPS):
            raise GeometryError(f"V-miter {label} is not single valid material")
    tol = max(1e-5, source.area * 1e-9)
    if (corrected_full.difference(source).area > tol or
            first_source.difference(source).area > tol or
            first_corrected.difference(first_source).area > tol or
            unchanged_second.difference(source).area > tol):
        raise GeometryError("V-miter R-root reprofile cannot invent source material")
    removed = source.difference(corrected_full)
    if abs(source.area - corrected_full.area - removed.area) > tol:
        raise GeometryError("V-miter R-root reprofile whole source area does not balance")
    if corrected_full.intersection(first_source).symmetric_difference(first_corrected).area > tol:
        raise GeometryError("V-miter R-root first flange disagrees with 3D source")
    if (removed.intersection(unchanged_second).area > tol or
            abs(corrected_full.intersection(unchanged_second).area -
                unchanged_second.area) > tol):
        raise GeometryError("V-miter R-root reprofile would shorten the unmodified second flange")
    return corrected_full, removed


def _search_source_safe_edge_trim(evaluate, limit: float, *, failure_message: str, failure_factory=None):
    """Search only connected source-sheet candidates below an operator MAX.

    A permitted maximum is not a mandatory cut.  If that maximum severs the
    physical sheet (or destroys a flange), reduce the upper bound instead
    of rejecting a potentially sound smaller trim.  Every evaluated
    candidate still runs the original single-sheet/other-flange gate.
    This is only an uncertified geometry search, NOT 3D clearance
    certification. The genuine R/BA curved skins are now source-vertex
    watertight; a candidate for which the strict volume detector cannot
    even verify both closed meshes must be rejected, not silently selected.
    """
    def clear(candidate):
        # A returned CHECK hypothesis must be evaluable as two real closed
        # T-shells with no DETECTED crossing or positive volume witness.
        # Closed+zero sampled witnesses is STILL NOT certified zero overlap.
        # No shortened legacy synthetic candidate without a volume result
        # may bypass this physical precondition.
        return (
            len(candidate) >= 7
            and candidate[3] == 0
            and not candidate[5]
            and candidate[6] is True
        )

    original = evaluate(0.0)
    if clear(original):
        return original, original, 0.0

    safe_limit = limit
    try:
        upper = evaluate(limit)
    except GeometryError:
        # Keep a verified-valid lower candidate and a rejected upper limit.
        # Do not accept a detached maximal trim, even if its 3D shadows
        # would show zero surface crossings.
        low, high = 0.0, limit
        upper = original
        for _ in range(_BINARY_STEPS):
            mid = (low + high) / 2.0
            try:
                candidate = evaluate(mid)
            except GeometryError:
                high = mid
            else:
                low, upper = mid, candidate
        safe_limit = low

    if not clear(upper):
        if failure_factory is not None:
            raise failure_factory(original, upper, safe_limit)
        raise GeometryError(failure_message)

    low, high = 0.0, safe_limit
    best = upper
    for _ in range(_BINARY_STEPS):
        mid = (low + high) / 2.0
        # Any non-monotone invalidity INSIDE an already-validated interval
        # remains an error; do not guess a new safe manufacturing interval.
        candidate = evaluate(mid)
        if clear(candidate):
            high, best = mid, candidate
        else:
            low = mid
    return original, best, high


def _search_round_r_source_tip_profiles(
    evaluate, limit: float, relief_cutback: float, *,
    failure_message: str, failure_factory,
):
    """Retry a failed R root with a *source-scaled*, shorter trial taper.

    The legacy run=offset leaves a shallow transition from the original
    circular relief tangency. If it cannot clear the physical T-thick joint,
    evaluate run=min(offset, actual source R cutback). This is a second
    uncertified contour family, not a guessed shop tolerance or new relief
    diameter. Every candidate must pass the same closed source/unchanged
    second flange and real R/BA 3D contact gates. If nothing works, preserve
    the original measured collision evidence and reject manufacturing.
    """
    try:
        original, best, selected = _search_source_safe_edge_trim(
            lambda trim: evaluate(trim, None),
            limit, failure_message=failure_message,
            failure_factory=failure_factory,
        )
        return original, best, selected, selected, False
    except VMiterRadiusBAContactError as original_failure:
        try:
            original, best, selected = _search_source_safe_edge_trim(
                lambda trim: evaluate(
                    trim, min(trim, relief_cutback) if trim else None,
                ),
                limit, failure_message=failure_message,
                failure_factory=failure_factory,
            )
        except GeometryError:
            raise original_failure
        return original, best, selected, min(selected, relief_cutback), True


def solve_v_miter_radius_ba_interface_trial(
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
    first_inner_radius_mm: float,
    second_inner_radius_mm: float,
    first_bend_allowance_mm: float,
    second_bend_allowance_mm: float,
    max_permitted_edge_trim_mm: float,
) -> VMiterRadiusCompensatedInterfaceTrial:
    """Trial only: measured R/BA curved fold and bounded one-sided V correction.

    The maximum edge trim is an explicit operator/process constraint, not an
    arbitrary Engine default. If no collision-free *surface* candidate fits,
    refuse instead of quietly shrinking unequal flanges or ignoring overlaps.
    """
    params = dict(thickness_mm=thickness_mm,
                  first_flange_height_mm=first_flange_height_mm,
                  second_flange_height_mm=second_flange_height_mm,
                  second_fold_angle_deg=second_fold_angle_deg,
                  relief_mode=relief_mode, relief_t_factor=relief_t_factor)
    mating = project_v_miter_relief_mating_trial(
        scene, v_edge_bend, second_bend, **params,
    )
    bounded = diagnose_v_miter_bounded_bend_reach(
        scene, v_edge_bend, second_bend, **params,
    )
    if bounded.needs_independent_material_extension_evidence:
        raise GeometryError("V-miter measured R/BA trial needs independent source material extension evidence")
    q = mating.relief.source_trial.ideal.source
    limit = _finite(max_permitted_edge_trim_mm, "max_permitted_edge_trim_mm", positive=True)
    r1, ba1, k1 = _bend_measurement(
        first_inner_radius_mm, first_bend_allowance_mm, math.pi / 2,
        q.thickness_mm, "first",
    )
    theta = math.radians(q.second_fold_angle_deg)
    r2, ba2, k2 = _bend_measurement(
        second_inner_radius_mm, second_bend_allowance_mm, theta,
        q.thickness_mm, "second",
    )
    apex = q.bend_intersection
    e1 = _outward_bend_axis(v_edge_bend, apex)
    e2 = _outward_bend_axis(second_bend, apex)
    n1, n2 = _outside_normal(e1, e2), _outside_normal(e2, e1)
    remaining = Polygon([(p.x, p.y) for p in mating.relief.trial_remaining_outline])
    if remaining.is_empty or not remaining.is_valid or remaining.interiors:
        raise GeometryError("V-miter R/BA trial remaining source is invalid")
    patch1, _ = _flange_footprint(
        remaining, apex, e1, n1,
        source_span=bounded.first_bend_span_mm,
        source_flange_height=q.first_flange_height_mm,
    )
    patch2, _ = _flange_footprint(
        remaining, apex, e2, n2,
        source_span=bounded.second_bend_span_mm,
        source_flange_height=q.second_flange_height_mm,
    )
    if patch1.intersection(patch2).area > _EPS:
        raise GeometryError("V-miter R/BA source flanges have flat material overlap")
    skin2 = _formed_curved_skin(
        patch2, apex, e2, n2, angle_rad=theta, inner_r=r2,
        allowance=ba2, thickness=q.thickness_mm,
        axial_span=bounded.second_bend_span_mm,
        flange_height=q.second_flange_height_mm,
    )
    solid2 = tuple(thicken_triangle_surface(skin2, q.thickness_mm, smooth_vertex_normals=True))
    if not solid2:
        raise GeometryError("V-miter R/BA second solid is empty")
    source_material = (
        _single_source_material(scene)
        if q.relief_mode is VMiterReliefMode.ROUND_R else None
    )

    def evaluate_formed(candidate: Polygon, whole: Polygon):
        full_height = LineString((
            _flat_point(apex, e1, n1, 0, q.first_flange_height_mm),
            _flat_point(apex, e1, n1, bounded.first_bend_span_mm, q.first_flange_height_mm),
        ))
        if candidate.intersection(full_height).length <= _EPS:
            raise GeometryError("V-miter trial trim removes the first flange full-height source")
        skin = _formed_curved_skin(
            candidate, apex, e1, n1, angle_rad=math.pi / 2, inner_r=r1,
            allowance=ba1, thickness=q.thickness_mm,
            axial_span=bounded.first_bend_span_mm,
            flange_height=q.first_flange_height_mm,
        )
        solid = tuple(thicken_triangle_surface(skin, q.thickness_mm, smooth_vertex_normals=True))
        if not solid:
            raise GeometryError("V-miter R/BA first solid is empty")
        collision = detect_world_mesh_surface_interference(solid, solid2)
        if collision.pair_count:
            enclosed = ()
            closed = False
        else:
            # A zero surface-crossing verdict cannot conceal a fully
            # nested closed physical volume in either direction.
            inside = detect_world_mesh_enclosed_volume_witness(solid, solid2)
            enclosed = inside.strictly_inside_points
            closed = inside.meshes_closed
        return (
            candidate, skin, solid, collision.pair_count,
            collision.intersection_segments, enclosed, closed, whole,
        )

    def evaluate(trim: float, transition_run_mm: float | None = None):
        # A zero correction is EXACTLY the original source; do not clip
        # the physical ROUND_R root before counting actual interference.
        candidate = patch1 if trim == 0.0 else _trim_one_v_edge(
            patch1, apex, mating.relief.source_trial.ideal.first_flat_miter_ray[1],
            trim, relief_open_length_mm=mating.formed_open_relief_length_mm,
            transition_run_mm=transition_run_mm,
        )
        whole, _ = _checked_full_source_from_trim(
            remaining, patch1, candidate, patch2,
        )
        return evaluate_formed(candidate, whole)

    def evaluate_retargeted_round_r(trim: float):
        if trim == 0.0:
            return evaluate(0.0)
        if source_material is None:
            raise GeometryError("V-miter asymmetric R-root trial requires ROUND_R source")
        # Shift ONE original V cut line into the verified first-flange
        # material; recompute its intersection and the *same radius* arc
        # tangent to both lines. The second V line/end remain unchanged.
        whole = _retarget_round_r_first_v_edge(
            source_material, remaining, patch1,
            apex, mating.relief.source_trial.ideal.first_flat_miter_ray[1],
            mating.relief.source_trial.ideal.second_flat_miter_ray[1],
            radius=mating.relief.relief_radius_mm, offset=trim,
        )
        first, _ = _flange_footprint(
            whole, apex, e1, n1,
            source_span=bounded.first_bend_span_mm,
            source_flange_height=q.first_flange_height_mm,
        )
        _checked_full_source_profile(
            remaining, whole, patch1, first, patch2,
        )
        return evaluate_formed(first, whole)

    collision_failure = (
        "V-miter ROUND_R source-preserving trim still has detected "
        "true-T interference within permitted trim"
        if q.relief_mode is VMiterReliefMode.ROUND_R
        else "V-miter R/BA trial cannot eliminate detected overlap within permitted trim"
    )
    def contact_failure(baseline, rejected, attempted_trim):
        return VMiterRadiusBAContactError(
            collision_failure if rejected[3] else (
                "V-miter R/BA trial retains strictly enclosed true-T volume overlap"
                if rejected[5] else
                "V-miter R/BA trial cannot accept UNKNOWN true-T volume closure"
            ), original_pairs=baseline[3],
            attempted_pairs=rejected[3], attempted_segments=rejected[4],
            attempted_trim_mm=attempted_trim,
            attempted_containment_points=rejected[5],
        )

    retargeted_round_r = False
    if q.relief_mode is VMiterReliefMode.ROUND_R:
        try:
            original, best, selected, transition, local_root_taper = (
                _search_round_r_source_tip_profiles(
                    evaluate, limit, mating.formed_open_relief_length_mm,
                    failure_message=collision_failure,
                    failure_factory=contact_failure,
                )
            )
        except VMiterRadiusBAContactError as first_attempt_failure:
            # The original R-preserving profiles cannot clear the physical
            # root. Only now consider a *same-R*, new-tangency asymmetric
            # notch, still within the explicit one-side operator trim MAX.
            try:
                original, best, selected = _search_source_safe_edge_trim(
                    evaluate_retargeted_round_r, limit,
                    failure_message=collision_failure,
                    failure_factory=contact_failure,
                )
            except GeometryError:
                # Never promote a split source or unsupported new root. The
                # initial measured 3D collision remains authoritative.
                raise first_attempt_failure
            transition, local_root_taper = 0.0, False
            retargeted_round_r = True
    else:
        original, best, selected = _search_source_safe_edge_trim(
            lambda trim: evaluate(trim, None),
            limit, failure_message=collision_failure,
            failure_factory=contact_failure,
        )
        transition, local_root_taper = selected, False

    # The source-safe trim search now rejects any UNKNOWN strict-volume
    # closure before returning CHECK. Publish independent edge-incidence
    # evidence as well: verified closure + no detected finite witness is
    # only a precondition for an uncertified geometry hypothesis, not a
    # proof of arbitrary non-convex zero overlap or factory acceptance.
    topo_first = diagnose_world_mesh_triangle_edge_incidence(best[2])
    topo_second = diagnose_world_mesh_triangle_edge_incidence(solid2)
    true_t_volume_status = (
        "V_MITER_TRUE_T_VOLUME_SAMPLED_NO_POSITIVE_WITNESS_UNCERTIFIED"
        if best[6] and topo_first.edges_manifold_closed
        and topo_second.edges_manifold_closed else
        "V_MITER_TRUE_T_VOLUME_UNKNOWN_OPEN_MESH_UNCERTIFIED"
    )

    # This section-based physical gap evidence is evaluated exactly ONCE
    # after final 2D whole-source and R/BA/T collision checks, not in each
    # trim search step. It can expose missing mating material and positive
    # gaps, but has NO factory threshold and cannot certify seam continuity.
    seam_gap = project_v_miter_true_t_seam_section_gap_trial(
        best[2], solid2,
        formed_seam_start=bounded.ideal.formed_seam_start,
        formed_seam_end=bounded.ideal.formed_seam_end,
    )

    # Trace the *original* new 2D CUTTING edges to the actual 3D T-thick
    # sidewalls after all one-sheet, real R/BA and collision gates.
    # Preserve paired flat triangle provenance from the same fold owner;
    # any 3D mesh mismatch or nonphysical sidewall fails closed.
    original_cutting = _single_source_material(scene)
    corrected_whole = best[7]
    first_formed_check, first_flat_pairs = _formed_curved_skin(
        best[0], apex, e1, n1, angle_rad=math.pi / 2, inner_r=r1,
        allowance=ba1, thickness=q.thickness_mm,
        axial_span=bounded.first_bend_span_mm,
        flange_height=q.first_flange_height_mm,
        return_flat_pairs=True,
    )
    second_formed_check, second_flat_pairs = _formed_curved_skin(
        patch2, apex, e2, n2, angle_rad=theta, inner_r=r2,
        allowance=ba2, thickness=q.thickness_mm,
        axial_span=bounded.second_bend_span_mm,
        flange_height=q.second_flange_height_mm,
        return_flat_pairs=True,
    )
    if first_formed_check != best[1] or second_formed_check != skin2:
        raise GeometryError("V-miter source-mapped 2D/3D cut-face mesh changed during CHECK")
    first_cut_face = trace_v_miter_source_true_t_cut_faces(
        original_cutting, corrected_whole,
        first_flat_pairs, best[1], best[2], thickness_mm=q.thickness_mm,
    )
    second_cut_face = trace_v_miter_source_true_t_cut_faces(
        original_cutting, corrected_whole,
        second_flat_pairs, skin2, solid2, thickness_mm=q.thickness_mm,
    )
    cut_face_gap = (
        project_v_miter_true_t_seam_section_gap_trial(
            first_cut_face.true_cut_face_triangles,
            second_cut_face.true_cut_face_triangles,
            formed_seam_start=bounded.ideal.formed_seam_start,
            formed_seam_end=bounded.ideal.formed_seam_end,
        )
        if first_cut_face.has_source_tagged_cut_faces
        and second_cut_face.has_source_tagged_cut_faces
        else None
    )

    # Fixed seven-section CHECK witnesses remain stable for back-compat;
    # this source-mesh topology CHECK subdivides every interval between
    # real physical cut-face vertex events, so a short material absence
    # cannot be omitted merely because it fell between those seven stations.
    # A complete face-presence verdict is NOT continuous contact nor a
    # qualified maximum factory seam gap.
    cut_face_continuity = (
        project_v_miter_true_cut_face_continuity_trial(
            first_cut_face.true_cut_face_triangles,
            second_cut_face.true_cut_face_triangles,
            formed_seam_start=bounded.ideal.formed_seam_start,
            formed_seam_end=bounded.ideal.formed_seam_end,
        )
        if first_cut_face.has_source_tagged_cut_faces
        and second_cut_face.has_source_tagged_cut_faces
        else None
    )

    return VMiterRadiusCompensatedInterfaceTrial(
        first_inner_radius_mm=r1, second_inner_radius_mm=r2,
        first_bend_allowance_mm=ba1, second_bend_allowance_mm=ba2,
        first_neutral_axis_k=k1, second_neutral_axis_k=k2,
        first_edge_trim_mm=selected, max_permitted_edge_trim_mm=limit,
        untrimmed_surface_interference_pairs=original[3],
        trimmed_surface_interference_pairs=best[3],
        first_flat_source_area_mm2=patch1.area,
        first_flat_source_outline=tuple(Vec2(float(x), float(y)) for x, y in patch1.exterior.coords),
        full_source_remaining_outline=mating.relief.trial_remaining_outline,
        first_flat_trimmed_area_mm2=best[0].area,
        second_flat_source_area_mm2=patch2.area,
        first_trimmed_check_outline=tuple(Vec2(float(x), float(y)) for x, y in best[0].exterior.coords),
        first_formed_skin_triangles=best[1],
        second_formed_skin_triangles=skin2,
        first_thick_solid_triangles=best[2],
        second_thick_solid_triangles=solid2,
        untrimmed_enclosed_volume_witness_count=len(original[5]),
        trimmed_enclosed_volume_witness_count=len(best[5]),
        formed_volume_containment_meshes_closed=bool(best[6]),
        first_thick_solid_boundary_edge_count=topo_first.boundary_edge_count,
        second_thick_solid_boundary_edge_count=topo_second.boundary_edge_count,
        first_thick_solid_nonmanifold_edge_count=topo_first.nonmanifold_edge_count,
        second_thick_solid_nonmanifold_edge_count=topo_second.nonmanifold_edge_count,
        first_thick_solid_degenerate_triangle_count=topo_first.degenerate_triangle_count,
        second_thick_solid_degenerate_triangle_count=topo_second.degenerate_triangle_count,
        first_thick_solid_boundary_edge_examples_xyz=topo_first.boundary_edge_examples_xyz,
        second_thick_solid_boundary_edge_examples_xyz=topo_second.boundary_edge_examples_xyz,
        true_t_volume_check_status=true_t_volume_status,
        first_edge_transition_span_mm=transition,
        seam_section_gap_trial=seam_gap,
        first_source_cut_face=first_cut_face,
        second_source_cut_face=second_cut_face,
        source_cut_face_section_gap_trial=cut_face_gap,
        source_cut_face_continuity_trial=cut_face_continuity,
        full_corrected_check_outline=tuple(
            Vec2(float(x), float(y)) for x, y in best[7].exterior.coords
        ),
        geometry_model=(
            "SOURCE_R_BA_CYLINDRICAL_FOLD_ASYMMETRIC_SAME_R_TANGENT_TRIM_TRIAL"
            if retargeted_round_r else
            "SOURCE_R_BA_CYLINDRICAL_FOLD_R_TIP_LOCAL_V_TRIM_TRIAL"
            if local_root_taper else
            "SOURCE_R_BA_CYLINDRICAL_FOLD_ONE_SIDED_V_TRIM_TRIAL"
        ),
    )


@dataclass(frozen=True)
class VMiterRadiusBAFullSheetCheck:
    """One checked closed *single-sheet* outline; never production CUTTING."""

    trial: VMiterRadiusCompensatedInterfaceTrial
    full_source_area_mm2: float
    full_corrected_area_mm2: float
    actual_removed_trim_area_mm2: float
    corrected_check_outline: tuple[Vec2, ...]
    geometry_model: str = "SOURCE_SINGLE_SHEET_R_BA_CORRECTED_CHECK_ONLY"
    manufacturing_status: str = "V_MITER_RADIUS_BA_FULL_SHEET_UNCERTIFIED"


def project_v_miter_radius_ba_full_sheet_check(
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
    first_inner_radius_mm: float,
    second_inner_radius_mm: float,
    first_bend_allowance_mm: float,
    second_bend_allowance_mm: float,
    max_permitted_edge_trim_mm: float,
) -> VMiterRadiusBAFullSheetCheck:
    """Backproject the *same solved* local R/BA trim onto original whole sheet.

    The trial's local clipped flange is NOT the whole material outline. The
    removed delta must be a genuine subset of the same original source
    material; subtract it only once from the source-backed V-relieved sheet.
    A hole, split sheet, other-flange change or area mismatch rejects the
    candidate. The resulting closed polygon is a CHECK witness, NOT a
    certified machine-cutting route.
    """
    trial = solve_v_miter_radius_ba_interface_trial(
        scene, v_edge_bend, second_bend,
        thickness_mm=thickness_mm,
        first_flange_height_mm=first_flange_height_mm,
        second_flange_height_mm=second_flange_height_mm,
        second_fold_angle_deg=second_fold_angle_deg,
        relief_mode=relief_mode,
        relief_t_factor=relief_t_factor,
        first_inner_radius_mm=first_inner_radius_mm,
        second_inner_radius_mm=second_inner_radius_mm,
        first_bend_allowance_mm=first_bend_allowance_mm,
        second_bend_allowance_mm=second_bend_allowance_mm,
        max_permitted_edge_trim_mm=max_permitted_edge_trim_mm,
    )
    source = Polygon([(point.x, point.y) for point in trial.full_source_remaining_outline])
    original_patch = Polygon([(point.x, point.y) for point in trial.first_flat_source_outline])
    trimmed_patch = Polygon([(point.x, point.y) for point in trial.first_trimmed_check_outline])
    # The second (possibly taller) flange is not a trimming target. It is
    # independently re-extracted from the ORIGINAL two-BEND material
    # source, and its area must survive the whole-sheet correction intact.
    bounded = diagnose_v_miter_bounded_bend_reach(
        scene, v_edge_bend, second_bend,
        thickness_mm=thickness_mm,
        first_flange_height_mm=first_flange_height_mm,
        second_flange_height_mm=second_flange_height_mm,
        second_fold_angle_deg=second_fold_angle_deg,
        relief_mode=relief_mode,
        relief_t_factor=relief_t_factor,
    )
    apex = bounded.ideal.source.bend_intersection
    e1 = _outward_bend_axis(v_edge_bend, apex)
    e2 = _outward_bend_axis(second_bend, apex)
    n2 = _outside_normal(e2, e1)
    second_patch, _ = _flange_footprint(
        source, apex, e2, n2,
        source_span=bounded.second_bend_span_mm,
        source_flange_height=bounded.ideal.source.second_flange_height_mm,
    )
    if abs(second_patch.area - trial.second_flat_source_area_mm2) > max(
        1e-5, source.area * 1e-9,
    ):
        raise GeometryError("V-miter CHECK source second flange differs from the solved source")
    if trial.full_corrected_check_outline:
        corrected = Polygon((
            (point.x, point.y) for point in trial.full_corrected_check_outline
        ))
        whole, removed = _checked_full_source_profile(
            source, corrected, original_patch, trimmed_patch, second_patch,
        )
    else:
        whole, removed = _checked_full_source_from_trim(
            source, original_patch, trimmed_patch, second_patch,
        )
    return VMiterRadiusBAFullSheetCheck(
        trial=trial,
        full_source_area_mm2=source.area,
        full_corrected_area_mm2=whole.area,
        actual_removed_trim_area_mm2=removed.area,
        corrected_check_outline=tuple(
            Vec2(float(x), float(y)) for x, y in whole.exterior.coords
        ),
    )


def build_v_miter_radius_ba_full_sheet_check_scene(
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
    first_inner_radius_mm: float,
    second_inner_radius_mm: float,
    first_bend_allowance_mm: float,
    second_bend_allowance_mm: float,
    max_permitted_edge_trim_mm: float,
) -> DrawingScene:
    """Write only DATUM source and CHECK candidate, never CNC CUTTING/BEND."""
    from .v_miter_material_trial import _single_source_material
    from .sheetmetal_drawing import PolylinePrimitive

    trial = project_v_miter_radius_ba_full_sheet_check(
        scene, v_edge_bend, second_bend,
        thickness_mm=thickness_mm,
        first_flange_height_mm=first_flange_height_mm,
        second_flange_height_mm=second_flange_height_mm,
        second_fold_angle_deg=second_fold_angle_deg,
        relief_mode=relief_mode, relief_t_factor=relief_t_factor,
        first_inner_radius_mm=first_inner_radius_mm,
        second_inner_radius_mm=second_inner_radius_mm,
        first_bend_allowance_mm=first_bend_allowance_mm,
        second_bend_allowance_mm=second_bend_allowance_mm,
        max_permitted_edge_trim_mm=max_permitted_edge_trim_mm,
    )
    original = _single_source_material(scene)
    result = DrawingScene([
        PolylinePrimitive(
            tuple(Vec2(float(x), float(y)) for x, y in original.exterior.coords),
            "DATUM", closed=True, semantic_id="v_miter_radius_ba_original_source",
        ),
        PolylinePrimitive(
            trial.corrected_check_outline,
            "CHECK", closed=True,
            semantic_id="v_miter_radius_ba_corrected_uncertified",
        ),
        LinePrimitive(v_edge_bend.p1, v_edge_bend.p2, "DATUM"),
        LinePrimitive(second_bend.p1, second_bend.p2, "DATUM"),
    ])
    return result
