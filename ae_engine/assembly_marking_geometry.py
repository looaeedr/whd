# -*- coding: utf-8 -*-
"""Neutral geometry for Joint Placement MARKING contact frames and projection."""
from __future__ import annotations

import math

from shapely.geometry import Polygon

from .contracts import (
    ContactLocalFrame,
    ContactLocalFrameResult,
    LocatorBackprojectionResult,
    PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES,
    ResolvedLegalContact,
    SemanticBoundary,
    SemanticBoundaryPair,
    SemanticBoundaryPairResult,
)

CONTACT_LOCAL_FRAME_VERSION = "CONTACT_LOCAL_FRAME_V1"


def _add(a, b):
    return tuple(float(a[i]) + float(b[i]) for i in range(3))


def _sub(a, b):
    return tuple(float(a[i]) - float(b[i]) for i in range(3))


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


def _normalize(v, tolerance):
    mag = _norm(v)
    if mag <= float(tolerance):
        raise ValueError("degenerate vector")
    return tuple(float(value) / mag for value in v)


def _flat_axis_vector(axis):
    table = {
        "+X": (1.0, 0.0),
        "-X": (-1.0, 0.0),
        "+Y": (0.0, 1.0),
        "-Y": (0.0, -1.0),
    }
    key = str(axis or "").strip().upper()
    if key not in table:
        raise ValueError(f"unsupported signed flat axis: {axis!r}")
    return key, table[key]


def _authoritative_locator_mapping(contact):
    """Return the locator region's canonical flat mapping and reject stale copies."""
    region = getattr(contact, "locator_region", None)
    mapping = tuple(getattr(region, "flat_mapping", ()) or ())
    if not mapping:
        raise ValueError("locator authoritative flat mapping is missing")

    copied = tuple(getattr(contact, "locator_flat_mapping", ()) or ())
    if copied and copied != mapping:
        raise ValueError(
            "legal-contact locator mapping copy disagrees with locator region authority"
        )
    return mapping


def _mapped_axis_vector(record, axis):
    flat = tuple(getattr(record, "flat", ()) or ())
    world = tuple(getattr(record, "world", ()) or ())
    if len(flat) != 3 or len(world) != 3:
        raise ValueError("authoritative locator mapping record must be triangular")

    _key, desired = _flat_axis_vector(axis)
    p0, p1, p2 = flat
    e1 = (float(p1[0]) - float(p0[0]), float(p1[1]) - float(p0[1]))
    e2 = (float(p2[0]) - float(p0[0]), float(p2[1]) - float(p0[1]))
    det = e1[0] * e2[1] - e1[1] * e2[0]
    eps = float(PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.polygon_robustness_epsilon)
    if abs(det) <= eps:
        raise ValueError("degenerate authoritative locator flat triangle")

    a = (desired[0] * e2[1] - desired[1] * e2[0]) / det
    b = (e1[0] * desired[1] - e1[1] * desired[0]) / det

    w0, w1, w2 = world
    w1d = _sub(w1, w0)
    w2d = _sub(w2, w0)
    return _add(_scale(w1d, a), _scale(w2d, b))


def _project_to_plane(v, normal):
    return _sub(v, _scale(normal, _dot(v, normal)))


def _mapped_semantic_axis(mapping, axis, normal, *, remove_axis=None):
    tol = float(PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance)
    agreement = float(
        PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.flat_world_mapping_tolerance
    )
    candidates = []
    for record in tuple(mapping or ()):
        vector = _project_to_plane(_mapped_axis_vector(record, axis), normal)
        if remove_axis is not None:
            vector = _sub(vector, _scale(remove_axis, _dot(vector, remove_axis)))
        candidates.append(_normalize(vector, tol))

    if not candidates:
        raise ValueError("authoritative locator mapping is empty")

    owner = candidates[0]
    for candidate in candidates[1:]:
        if _dot(owner, candidate) < 1.0 - agreement:
            raise ValueError("authoritative locator mapping does not define one signed panel basis")
    return owner


def _overlap_centroid(points, longitudinal, cross_axis):
    rows = tuple(tuple(float(v) for v in point) for point in tuple(points or ()))
    if len(rows) < 3:
        raise ValueError("legal contact overlap has no bounded polygon")
    anchor = rows[0]
    coords = [
        (
            _dot(_sub(point, anchor), longitudinal),
            _dot(_sub(point, anchor), cross_axis),
        )
        for point in rows
    ]
    polygon = Polygon(coords)
    if polygon.is_empty or not polygon.is_valid or float(polygon.area) <= 0.0:
        raise ValueError("legal contact overlap polygon is invalid")
    center = polygon.centroid
    return _add(
        anchor,
        _add(
            _scale(longitudinal, float(center.x)),
            _scale(cross_axis, float(center.y)),
        ),
    )


