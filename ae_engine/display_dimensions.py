# -*- coding: utf-8 -*-
"""Shared operator-facing finished-dimension provider for 2D and 3D."""
from __future__ import annotations

import math

from .sheetmetal_geometry import box_body_height_from_corner_policies


def _number(value, default=0.0):
    if isinstance(value, bool):
        return float(default)
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return float(default)
    return result if math.isfinite(result) else float(default)


def _preferred_number(*values, default=0.0):
    """Fallback per field to another authoritative finite input, not zero."""
    for value in values:
        if isinstance(value, bool):
            continue
        try:
            result = float(value)
        except (TypeError, ValueError, OverflowError):
            continue
        if math.isfinite(result):
            return result
    return float(default)


def folded_outside_envelope(triangles, thickness):
    """Return compensated outside AABB for an already-folded FinalScene mesh."""
    # A FinalScene vertex must be a real physical XYZ before becoming a
    # display or manufacturing CHECK dimension. float(True) is not 1 mm.
    try:
        source_tris = [tuple(tri) for tri in (triangles or ())]
        source_tris = [tri for tri in source_tris if len(tri) >= 3]
        if not source_tris:
            return None
        tris = []
        for tri in source_tris:
            raw_points = tuple(tuple(pt) for pt in tri[:3])
            if any(len(pt) != 3 or any(isinstance(v, bool) for v in pt)
                   for pt in raw_points):
                raise ValueError("FOLDED_ENVELOPE_INVALID_WORLD_MESH")
            xyz = tuple(tuple(float(v) for v in pt) for pt in raw_points)
            if not all(math.isfinite(v) for pt in xyz for v in pt):
                raise ValueError("FOLDED_ENVELOPE_INVALID_WORLD_MESH")
            tris.append(xyz)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("FOLDED_ENVELOPE_INVALID_WORLD_MESH") from exc
    points = [pt for tri in tris for pt in tri]
    mins = [min(point[axis] for point in points) for axis in range(3)]
    maxs = [max(point[axis] for point in points) for axis in range(3)]
    normal_extent = [0.0, 0.0, 0.0]
    for a, b, c in tris:
        u = tuple(b[i] - a[i] for i in range(3))
        v = tuple(c[i] - a[i] for i in range(3))
        n = (
            u[1] * v[2] - u[2] * v[1],
            u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0],
        )
        mag = math.sqrt(sum(value * value for value in n))
        if mag <= 1e-12:
            continue
        for axis in range(3):
            normal_extent[axis] = max(normal_extent[axis], abs(n[axis] / mag))
    t = max(0.0, _number(thickness, 0.0))
    bounds = tuple(
        (mins[axis] - t * normal_extent[axis], maxs[axis] + t * normal_extent[axis])
        for axis in range(3)
    )
    dims = tuple(hi - lo for lo, hi in bounds)
    return dims, bounds


def resolve_operator_finished_dimensions(
    part_key,
    *,
    snapshot=None,
    settings=None,
    triangles=None,
    thickness=None,
    head_corner_policy=None,
    tail_corner_policy=None,
    fallback_dimensions=None,
):
    """Resolve one operator-facing finished-dimension tuple from shared inputs.

    Already-folded mesh measurement wins.  Snapshot fallback mirrors the legacy
    Phase6 display contract but now lives in one engine-layer provider.
    """
    key = str(part_key or "")
    snapshot = dict(snapshot or {})
    settings = dict(settings or {})
    t = _preferred_number(thickness, settings.get("t"), snapshot.get("t"), default=2.0)

    if triangles:
        envelope = folded_outside_envelope(triangles, t)
        if envelope is not None:
            measured, _bounds = envelope
            if key == "box_body":
                return tuple(float(value) for value in measured)
            return float(measured[0]), float(measured[1])

    if fallback_dimensions is not None:
        return tuple(float(value) for value in fallback_dimensions)

    dims = dict((snapshot.get("part_dimensions") or {}).get(key, {}) or {})
    if key == "box_body":
        w = _preferred_number(settings.get("w"), snapshot.get("w"))
        h = _preferred_number(settings.get("h"), snapshot.get("h"))
        d = _preferred_number(settings.get("d"), snapshot.get("d"))
        if head_corner_policy is not None and tail_corner_policy is not None:
            h = box_body_height_from_corner_policies(
                h, t,
                head_corner_policy=head_corner_policy,
                tail_corner_policy=tail_corner_policy,
            )
        return float(w), float(h), float(d)

    if dims.get("width") and dims.get("height"):
        return float(dims["width"]), float(dims["height"])
    if key in {"head", "tail"}:
        return _preferred_number(snapshot.get("w"), settings.get("w")), _preferred_number(snapshot.get("d"), settings.get("d"))
    return None
