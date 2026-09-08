# -*- coding: utf-8 -*-
"""Shared operator-facing finished-dimension provider for 2D and 3D."""
from __future__ import annotations

import math

from .sheetmetal_geometry import box_body_height_from_corner_policies


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def folded_outside_envelope(triangles, thickness):
    """Return compensated outside AABB for an already-folded FinalScene mesh."""
    tris = [tuple(tri) for tri in (triangles or ()) if len(tuple(tri)) >= 3]
    points = [tuple(float(v) for v in point) for tri in tris for point in tri[:3]]
    if not points:
        return None
    mins = [min(point[axis] for point in points) for axis in range(3)]
    maxs = [max(point[axis] for point in points) for axis in range(3)]
    normal_extent = [0.0, 0.0, 0.0]
    for tri in tris:
        a, b, c = (tuple(float(v) for v in point) for point in tri[:3])
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
    t = _number(
        thickness if thickness is not None else settings.get("t", snapshot.get("t", 2.0)),
        2.0,
    )

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
        w = _number(settings.get("w", snapshot.get("w", 0.0)), 0.0)
        h = _number(settings.get("h", snapshot.get("h", 0.0)), 0.0)
        d = _number(settings.get("d", snapshot.get("d", 0.0)), 0.0)
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
        return float(snapshot.get("w", 0.0)), float(snapshot.get("d", 0.0))
    return None