def _frame_fail(reason):
    return ContactLocalFrameResult(
        status="SKIPPED_FAIL_CLOSED",
        diagnostic_code="BOUNDARY_FRAME_UNRESOLVED",
        frame=None,
        evidence={"reason": str(reason)},
    )


def resolve_contact_local_frame(
    contact: ResolvedLegalContact,
    *,
    longitudinal_flat_axis: str,
    cross_flat_axis: str,
) -> ContactLocalFrameResult:
    """Resolve CONTACT_LOCAL_FRAME_V1 from one signed locator flat basis."""
    try:
        if not isinstance(contact, ResolvedLegalContact):
            raise ValueError("legal contact is unresolved")
        mapping = _authoritative_locator_mapping(contact)

        longitudinal_key, longitudinal_flat = _flat_axis_vector(
            longitudinal_flat_axis
        )
        cross_key, cross_flat = _flat_axis_vector(cross_flat_axis)
        flat_dot = (
            longitudinal_flat[0] * cross_flat[0]
            + longitudinal_flat[1] * cross_flat[1]
        )
        if abs(flat_dot) > float(
            PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.flat_world_mapping_tolerance
        ):
            raise ValueError("signed flat axes must be orthogonal")

        tol = float(
            PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance
        )
        normal = _normalize(contact.locator_outward_normal, tol)
        longitudinal = _mapped_semantic_axis(
            mapping, longitudinal_key, normal
        )
        cross_axis = _mapped_semantic_axis(
            mapping,
            cross_key,
            normal,
            remove_axis=longitudinal,
        )
        reference_cross = _normalize(_cross(normal, longitudinal), tol)
        orientation_dot = _dot(cross_axis, reference_cross)
        if abs(orientation_dot) <= tol:
            raise ValueError("signed flat basis parity is unresolved")
        parity = 1 if orientation_dot > 0.0 else -1
        origin = _overlap_centroid(
            contact.overlap_world,
            longitudinal,
            cross_axis,
        )
        frame = ContactLocalFrame(
            frame_version=CONTACT_LOCAL_FRAME_VERSION,
            origin=origin,
            normal=normal,
            longitudinal=longitudinal,
            cross=cross_axis,
            handedness_parity=parity,
            basis_part="LOCATOR",
            longitudinal_flat_axis=longitudinal_key,
            cross_flat_axis=cross_key,
        )
        return ContactLocalFrameResult(
            status="RESOLVED",
            diagnostic_code=None,
            frame=frame,
            evidence={
                "basis_part": "LOCATOR",
                "mapping_record_count": len(mapping),
                "handedness_parity": parity,
            },
        )
    except (TypeError, ValueError) as exc:
        return _frame_fail(exc)


def _support_boundary(points, frame, target_cross):
    tol = float(PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance)
    rows = tuple(tuple(float(v) for v in point) for point in tuple(points or ()))
    intervals = []
    endpoint_rows = []
    for index, a in enumerate(rows):
        b = rows[(index + 1) % len(rows)]
        ca = _dot(_sub(a, frame.origin), frame.cross)
        cb = _dot(_sub(b, frame.origin), frame.cross)
        if abs(ca - target_cross) > tol or abs(cb - target_cross) > tol:
            continue
        la = _dot(_sub(a, frame.origin), frame.longitudinal)
        lb = _dot(_sub(b, frame.origin), frame.longitudinal)
        if abs(lb - la) <= tol:
            continue
        intervals.append((min(la, lb), max(la, lb)))
        endpoint_rows.extend(((la, a), (lb, b)))

    if not intervals:
        raise ValueError("semantic support boundary is absent")
    intervals.sort()
    merged_start, merged_end = intervals[0]
    for start, end in intervals[1:]:
        if start > merged_end + tol:
            raise ValueError("semantic support boundary is fragmented")
        merged_end = max(merged_end, end)

    minimum = min(endpoint_rows, key=lambda row: row[0])
    maximum = max(endpoint_rows, key=lambda row: row[0])
    if maximum[0] - minimum[0] <= tol:
        raise ValueError("semantic support boundary has no longitudinal span")
    return (
        tuple(float(v) for v in minimum[1]),
        tuple(float(v) for v in maximum[1]),
    )


