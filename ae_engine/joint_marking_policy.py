# -*- coding: utf-8 -*-
"""Pure Joint Placement MARKING policy, diagnostics, coverage and stable identity core.

This module is intentionally dormant foundation.  It does not mutate FinalScene,
serialize output, or activate any manufacturing marking policy.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from shapely.geometry import Polygon

from .contracts import (
    ContactSpanValidationResult,
    JointMarkingPolicy,
    JointMarkingPolicyLookupResult,
    PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES,
    ResolvedPhysicalMatingRegion,
)


MARKING_DIAGNOSTIC_CODES = frozenset(
    {
        "POLICY_NOT_FOUND",
        "LOCATOR_MISSING",
        "ATTACHED_MISSING",
        "STALE_STABLE_ID",
        "PLACEMENT_UNRESOLVED",
        "MATING_REGION_UNRESOLVED",
        "CONTACT_NOT_FOUND",
        "CONTACT_NOT_COPLANAR",
        "CONTACT_NORMAL_MISMATCH",
        "CONTACT_SPAN_BELOW_MINIMUM",
        "CONTACT_NOT_UNIQUE",
        "PENETRATION_NOT_CONTACT",
        "OVERLAP_AUTHORITY_MISSING",
        "BOUNDARY_FRAME_UNRESOLVED",
        "FOOTPRINT_MODE_MISMATCH",
        "BACKPROJECTION_FAILED",
        "BOUNDARY_PAIR_AMBIGUOUS",
        "MARK_OUTSIDE_FINAL_MATERIAL",
    }
)


def _nonblank(value, label):
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} must be nonblank")
    return text


@dataclass(frozen=True)
class JointMarkingPolicyRegistry:
    """Deterministic registry with explicit no-policy and explicit-miss semantics."""

    policies: tuple[JointMarkingPolicy, ...] = ()

    def __post_init__(self):
        rows = tuple(self.policies or ())
        object.__setattr__(self, "policies", rows)
        seen = set()
        for policy in rows:
            if not isinstance(policy, JointMarkingPolicy):
                raise TypeError("registry policies must be JointMarkingPolicy")
            key = str(policy.policy_id)
            if key in seen:
                raise ValueError(f"duplicate JointMarkingPolicy id: {key}")
            seen.add(key)

    def resolve(
        self,
        *,
        policy_id: str | None = None,
        locator_selector: str | None = None,
        attached_selector: str | None = None,
    ) -> JointMarkingPolicyLookupResult:
        explicit = str(policy_id or "").strip()
        enabled = tuple(policy for policy in self.policies if bool(policy.enabled))

        if explicit:
            for policy in enabled:
                if str(policy.policy_id) == explicit:
                    return JointMarkingPolicyLookupResult(
                        status="MATCHED",
                        policy=policy,
                        diagnostic_code=None,
                        evidence={"selection": "EXPLICIT_POLICY_ID"},
                    )
            return JointMarkingPolicyLookupResult(
                status="EXPLICIT_POLICY_ID_MISSING",
                policy=None,
                diagnostic_code="POLICY_NOT_FOUND",
                evidence={"requested_policy_id": explicit},
            )

        locator = str(locator_selector or "").strip()
        attached = str(attached_selector or "").strip()
        matches = tuple(
            policy
            for policy in enabled
            if str(policy.locator_selector) == locator
            and str(policy.attached_selector) == attached
        )
        if not matches:
            return JointMarkingPolicyLookupResult(
                status="NO_POLICY_REQUIRED",
                policy=None,
                diagnostic_code=None,
                evidence={"selection": "SEMANTIC_SELECTORS"},
            )
        if len(matches) != 1:
            raise ValueError(
                "ambiguous JointMarkingPolicy selector match; registry must be unique"
            )
        return JointMarkingPolicyLookupResult(
            status="MATCHED",
            policy=matches[0],
            diagnostic_code=None,
            evidence={"selection": "SEMANTIC_SELECTORS"},
        )


def stable_joint_mark_id(
    policy_id: str,
    locator_part_id: str,
    attached_part_id: str,
    boundary_role: str,
) -> str:
    """Return semantic stable identity independent of derived geometry coordinates."""

    rows = (
        _nonblank(policy_id, "policy_id"),
        _nonblank(locator_part_id, "locator_part_id"),
        _nonblank(attached_part_id, "attached_part_id"),
        _nonblank(boundary_role, "boundary_role"),
    )
    if rows[3] not in {"SIDE_NEGATIVE", "SIDE_POSITIVE"}:
        raise ValueError(f"unsupported boundary role: {rows[3]}")
    return "jointmark:" + ":".join(rows)


def _sub3(a, b):
    return tuple(float(a[i]) - float(b[i]) for i in range(3))


def _dot3(a, b):
    return sum(float(a[i]) * float(b[i]) for i in range(3))


def _cross3(a, b):
    return (
        float(a[1]) * float(b[2]) - float(a[2]) * float(b[1]),
        float(a[2]) * float(b[0]) - float(a[0]) * float(b[2]),
        float(a[0]) * float(b[1]) - float(a[1]) * float(b[0]),
    )


def _norm3(v):
    return math.sqrt(_dot3(v, v))


def _normalize3(v, tolerance):
    length = _norm3(v)
    if length <= float(tolerance):
        raise ValueError("degenerate supporting-plane normal")
    return tuple(float(value) / length for value in v)


def _plane_basis(normal):
    tolerance = float(
        PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.boundary_separation_tolerance
    )
    n = _normalize3(normal, tolerance)
    helper = (1.0, 0.0, 0.0)
    if abs(_dot3(n, helper)) > 0.9:
        helper = (0.0, 1.0, 0.0)
    u = _normalize3(_cross3(n, helper), tolerance)
    v = _normalize3(_cross3(n, u), tolerance)
    return u, v


def _project_polygon(points, origin, u, v):
    projected = []
    for raw in tuple(points or ()):
        if len(tuple(raw)) != 3:
            raise ValueError("world polygon point must be 3D")
        delta = _sub3(tuple(float(x) for x in raw), origin)
        projected.append((_dot3(delta, u), _dot3(delta, v)))
    if len(projected) < 3:
        raise ValueError("bounded region requires at least three points")
    polygon = Polygon(projected)
    epsilon = float(
        PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.polygon_robustness_epsilon
    )
    if not polygon.is_valid or polygon.area <= epsilon:
        raise ValueError("bounded region polygon is invalid")
    return polygon


def validate_expected_region_coverage(
    expected_region: ResolvedPhysicalMatingRegion,
    overlap_world,
) -> ContactSpanValidationResult:
    """Validate authoritative EXPECTED_REGION_COVERAGE without product mm thresholds."""

    if not isinstance(expected_region, ResolvedPhysicalMatingRegion):
        return ContactSpanValidationResult(
            status="SKIPPED_FAIL_CLOSED",
            diagnostic_code="OVERLAP_AUTHORITY_MISSING",
            evidence={"reason": "expected mating region authority is missing"},
        )

    try:
        plane = tuple(expected_region.supporting_plane or ())
        if len(plane) != 2:
            raise ValueError("expected region supporting plane is unresolved")
        origin = tuple(float(x) for x in plane[0])
        normal = tuple(float(x) for x in expected_region.outward_normal)
        u, v = _plane_basis(normal)
        expected = _project_polygon(expected_region.world_polygon, origin, u, v)
        overlap = _project_polygon(overlap_world, origin, u, v)
    except (TypeError, ValueError) as exc:
        return ContactSpanValidationResult(
            status="SKIPPED_FAIL_CLOSED",
            diagnostic_code="OVERLAP_AUTHORITY_MISSING",
            evidence={"reason": str(exc)},
        )

    epsilon = float(
        PRODUCTION_ASSEMBLY_GEOMETRY_TOLERANCES.polygon_robustness_epsilon
    )
    missing = expected.difference(overlap)
    if (not missing.is_empty and float(missing.area) > epsilon) or not overlap.intersects(expected):
        return ContactSpanValidationResult(
            status="SKIPPED_FAIL_CLOSED",
            diagnostic_code="CONTACT_SPAN_BELOW_MINIMUM",
            evidence={
                "contract": "EXPECTED_REGION_COVERAGE",
                "expected_area": float(expected.area),
                "covered_area": float(expected.intersection(overlap).area),
                "missing_area": float(missing.area),
            },
        )

    covered = expected.intersection(overlap)
    if covered.is_empty or float(covered.area) <= epsilon:
        return ContactSpanValidationResult(
            status="SKIPPED_FAIL_CLOSED",
            diagnostic_code="CONTACT_SPAN_BELOW_MINIMUM",
            evidence={"contract": "EXPECTED_REGION_COVERAGE"},
        )

    return ContactSpanValidationResult(
        status="COVERED",
        diagnostic_code=None,
        evidence={
            "contract": "EXPECTED_REGION_COVERAGE",
            "expected_area": float(expected.area),
            "covered_area": float(covered.area),
        },
    )
