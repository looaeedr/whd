# -*- coding: utf-8 -*-
"""#3317 trace genuine source V CUTTING-edge sidewalls into formed true-T mesh.

A globally closest formed-surface triangle (or even the nearest triangle to
the ideal seam datum) is not necessarily a *cut edge*. This CHECK-only owner
requires BOTH (1) an actual newly removed portion of the original one-piece
CUTTING perimeter and (2) the boundary of a real, source-paired curved skin.
Its two sidewall triangles must also be present in the independently built
true-thickness closed-solid mesh. Do not manufacture a bevel or assume that
an untagged perimeter / artificial flange clipping plane is a V cut face.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math

from shapely.geometry import LineString, Polygon

from .assembly_geometry_primitives import smoothed_surface_vertex_offsets
from .contracts import PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES
from .sheetmetal_geometry_core import GeometryError


@dataclass(frozen=True)
class VMiterSourceCutFaceTrial:
    """True T-thick sidewalls positively traced to new 2D V cut material."""

    source_new_v_cut_length_mm: float
    selected_flat_v_cut_length_mm: float
    formed_boundary_edge_count: int
    true_cut_face_triangles: tuple
    geometry_model: str = "SOURCE_2D_V_CUT_TO_CURVED_3D_T_SIDEWALL_CHECK"
    manufacturing_status: str = "V_MITER_TRUE_CUT_FACE_UNCERTIFIED"

    @property
    def has_source_tagged_cut_faces(self) -> bool:
        return bool(self.true_cut_face_triangles)


def _key(point, tolerance):
    return tuple(int(round(float(x) / tolerance)) for x in point)


def _tri_key(triangle, tolerance):
    return tuple(sorted(_key(p, tolerance) for p in triangle))


def trace_v_miter_source_true_t_cut_faces(
    original_cutting_material: Polygon,
    corrected_whole_material: Polygon,
    paired_flat_skin_triangles,
    formed_skin_triangles,
    physical_thick_solid_triangles,
    *,
    thickness_mm: float,
    physical_vertex_offsets=None,
    physical_v_cut_leg_lines=None,
) -> VMiterSourceCutFaceTrial:
    """Select only real new V-cut boundary sidewall triangles, not all faces.

    `paired_flat_skin_triangles` are recorded by the SAME curved-fold owner
    during meshing (no inverse Z->flat guess). Every selected boundary edge
    must lie exactly on the corrected full source's *new* CUTTING boundary,
    not on original outer stock or an artificial first/second flange clip.
    Full source closure, whole-sheet area, T and the formed skin/solid identity
    are verified before exposing evidence. When provided, exactly two
    source-proven straight V-leg boundaries exclude the ROUND_R / relief-hole
    *root* face: a bottom relief surface cannot masquerade as an inclined
    mating face. Missing tagged faces are UNKNOWN, not a zero gap.
    """
    tol = float(
        PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance
    )
    if not math.isfinite(tol) or tol <= 0:
        raise GeometryError("V-miter source cut-face numerical tolerance is invalid")
    if (
        original_cutting_material.geom_type != "Polygon"
        or corrected_whole_material.geom_type != "Polygon"
        or original_cutting_material.is_empty
        or corrected_whole_material.is_empty
        or not original_cutting_material.is_valid
        or not corrected_whole_material.is_valid
        or original_cutting_material.interiors
        or corrected_whole_material.interiors
    ):
        raise GeometryError("V-miter source cut-face needs original and corrected single sheets")
    # The two leg directions must originate from the independently qualified
    # Factory V source. This filter cannot grant geometry: all selected edges
    # must independently pass the full new-CUTTING boundary and T-solid gates.
    eligible_legs = None
    if physical_v_cut_leg_lines is not None:
        if (type(physical_v_cut_leg_lines) not in (tuple, list)
                or len(physical_v_cut_leg_lines) != 2):
            raise GeometryError("V_MITER_SOURCE_CUT_FACE_LEGS_INVALID")
        eligible_legs = tuple(physical_v_cut_leg_lines)
        for leg in eligible_legs:
            if (not isinstance(leg, LineString) or leg.is_empty
                    or not leg.is_valid or len(leg.coords) != 2
                    or leg.length <= tol
                    or any(not math.isfinite(float(value))
                           for point in leg.coords for value in point)):
                raise GeometryError("V_MITER_SOURCE_CUT_FACE_LEGS_INVALID")
    t = thickness_mm
    if isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t) or t <= 0:
        raise GeometryError("V-miter source cut-face requires actual finite positive thickness")
    # The error budget is a coordinate LENGTH, not a fraction of the sheet
    # AREA. An area-scaled test lets a large original blank silently admit
    # a small but physically out-of-perimeter material tab as "source".
    # Use only the already-owned numerical distance tolerance, never an
    # assumed kerf, clearance, R/BA or factory allowance. No positive-area
    # outside-source material may survive beyond that spatial envelope.
    outside_source = corrected_whole_material.difference(
        original_cutting_material.buffer(tol)
    )
    if not outside_source.is_empty:
        raise GeometryError("V-miter source cut-face cannot invent corrected stock")

    # Unlike corrected material's entire perimeter, this difference includes
    # ONLY edges introduced by actual subtraction from original CUTTING.
    new_cut = corrected_whole_material.boundary.difference(
        original_cutting_material.boundary
    )
    new_length = float(new_cut.length)
    if not math.isfinite(new_length) or new_length <= tol:
        raise GeometryError("V-miter source cut-face has no real new V-cut perimeter")

    flat = tuple(paired_flat_skin_triangles)
    formed = tuple(formed_skin_triangles)
    solid = tuple(physical_thick_solid_triangles)
    if not flat or len(flat) != len(formed) or not solid:
        raise GeometryError("V-miter source cut-face lacks paired 2D/3D/true-T mesh")
    edges = defaultdict(list)
    # Use the exact shared vertex offsets applied by the source R/BA curved
    # T-shell builder: now the measured cylindrical R/BA radial offsets,
    # not triangulation-area-averaged face normals. A second independent
    # sidewall formula could invent faces absent from the true physical T.
    vertex_offsets = (
        physical_vertex_offsets if physical_vertex_offsets is not None else
        smoothed_surface_vertex_offsets(formed, t, tolerance=tol)
    )

    def pair_point(a, name, dimension):
        try:
            p = tuple(float(x) for x in a)
        except (TypeError, ValueError, OverflowError):
            raise GeometryError(f"V-miter source cut-face {name} point invalid") from None
        if len(p) != dimension or not all(math.isfinite(x) for x in p):
            raise GeometryError(f"V-miter source cut-face {name} point invalid")
        return p

    for row_index, (tri2, tri3) in enumerate(zip(flat, formed)):
        if len(tri2) != 3 or len(tri3) != 3:
            raise GeometryError("V-miter source cut-face needs matching triangles")
        f2 = tuple(pair_point(v, "flat", 2) for v in tri2)
        f3 = tuple(pair_point(v, "formed", 3) for v in tri3)
        for i in range(3):
            a, b = f2[i], f2[(i + 1) % 3]
            k = tuple(sorted((_key(a, tol), _key(b, tol))))
            edges[k].append((a, b, f3[i], f3[(i + 1) % 3], f3[(i + 2) % 3]))
    # The sidewalls from the *same actual thicken_triangle_surface* must
    # be present in the independent true-T solid. A fabricated face is RED.
    solid_keys = {_tri_key(tri, tol) for tri in solid}
    result = []
    total_flat_length = 0.0
    selected_edges = 0
    for adjacent in edges.values():
        if len(adjacent) != 1:
            continue
        a2, b2, a3, b3, c3 = adjacent[0]
        segment = LineString((a2, b2))
        seg_length = float(segment.length)
        if seg_length <= tol:
            continue
        # Full segment overlap, NOT just a vertex touching the V notch.
        # Avoid the global source perimeter and artificial clipping edges.
        # A curved neutral-axis bend subdivides the exact flat source
        # V leg into strip polygons. Shapely may return slightly displaced
        # floating-point vertices after polygon intersection; literal
        # LineString intersection can report *zero* overlap for a genuine
        # source cut face. Demand whole-edge containment in the original
        # true CUTTING boundary's NUMERICAL envelope, not just endpoint
        # touch or a nearest-edge lookup. This is Engine tolerance, never
        # an operator-acceptable manufacturing gap.
        if segment.difference(new_cut.buffer(tol)).length > tol:
            continue
        if eligible_legs is not None and not any(
            # The same edge has passed the strict original new-CUTTING
            # numerical envelope. Strip intersection can then shift a
            # second time by one tolerance when tested against the ideal
            # source ray; allow TWO such round-off budgets only, not an
            # operator-specified fit or clearance allowance.
            segment.difference(leg.buffer(2.0 * tol)).length <= tol
            for leg in eligible_legs
        ):
            # The circular/swept relief-root wall is genuine CUTTING but
            # not a weldable V side. Do not count it as seam-face coverage.
            continue
        offset_a = vertex_offsets[_key(a3, tol)]
        offset_b = vertex_offsets[_key(b3, tol)]
        plus_a = tuple(a3[i] + offset_a[i] for i in range(3))
        plus_b = tuple(b3[i] + offset_b[i] for i in range(3))
        minus_a = tuple(a3[i] - offset_a[i] for i in range(3))
        minus_b = tuple(b3[i] - offset_b[i] for i in range(3))
        wall = ((plus_a, plus_b, minus_b), (plus_a, minus_b, minus_a))
        if any(_tri_key(tri, tol) not in solid_keys for tri in wall):
            raise GeometryError(
                "V-miter source CUTTING edge is not a physical T-solid sidewall"
            )
        selected_edges += 1
        total_flat_length += seg_length
        result.extend(wall)
    return VMiterSourceCutFaceTrial(
        source_new_v_cut_length_mm=new_length,
        selected_flat_v_cut_length_mm=total_flat_length,
        formed_boundary_edge_count=selected_edges,
        true_cut_face_triangles=tuple(result),
    )
