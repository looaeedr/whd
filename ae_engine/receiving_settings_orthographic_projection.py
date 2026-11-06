# -*- coding: utf-8 -*-
"""Read-only world-XY projection of already-resolved physical 3D meshes.

Physical mesh and feature-edge authority remains in Engine; projected segments
are display evidence, not new CUTTING, BEND or DXF manufacturing data. (#2517)
"""
from __future__ import annotations

from .solid_mesh_feature_edges import physical_solid_mesh_feature_segments


def project_solid_mesh_xy_outline(triangles):
    """Return deterministic undirected world-XY outlines from true 3D edges.

    Preserve Receiving settings preview's historical five-decimal display
    precision and skip edges with no visible XY extent.
    """
    projected = set()
    for start, end in physical_solid_mesh_feature_segments(triangles):
        p1 = (round(float(start[0]), 5), round(float(start[1]), 5))
        p2 = (round(float(end[0]), 5), round(float(end[1]), 5))
        if p1 != p2:
            projected.add(tuple(sorted((p1, p2))))
    return tuple(sorted(projected))
