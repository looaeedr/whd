# -*- coding: utf-8 -*-
"""#3317: source-backed ALTERNATIVE mating-face check on the SAME Tail sheet.

The original 90-degree V cut has TWO physical edge walls: upper SIDE V and
lower BOTTOM V. Instead of repeatedly re-measuring those same walls, test
the other real, uncut T/2 OUTER SKIN of the BOTTOM stock facing the side wall.

This is a side-wall-to-existing-broad-face LAP-contact hypothesis. It does
NOT change the actual V, cannot certify a V-miter, and cannot be used for
CUTTING or manufacturing. Every actual face is an existing T-solid face
indexed from the one Factory source triangle mesh. A zero nearest-surface
distance somewhere off datum is not a proven full seam.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from shapely.geometry import Point

from .contracts import PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES
from .sheetmetal_geometry_core import GeometryError
from .v_miter_cut_face_continuity_trial import (
    project_v_miter_true_cut_face_continuity_trial,
)
from .v_miter_seam_gap_trial import (
    project_v_miter_true_t_seam_section_gap_trial,
)
from .v_miter_tail_sequential_fold_check import TailSequentialFoldResult


@dataclass(frozen=True)
class TailAlternativeMatingTrial:
    corner: str
    candidate_id: str
    first_axis: str
    side_surface_source: str
    bottom_surface_source: str
    side_true_t_faces: tuple
    bottom_true_t_broad_faces: tuple
    bottom_broad_source_triangles_xy: tuple
    bottom_broad_source_area_mm2: float
    # physical fold panels are source owned; candidate does not create
    # CUTTING, change R/BA, join previously disconnected UV regions,
    # or grant unapproved overlap/contact.
    bottom_actual_t_outer_skin_verified: bool
    sampled_section_z_gap_mm: tuple
    full_span_coverage: object | None
    full_span_error: str | None
    min_section_gap_mm: float | None
    max_section_gap_mm: float | None
    seam_mating_status: str
    source_validity_status: str = "BOTH_FACES_FROM_EXISTING_FACTORY_T_SHELL"
    root_physical_status: str = "FINITE_BEND_TIP_TRANSITION_UNCERTIFIED"
    manufacturing_status: str = "CHECK_ONLY_NOT_APPROVED"


def project_tail_existing_bottom_broad_face_candidate(
    sequential: TailSequentialFoldResult,
    *, corner: str, apex, current_V_hits,
    formed_seam_start, formed_seam_end,
    station_fractions: tuple[float, ...] = (.25,.50,.75,.95),
) -> TailAlternativeMatingTrial:
    """Try actual SIDE upper-V wall versus retained BOTTOM broad outer face.

    The broad panel is the BOTTOM's source UV y<=apex.y, located outboard
    of the finite bottom BEND endpoints (same corner as the original V).
    Its T/2 outer triangles come from the FIRST of each actual source T
    solid's paired plus/minus faces, never from a fabricated clipping plane.
    """
    if not isinstance(sequential,TailSequentialFoldResult):
        raise GeometryError("TAIL_ALT_TYPED_SAME_SHEET_REQUIRED")
    if corner not in ("bottom_left","bottom_right"):
        raise GeometryError("TAIL_ALT_SOURCE_CORNER_INVALID")
    if not (hasattr(apex,"x") and hasattr(apex,"y")
            and len(tuple(current_V_hits))==2):
        raise GeometryError("TAIL_ALT_ORIGINAL_V_SOURCE_REQUIRED")
    tol=float(
        PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance
    )
    left,right,bottom,minx,maxx,side_end,allowance,midr=(
        sequential.source_fold_parameters
    )
    if abs(float(apex.y)-bottom)>tol:
        raise GeometryError("TAIL_ALT_ORIGINAL_BEND_STATION_CHANGED")
    is_left=corner=="bottom_left"
    if abs(float(apex.x)-(left if is_left else right))>tol:
        raise GeometryError("TAIL_ALT_SIDE_BEND_STATION_CHANGED")
    source=sequential.flat_source_triangles
    stage2=sequential.second_formed_skin_triangles
    physical=sequential.second_thick_solid_triangles
    if len(physical)<2*len(source) or len(stage2)!=len(source):
        raise GeometryError("TAIL_ALT_UNPAIRED_TRUE_T_SOURCE")
    broad=[]
    flat=[]
    flat_area=0.0
    for i,triangle in enumerate(source):
        # The same Factory original lower-side material. No assignment of
        # y<48 to the side fold; it remains exclusively BOTTOM-owned.
        if not all(
            y<=bottom+tol and
            (x<=left+tol if is_left else x>=right-tol)
            for x,y in triangle
        ):
            continue
        # Valid original retained stock on this side, not a guessed panel.
        # GEOS line intersections used for the original 45-degree V
        # tessellation can put a vertex a few IEEE ulps outside the
        # polygon boundary. Demand the *actual source* numerical envelope
        # (not a manufactured clearance) and never accept a finite-area
        # outsider. The paired triangle was already derived by the
        # source-conserving full-blank triangulator.
        if any(
            Point(float(x),float(y)).distance(
                sequential.source_material_polygon
            ) > tol
            for x,y in triangle
        ):
            raise GeometryError("TAIL_ALT_FACE_OUTSIDE_REAL_CUTTING")
        z_levels=[p[2] for p in stage2[i]]
        if min(z_levels)<-tol:
            raise GeometryError("TAIL_ALT_BOTTOM_SOURCE_MOVED_INTO_NEGATIVE_Z")
        face=physical[2*i]  # actual true-T outward + skin from Engine
        if len(face)!=3:
            raise GeometryError("TAIL_ALT_T_FACE_NOT_PHYSICAL")
        for inner,outer in zip(stage2[i],face):
            if abs(math.dist(inner,outer)-(
                math.dist(physical[2*i][0],stage2[i][0])
            ))>tol:
                raise GeometryError("TAIL_ALT_OUTER_T_FACE_NOT_SOURCE_PAIRED")
        broad.append(face)
        flat.append(triangle)
        a,b,c=triangle
        flat_area+=abs(
            (b[0]-a[0])*(c[1]-a[1]) -
            (b[1]-a[1])*(c[0]-a[0])
        )/2.0
    if not broad or flat_area<=tol:
        raise GeometryError("TAIL_ALT_REAL_BOTTOM_OUTER_STOCK_MISSING")
    row=next(
        (r for r in sequential.true_t_cut_faces_by_corner if r[0]==corner),
        None,
    )
    if row is None or not row[3]:
        raise GeometryError("TAIL_ALT_TRUE_SIDE_V_CUT_WALL_MISSING")
    side_wall=row[3]
    # The other mating surface is a broad T face, NOT an originally CUT
    # V wall. Do not claim any improvement in the original V-cut pairing
    # unless actual full-span measurement proves it.
    samples=project_v_miter_true_t_seam_section_gap_trial(
        side_wall,tuple(broad),
        formed_seam_start=formed_seam_start,
        formed_seam_end=formed_seam_end,
        station_fractions=station_fractions,
    )
    full=None
    full_error=None
    try:
        # The mathematical mesh-event interval algorithm works for BOTH
        # genuine broad skin and cut-wall triangles; its class naming is
        # historical. Do not label the broad skin a V CUTTING face.
        full=project_v_miter_true_cut_face_continuity_trial(
            side_wall,tuple(broad),
            formed_seam_start=formed_seam_start,
            formed_seam_end=formed_seam_end,
        )
    except GeometryError as exc:
        full_error=str(exc)
        # Unresolved math stays RED but station results remain observable.
    rows=tuple(
        (float(s.section_origin_xyz[2]),s.status,s.measured_gap_mm,
         s.nearest_first_xyz,s.nearest_second_xyz,
         s.off_datum_shortcut)
        for s in samples.sections
    )
    # A point/sampled seam is NEVER a full contact certification.
    # Only an interval-complete upper bound at numerical geometry
    # tolerance can even qualify for further physical approval.
    qualified=(
        full is not None and
        full.max_gap_upper_bound_mm is not None and
        full.max_gap_upper_bound_mm <= tol and
        full.missing_face_interval_count==0 and
        full.numerically_unresolved_vertex_event_count==0 and
        samples.missing_section_count==0 and
        not samples.off_datum_shortcut_station_count
    )
    status=(
        "ALTERNATE_BROAD_FACE_FIT_CANDIDATE_REQUIRES_ROOT_VERIFICATION"
        if qualified else
        "ALTERNATE_BROAD_FACE_NOT_FULLY_MATING"
    )
    return TailAlternativeMatingTrial(
        corner=corner,
        candidate_id="SIDE_UPPER_V_WALL_TO_EXISTING_BOTTOM_OUTER_T_SKIN",
        first_axis=sequential.first_axis,
        side_surface_source="EXISTING_UPPER_V_CUTTING_SIDE_T_WALL",
        bottom_surface_source="EXISTING_BOTTOM_PANEL_OUTER_TRUE_T_BROAD_FACE",
        side_true_t_faces=tuple(side_wall),
        bottom_true_t_broad_faces=tuple(broad),
        bottom_broad_source_triangles_xy=tuple(flat),
        bottom_broad_source_area_mm2=float(flat_area),
        bottom_actual_t_outer_skin_verified=True,
        sampled_section_z_gap_mm=rows,
        full_span_coverage=full,
        full_span_error=full_error,
        min_section_gap_mm=samples.min_measured_gap_mm,
        max_section_gap_mm=samples.max_measured_gap_mm,
        seam_mating_status=status,
    )
