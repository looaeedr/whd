# -*- coding: utf-8 -*-
"""Low-level world-to-flat collision backprojection helpers."""
from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class FlatInterferenceProjection:
    """World-space sheet crossings mapped back to authoritative flat coordinates."""

    segments_2d: tuple
    points_2d: tuple
    pair_count: int = 0
    # Optional diagnostic evidence. Kept after the legacy positional fields so
    # existing constructors ``FlatInterferenceProjection(seg, pts, count)``
    # remain binary/source compatible.
    segments_world: tuple = ()

    @property
    def has_interference(self) -> bool:
        return bool(self.segments_2d)


def _triangle_pair_crossing_segment(target_tri, source_tri, *, tolerance=1e-7):
    """Return the longest non-coplanar triangle/triangle crossing segment."""
    from .assembly_geometry import _segment_triangle_intersection

    pair_points = []
    for a, b in ((target_tri[0], target_tri[1]), (target_tri[1], target_tri[2]), (target_tri[2], target_tri[0])):
        hit = _segment_triangle_intersection(a, b, source_tri, tolerance=tolerance)
        if hit is not None:
            pair_points.append(hit)
    for a, b in ((source_tri[0], source_tri[1]), (source_tri[1], source_tri[2]), (source_tri[2], source_tri[0])):
        hit = _segment_triangle_intersection(a, b, target_tri, tolerance=tolerance)
        if hit is not None:
            pair_points.append(hit)
    unique = []
    seen = set()
    for point in pair_points:
        key = tuple(round(float(v), 8) for v in point)
        if key not in seen:
            seen.add(key)
            unique.append(tuple(float(v) for v in point))
    if len(unique) < 2:
        return None
    best = None
    best_d2 = -1.0
    for i in range(len(unique)):
        for j in range(i + 1, len(unique)):
            a, b = unique[i], unique[j]
            d2 = sum((a[k] - b[k]) ** 2 for k in range(3))
            if d2 > best_d2:
                best_d2 = d2
                best = (a, b)
    if best is None or best_d2 <= tolerance * tolerance:
        return None
    return best


def _barycentric_world_to_flat(point, world_triangle, flat_triangle, *, tolerance=1e-10):
    a, b, c = world_triangle
    p = point
    v0 = tuple(float(b[i]) - float(a[i]) for i in range(3))
    v1 = tuple(float(c[i]) - float(a[i]) for i in range(3))
    v2 = tuple(float(p[i]) - float(a[i]) for i in range(3))
    d00 = sum(v0[i] * v0[i] for i in range(3))
    d01 = sum(v0[i] * v1[i] for i in range(3))
    d11 = sum(v1[i] * v1[i] for i in range(3))
    d20 = sum(v2[i] * v0[i] for i in range(3))
    d21 = sum(v2[i] * v1[i] for i in range(3))
    denom = d00 * d11 - d01 * d01
    if abs(denom) <= tolerance:
        raise ValueError("degenerate mapped target triangle")
    beta = (d11 * d20 - d01 * d21) / denom
    gamma = (d00 * d21 - d01 * d20) / denom
    alpha = 1.0 - beta - gamma
    u = alpha * float(flat_triangle[0][0]) + beta * float(flat_triangle[1][0]) + gamma * float(flat_triangle[2][0])
    v = alpha * float(flat_triangle[0][1]) + beta * float(flat_triangle[1][1]) + gamma * float(flat_triangle[2][1])
    return (u, v)


def backproject_world_interference_to_endcap_flat(
    source_triangles,
    mapped_target_skin_triangles,
    *,
    tolerance=1e-6,
) -> FlatInterferenceProjection:
    """Map physical world-space crossings back to EndCap/Tail flat coordinates.

    ``mapped_target_skin_triangles`` retains the original flat UV for every
    physical skin triangle.  Triangle crossing endpoints are mapped with
    barycentric coordinates, which is exact for the current sharp-bend,
    piecewise-affine Fold Profile model.
    """
    import numpy as np

    source = tuple(tuple(tuple(map(float, p)) for p in tri) for tri in (source_triangles or ()))
    targets = tuple(mapped_target_skin_triangles or ())
    if not source or not targets:
        return FlatInterferenceProjection((), (), 0)
    src = np.asarray(source, dtype=float)
    src_min = src.min(axis=1)
    src_max = src.max(axis=1)
    segments = []
    segment_keys = set()
    world_segments = []
    world_segment_keys = set()
    points = []
    point_keys = set()
    pair_count = 0

    def record_point(point):
        key = tuple(round(float(v), 6) for v in point)
        if key not in point_keys:
            point_keys.add(key)
            points.append(tuple(float(v) for v in point))

    for mapped in targets:
        target_tri = tuple(tuple(map(float, p)) for p in mapped.world)
        arr = np.asarray(target_tri, dtype=float)
        tmin = arr.min(axis=0) - float(tolerance)
        tmax = arr.max(axis=0) + float(tolerance)
        mask = np.all(src_max + tolerance >= tmin, axis=1) & np.all(src_min - tolerance <= tmax, axis=1)
        for idx in np.nonzero(mask)[0]:
            crossing = _triangle_pair_crossing_segment(
                target_tri, source[int(idx)], tolerance=tolerance
            )
            if crossing is None:
                continue
            a2 = _barycentric_world_to_flat(crossing[0], target_tri, mapped.flat)
            b2 = _barycentric_world_to_flat(crossing[1], target_tri, mapped.flat)
            d2 = (a2[0] - b2[0]) ** 2 + (a2[1] - b2[1]) ** 2
            if d2 <= tolerance * tolerance:
                continue
            pair_count += 1
            key = tuple(sorted((
                tuple(round(float(v), 6) for v in a2),
                tuple(round(float(v), 6) for v in b2),
            )))
            if key not in segment_keys:
                segment_keys.add(key)
                segments.append((a2, b2))
            wseg = (
                tuple(float(v) for v in crossing[0]),
                tuple(float(v) for v in crossing[1]),
            )
            wkey = tuple(sorted(tuple(round(float(v), 6) for v in point) for point in wseg))
            if wkey not in world_segment_keys:
                world_segment_keys.add(wkey)
                world_segments.append(wseg)
            record_point(a2)
            record_point(b2)
    return FlatInterferenceProjection(
        tuple(segments), tuple(points), pair_count, tuple(world_segments)
    )


# The barycentric implementation is generic; keep the legacy EndCap name as a
# compatibility alias while Solver v2 uses the neutral API.
backproject_world_interference_to_flat = backproject_world_interference_to_endcap_flat
