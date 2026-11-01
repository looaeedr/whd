# -*- coding: utf-8 -*-
"""Engine ownership for collision diagnostic source mesh from resolved BoxBody.

Use existing physical true-thickness skins exactly once; legacy mid-surface
fall-back receives the canonical thickness solver. This is diagnostic-only:
no new assembly collision/relief manufacturing rule or cutting authority.
"""
from __future__ import annotations

from .assembly_geometry_primitives import thicken_triangle_surface


def project_box_body_collision_source_mesh(
    render_data, *, box_body_world, placed_piece_meshes=(),
    physical_piece_world=(), thickness,
):
    """Assemble canonical BoxBody solid skin source for interference diagnostics.

    The physical-piece world meshes are already solid. Re-thickening their
    triangles creates impossible collision volumes, so they pass unchanged.
    Fallback mid-surface pieces and integral sheets are thickened exactly once.
    """
    if getattr(render_data, "pieces", None):
        solid = []
        has_physical_skins = bool(physical_piece_world)
        for _piece, triangles in placed_piece_meshes:
            solid.extend(
                triangles if has_physical_skins
                else thicken_triangle_surface(triangles, thickness)
            )
        return tuple(solid)
    return thicken_triangle_surface(box_body_world, thickness)