def resolve_side_boundary_pair(
    contact: ResolvedLegalContact,
    frame: ContactLocalFrame,
) -> SemanticBoundaryPairResult:
    """Extract semantic SIDE_NEGATIVE/SIDE_POSITIVE support boundaries."""
    try:
        if not isinstance(contact, ResolvedLegalContact):
            raise ValueError("legal contact is unresolved")
        if not isinstance(frame, ContactLocalFrame):
            raise ValueError("contact-local frame is unresolved")
        rows = tuple(contact.overlap_world or ())
        if len(rows) < 3:
            raise ValueError("legal contact overlap is unresolved")

        values = tuple(
            _dot(_sub(point, frame.origin), frame.cross)
            for point in rows
        )
        negative_cross = min(values)
        positive_cross = max(values)
        tol = float(
            PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance
        )
        if positive_cross - negative_cross <= tol:
            raise ValueError("semantic side separation is ambiguous")

        negative_segment = _support_boundary(rows, frame, negative_cross)
        positive_segment = _support_boundary(rows, frame, positive_cross)
        pair = SemanticBoundaryPair(
            negative=SemanticBoundary(
                role="SIDE_NEGATIVE",
                world_segment=negative_segment,
                signed_cross=float(negative_cross),
            ),
            positive=SemanticBoundary(
                role="SIDE_POSITIVE",
                world_segment=positive_segment,
                signed_cross=float(positive_cross),
            ),
        )
        return SemanticBoundaryPairResult(
            status="RESOLVED",
            diagnostic_code=None,
            pair=pair,
            evidence={
                "frame_version": frame.frame_version,
                "handedness_parity": frame.handedness_parity,
            },
        )
    except (TypeError, ValueError) as exc:
        return SemanticBoundaryPairResult(
            status="SKIPPED_FAIL_CLOSED",
            diagnostic_code="BOUNDARY_PAIR_AMBIGUOUS",
            pair=None,
            evidence={"reason": str(exc)},
        )


def _world_point_to_flat(point, record):
    tol = float(PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance)
    flat_tol = float(PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.flat_world_mapping_tolerance)
    world = tuple(getattr(record, "world", ()) or ())
    flat = tuple(getattr(record, "flat", ()) or ())
    if len(world) != 3 or len(flat) != 3:
        return None

    a, b, c = world
    v0 = _sub(b, a)
    v1 = _sub(c, a)
    v2 = _sub(point, a)
    d00 = _dot(v0, v0)
    d01 = _dot(v0, v1)
    d11 = _dot(v1, v1)
    d20 = _dot(v2, v0)
    d21 = _dot(v2, v1)
    denom = d00 * d11 - d01 * d01
    if abs(denom) <= float(
        PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.polygon_robustness_epsilon
    ):
        return None
    beta = (d11 * d20 - d01 * d21) / denom
    gamma = (d00 * d21 - d01 * d20) / denom
    alpha = 1.0 - beta - gamma
    weights = (alpha, beta, gamma)
    if any(value < -flat_tol or value > 1.0 + flat_tol for value in weights):
        return None

    reconstructed = tuple(
        alpha * float(a[i])
        + beta * float(b[i])
        + gamma * float(c[i])
        for i in range(3)
    )
    if _norm(_sub(point, reconstructed)) > tol:
        return None

    u = (
        alpha * float(flat[0][0])
        + beta * float(flat[1][0])
        + gamma * float(flat[2][0])
    )
    v = (
        alpha * float(flat[0][1])
        + beta * float(flat[1][1])
        + gamma * float(flat[2][1])
    )
    return (u, v)


def backproject_locator_world_points(
    contact: ResolvedLegalContact,
    points,
) -> LocatorBackprojectionResult:
    """Backproject contact points through locator authoritative mapping only."""
    try:
        mapping = _authoritative_locator_mapping(contact)
    except (TypeError, ValueError) as exc:
        return LocatorBackprojectionResult(
            status="SKIPPED_FAIL_CLOSED",
            diagnostic_code="BACKPROJECTION_FAILED",
            flat_points=(),
            evidence={"reason": str(exc)},
        )

    tolerance = float(
        PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.flat_world_mapping_tolerance
    )
    resolved = []
    for raw in tuple(points or ()):
        point = tuple(float(v) for v in raw)
        candidates = []
        for record in mapping:
            mapped = _world_point_to_flat(point, record)
            if mapped is not None:
                candidates.append(mapped)
        if not candidates:
            return LocatorBackprojectionResult(
                status="SKIPPED_FAIL_CLOSED",
                diagnostic_code="BACKPROJECTION_FAILED",
                flat_points=(),
                evidence={
                    "reason": "point is outside locator authoritative mapping",
                    "world_point": point,
                    "mapping_record_count": len(mapping),
                },
            )

        owner = candidates[0]
        for candidate in candidates[1:]:
            distance = math.hypot(
                float(candidate[0]) - float(owner[0]),
                float(candidate[1]) - float(owner[1]),
            )
            if distance > tolerance:
                return LocatorBackprojectionResult(
                    status="SKIPPED_FAIL_CLOSED",
                    diagnostic_code="BACKPROJECTION_FAILED",
                    flat_points=(),
                    evidence={"reason": "locator mapping is not unique at point"},
                )
        resolved.append((float(owner[0]), float(owner[1])))

    return LocatorBackprojectionResult(
        status="RESOLVED",
        diagnostic_code=None,
        flat_points=tuple(resolved),
        evidence={
            "mapping_owner": "LOCATOR",
            "mapping_record_count": len(mapping),
        },
    )
