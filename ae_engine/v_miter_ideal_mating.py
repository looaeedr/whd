# -*- coding: utf-8 -*-
"""#3317 source-backed *ideal sharp-fold* 3D miter mating candidate.

Given two genuine, adjacent BEND segments and an already-qualified V-miter
source, rotate the two exterior flange mid-surfaces about their BEND axes.
The intersection of the two formed planes is the only ideal (zero-radius,
zero-thickness) shared cut edge.  Invert each flange rotation to obtain two
different flat V-side rays.  With unequal flange heights, clip that shared
seam to the shorter *formed* reach; never silently trim the taller flange.

CRITICAL: This is an un-certified 3D geometric candidate, NOT a CUTTING path,
a fabrication DXF, a bend-allowance/inner-radius solution, or permission to
select a fifth CornerType.  Physical sheet thickness and R / hole are source
facts but cannot be substituted into this zero-thickness analytical model.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from .sheetmetal_drawing import DrawingScene, LinePrimitive
from .sheetmetal_geometry_core import GeometryError, Vec2
from .v_miter_corner_source import (
    VMiterSourceQualification,
    VMiterReliefMode,
    qualify_v_miter_corner_source,
)

Vec3 = tuple[float, float, float]
_UNIT_Z: Vec3 = (0.0, 0.0, 1.0)
_EPS = 1e-8


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _scale(a: Vec3, t: float) -> Vec3:
    return (a[0] * t, a[1] * t, a[2] * t)


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _unit(a: Vec3, *, label: str) -> Vec3:
    length = math.hypot(*a)
    if not math.isfinite(length) or length <= _EPS:
        raise GeometryError(f"V-miter {label} is degenerate")
    return _scale(a, 1.0 / length)


def _outward_bend_axis(
    bend: LinePrimitive,
    common: Vec2,
) -> Vec3:
    """Return the ray pointing *away* from the two-line intersection.

    For this corner-specific first model, the source meeting point must be
    at exactly one endpoint of each BEND segment.  A crossing-in-the-middle
    would need a separate material-side/placement source: never guess it.
    """
    a = bend.p1
    b = bend.p2
    da = math.hypot(a.x - common.x, a.y - common.y)
    db = math.hypot(b.x - common.x, b.y - common.y)
    length = math.hypot(a.x - b.x, a.y - b.y)
    if not math.isfinite(length) or length <= _EPS:
        raise GeometryError("V-miter bend has no usable physical length")
    tolerance = max(1e-7, length * 1e-9)
    if (da <= tolerance) == (db <= tolerance):
        raise GeometryError("V-miter ideal projection needs the intersection at a bend endpoint")
    far = b if da <= tolerance else a
    return _unit((far.x - common.x, far.y - common.y, 0.0), label="bend axis")


def _outside_normal(axis: Vec3, other_axis: Vec3) -> Vec3:
    """The exterior of the wedge formed by the two adjacent BEND rays."""
    left: Vec3 = (-axis[1], axis[0], 0.0)
    return _scale(left, -1.0) if _dot(left, other_axis) > 0 else left


@dataclass(frozen=True)
class VMiterIdealMatingCandidate:
    """Read-only 3D/flat line witness; deliberately cannot authorize CUTTING."""

    source: VMiterSourceQualification
    first_flat_miter_ray: tuple[Vec2, Vec2]
    second_flat_miter_ray: tuple[Vec2, Vec2]
    formed_seam_start: Vec3
    formed_seam_end: Vec3
    formed_contact_length_mm: float
    first_flat_height_reached_mm: float
    second_flat_height_reached_mm: float
    geometry_model: str = "IDEAL_SHARP_ZERO_RADIUS_MID_SURFACE_ONLY"
    manufacturing_status: str = "V_MITER_CUTTING_UNCERTIFIED"


def project_ideal_v_miter_mating_candidate(
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
) -> VMiterIdealMatingCandidate:
    """Find both zero-radius unfolded V rays from one common formed seam.

    Same-side folds rise toward +Z.  Their signed rotations are derived
    from exterior wedge normals; callers never supply invented cut vertices.
    All source validation is delegated to the current public Engine owner.
    """
    source = qualify_v_miter_corner_source(
        scene, v_edge_bend, second_bend,
        thickness_mm=thickness_mm,
        first_flange_height_mm=first_flange_height_mm,
        second_flange_height_mm=second_flange_height_mm,
        second_fold_angle_deg=second_fold_angle_deg,
        relief_mode=relief_mode,
        relief_t_factor=relief_t_factor,
    )
    at = source.bend_intersection
    e1 = _outward_bend_axis(v_edge_bend, at)
    e2 = _outward_bend_axis(second_bend, at)
    # Parallel lines have no wedge / unique exterior; reject *normalised*
    # near-parallel axes even when long source segments mask degeneracy.
    cross_z = e1[0] * e2[1] - e1[1] * e2[0]
    if abs(cross_z) <= _EPS:
        raise GeometryError("V-miter source bend rays form no usable corner wedge")
    n1 = _outside_normal(e1, e2)
    n2 = _outside_normal(e2, e1)
    # 90-degree first fold is vertical; second is operator-specified.
    theta = math.radians(source.second_fold_angle_deg)
    b1: Vec3 = _UNIT_Z
    b2 = _add(_scale(n2, math.cos(theta)), _scale(_UNIT_Z, math.sin(theta)))
    # Each formed flange plane spans its unchanged bend axis e_i and its
    # rotated outward in-plane direction b_i.
    plane_normal_1 = _cross(e1, b1)
    plane_normal_2 = _cross(e2, b2)
    seam_direction = _unit(
        _cross(plane_normal_1, plane_normal_2), label="formed plane intersection",
    )
    if _dot(seam_direction, b1) < 0:
        seam_direction = _scale(seam_direction, -1.0)
    rise_1 = _dot(seam_direction, b1)
    rise_2 = _dot(seam_direction, b2)
    if min(rise_1, rise_2) <= _EPS:
        raise GeometryError("V-miter formed planes have no common outward contact ray")
    # Trim contact to the smaller *formed* flange reach, not the smaller
    # nominal height.  Unequal or non-90-degree flanges give asymmetric rays.
    reach = min(
        source.first_flange_height_mm / rise_1,
        source.second_flange_height_mm / rise_2,
    )
    if not math.isfinite(reach) or reach <= _EPS:
        raise GeometryError("V-miter formed contact is degenerate")

    def flat_endpoint(axis: Vec3, outward: Vec3, formed_outward: Vec3) -> Vec2:
        axial = _dot(seam_direction, axis) * reach
        height = _dot(seam_direction, formed_outward) * reach
        return Vec2(
            at.x + axis[0] * axial + outward[0] * height,
            at.y + axis[1] * axial + outward[1] * height,
        )

    first_end = flat_endpoint(e1, n1, b1)
    second_end = flat_endpoint(e2, n2, b2)
    if not all(math.isfinite(x) for x in (
        first_end.x, first_end.y, second_end.x, second_end.y,
    )):
        raise GeometryError("V-miter ideal unfolded rays are non-finite")
    formed_origin: Vec3 = (at.x, at.y, 0.0)
    formed_end = _add(formed_origin, _scale(seam_direction, reach))
    return VMiterIdealMatingCandidate(
        source=source,
        first_flat_miter_ray=(at, first_end),
        second_flat_miter_ray=(at, second_end),
        formed_seam_start=formed_origin,
        formed_seam_end=formed_end,
        formed_contact_length_mm=reach,
        first_flat_height_reached_mm=rise_1 * reach,
        second_flat_height_reached_mm=rise_2 * reach,
    )
