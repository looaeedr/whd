# -*- coding: utf-8 -*-
"""Physical 3D solid mesh feature boundaries, moved intact from FinalScene GUI.

Already-thickened authoritative source mesh is the only input. This readback
never manufactures CUTTING material or grants DXF capability. (#2517)
"""
from __future__ import annotations

def physical_solid_mesh_feature_segments(triangles, *, tolerance=1e-6):
    """Return physical solid edges that are visible geometric features.

    Coplanar triangulation diagonals are excluded.  Boundary edges and shared
    edges whose adjacent face normals are non-coplanar are retained.  On a
    thickened formed sheet this yields the actual outer/inner hole rims, sheet
    perimeter, bend/miter edges, and thickness corners on the physical skins.
    """
    import math
    from collections import defaultdict

    inv_tol = 1.0 / max(float(tolerance), 1e-12)

    def key(point):
        return tuple(int(round(float(v) * inv_tol)) for v in point)

    def normal(tri):
        a, b, c = tri[:3]
        ux, uy, uz = (float(b[i]) - float(a[i]) for i in range(3))
        vx, vy, vz = (float(c[i]) - float(a[i]) for i in range(3))
        nx = uy * vz - uz * vy
        ny = uz * vx - ux * vz
        nz = ux * vy - uy * vx
        mag = math.sqrt(nx * nx + ny * ny + nz * nz)
        if mag <= 1e-12:
            return None
        return (nx / mag, ny / mag, nz / mag)

    edges = defaultdict(list)
    original = {}
    for tri in triangles or ():
        if len(tri) < 3:
            continue
        n = normal(tri)
        if n is None:
            continue
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            ka, kb = key(a), key(b)
            edge = (ka, kb) if ka <= kb else (kb, ka)
            edges[edge].append(n)
            original[ka] = tuple(float(v) for v in a)
            original[kb] = tuple(float(v) for v in b)

    segments = []
    for edge, normals in edges.items():
        visible = len(normals) == 1
        if not visible and len(normals) >= 2:
            base = normals[0]
            visible = any(
                abs(sum(base[i] * other[i] for i in range(3))) < 1.0 - 1e-6
                for other in normals[1:]
            )
        if visible:
            segments.append((original[edge[0]], original[edge[1]]))
    return tuple(segments)

