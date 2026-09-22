# -*- coding: utf-8 -*-
"""Geometry-neutral legal coplanar contact resolution.

This module consumes already-resolved authoritative physical mating regions.
It owns no renderer, DXF verifier, UI state, fixture expectation, or collision
probe.  Coplanarity is decided from the two actual supporting planes before
their bounded faces are projected into one computational contact-plane basis.
"""
from __future__ import annotations

import math

from shapely.geometry import Polygon

from .contracts import (
    AssemblyGeometryToleranceContract,
    LegalContactResult,
    PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES,
    ResolvedLegalContact,
    ResolvedPhysicalMatingRegion,
    TrueSolidPenetrationEvidence,
)


def _sub(a, b):
    return tuple(float(a[i]) - float(b[i]) for i in range(3))


def _add(a, b):
    return tuple(float(a[i]) + float(b[i]) for i in range(3))


def _scale(v, k):
    return tuple(float(v[i]) * float(k) for i in range(3))


def _dot(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def _cross(a, b):
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _norm(v):
    return math.sqrt(sum(float(value) * float(value) for value in v))


def _normalize(v, *, tolerance):
    mag = _norm(v)
    if mag <= float(tolerance):
        raise ValueError("physical mating-region normal is degenerate")
    return tuple(float(value) / mag for value in v)


def _plane_basis(normal, *, tolerance):
    """Return an arbitrary stable orthonormal basis for overlap computation only.

    This basis has no semantic SIDE_NEGATIVE/SIDE_POSITIVE meaning.  T2 owns the
    contact-local signed flat basis used for marking roles.
    """
    n = _normalize(normal, tolerance=tolerance)
    reference = min(
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        key=lambda axis: abs(_dot(axis, n)),
    )
    u = _normalize(_cross(reference, n), tolerance=tolerance)
    v = _normalize(_cross(n, u), tolerance=tolerance)
    return u, v


def _project_polygon(points, origin, u, v):
    return tuple(
        (
            _dot(_sub(point, origin), u),
            _dot(_sub(point, origin), v),
        )
        for point in tuple(points or ())
    )


def _world_polygon_from_plane(polygon, origin, u, v):
    coords = tuple(polygon.exterior.coords)
    return tuple(
        _add(origin, _add(_scale(u, float(x)), _scale(v, float(y))))
        for x, y in coords[:-1]
    )


def _fail(code, **evidence):
    return LegalContactResult(
        status="SKIPPED_FAIL_CLOSED",
        diagnostic_code=str(code),
        contact=None,
        evidence=dict(evidence),
    )


def resolve_legal_coplanar_contact(
    locator_region: ResolvedPhysicalMatingRegion,
    attached_region: ResolvedPhysicalMatingRegion,
    *,
    tolerances: AssemblyGeometryToleranceContract = PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES,
    penetration_evidence: TrueSolidPenetrationEvidence | None = None,
    allowed_overlap_mode: str = "NONE",
) -> LegalContactResult:
    """Resolve one policy-selected region pair as legal contact or fail closed.

    Normative order:
      1. canonicalize both outward normals;
      2. enforce norm(N_locator + N_attached) residual;
      3. compare the two actual supporting planes;
      4. reject authoritative through-thickness / positive-volume penetration;
      5. only then project the bounded faces to compute positive-area overlap.
    """
    if not isinstance(locator_region, ResolvedPhysicalMatingRegion):
        return _fail("MATING_REGION_UNRESOLVED", side="LOCATOR")
    if not isinstance(attached_region, ResolvedPhysicalMatingRegion):
        return _fail("MATING_REGION_UNRESOLVED", side="ATTACHED")
    if not isinstance(tolerances, AssemblyGeometryToleranceContract):
        raise TypeError("tolerances must be AssemblyGeometryToleranceContract")

    boundary_tol = float(tolerances.boundary_separation_tolerance)
    locator_normal = _normalize(locator_region.outward_normal, tolerance=boundary_tol)
    attached_normal = _normalize(attached_region.outward_normal, tolerance=boundary_tol)
    normal_residual = _norm(_add(locator_normal, attached_normal))
    normal_limit = float(tolerances.opposed_normal_residual_tolerance)
    if normal_residual > normal_limit:
        return _fail(
            "CONTACT_NORMAL_MISMATCH",
            normal_residual=normal_residual,
            normal_residual_limit=normal_limit,
            tolerance_provenance=tolerances.provenance,
            tolerance_revision=int(tolerances.revision),
        )

    locator_plane_point = tuple(float(v) for v in locator_region.supporting_plane[0])
    attached_plane_point = tuple(float(v) for v in attached_region.supporting_plane[0])

    # Coplanarity compares the two actual authoritative supporting planes.
    # The attached geometry is not projected onto the locator plane before this.
    plane_separation = abs(
        _dot(_sub(attached_plane_point, locator_plane_point), locator_normal)
    )
    coplanar_limit = float(tolerances.coplanar_distance_tolerance)
    if plane_separation > coplanar_limit:
        return _fail(
            "CONTACT_NOT_COPLANAR",
            plane_separation=plane_separation,
            coplanar_distance_limit=coplanar_limit,
            tolerance_provenance=tolerances.provenance,
            tolerance_revision=int(tolerances.revision),
        )

    penetration = penetration_evidence
    if (
        penetration is not None
        and bool(penetration.detected)
        and (bool(penetration.through_thickness) or bool(penetration.positive_volume))
    ):
        return _fail(
            "PENETRATION_NOT_CONTACT",
            penetration_source=str(penetration.source or ""),
            through_thickness=bool(penetration.through_thickness),
            positive_volume=bool(penetration.positive_volume),
            penetration_evidence=penetration.evidence,
        )

    if str(allowed_overlap_mode or "NONE").upper() != "NONE":
        return _fail(
            "OVERLAP_AUTHORITY_MISSING",
            requested_overlap_mode=str(allowed_overlap_mode),
        )

    locator_points = tuple(locator_region.world_polygon or ())
    attached_points = tuple(attached_region.world_polygon or ())
    if len(locator_points) < 3 or len(attached_points) < 3:
        return _fail("CONTACT_NOT_FOUND", reason="BOUNDED_FACE_MISSING")

    u, v = _plane_basis(locator_normal, tolerance=boundary_tol)
    locator_2d = Polygon(_project_polygon(locator_points, locator_plane_point, u, v))
    attached_2d = Polygon(_project_polygon(attached_points, locator_plane_point, u, v))
    if not locator_2d.is_valid:
        locator_2d = locator_2d.buffer(0)
    if not attached_2d.is_valid:
        attached_2d = attached_2d.buffer(0)
    if locator_2d.is_empty or attached_2d.is_empty:
        return _fail("CONTACT_NOT_FOUND", reason="EMPTY_BOUNDED_FACE")

    overlap = locator_2d.intersection(attached_2d)
    overlap_epsilon = float(tolerances.polygon_robustness_epsilon)
    if overlap.is_empty or float(getattr(overlap, "area", 0.0)) <= overlap_epsilon:
        return _fail(
            "CONTACT_NOT_FOUND",
            overlap_area=float(getattr(overlap, "area", 0.0)),
            polygon_robustness_epsilon=overlap_epsilon,
        )
    if str(getattr(overlap, "geom_type", "")) != "Polygon":
        return _fail(
            "CONTACT_NOT_UNIQUE",
            overlap_geometry_type=str(getattr(overlap, "geom_type", "")),
        )

    overlap_world = _world_polygon_from_plane(
        overlap, locator_plane_point, u, v
    )
    evidence = {
        "normal_residual": float(normal_residual),
        "normal_residual_limit": normal_limit,
        "plane_separation": float(plane_separation),
        "coplanar_distance_limit": coplanar_limit,
        "overlap_area": float(overlap.area),
        "tolerance_provenance": str(tolerances.provenance),
        "tolerance_revision": int(tolerances.revision),
        "allowed_overlap_mode": "NONE",
    }
    contact = ResolvedLegalContact(
        locator_part_id=str(locator_region.part_id),
        attached_part_id=str(attached_region.part_id),
        locator_region=locator_region,
        attached_region=attached_region,
        contact_plane=(locator_plane_point, locator_normal),
        locator_outward_normal=locator_normal,
        attached_outward_normal=attached_normal,
        overlap_world=overlap_world,
        locator_flat_mapping=locator_region.flat_mapping,
        evidence=evidence,
    )
    return LegalContactResult(
        status="LEGAL_CONTACT",
        diagnostic_code=None,
        contact=contact,
        evidence=evidence,
    )
