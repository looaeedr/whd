# -*- coding: utf-8 -*-
"""Physical EndCap CUTTING hole-ring projection for 3D FinalScene.

This is the move-only existing assembly display projection, using paired
canonical local/world surface vertices and Engine Fold mappers.  It is not a
CUTTING manufacturer or an independent EndCap placement/mesh solver.
"""
from __future__ import annotations

from .assembly_geometry_folded_mesh import _profile_geometry, _prepare_profile_mapper


def project_endcap_cutting_hole_rim_segments(
    material, x_profile, y_profile, fold_guides,
    local_surface, placed_surface, placement,
):
    """Return immutable world-space rims only for *real* material inner rings.

    No guessed envelope/width center or triangulation T-junctions: placement
    is anchored to the same pair of actual local/world mesh vertices that
    the canonical FinalScene already uses.
    """
    if not local_surface or not placed_surface or material is None:
        return ()
    plane = str(placement or "").lower()
    if plane not in {"head", "top", "tail", "bottom"}:
        return ()
    p0 = tuple(float(x) for x in local_surface[0][0])
    w0 = tuple(float(x) for x in placed_surface[0][0])
    sign = -1 if plane in {"head", "top"} else 1

    profiles_x = tuple(x_profile or ())
    profiles_y = tuple(y_profile or ())
    guides = tuple(fold_guides or ())
    map_x = _prepare_profile_mapper(
        profiles_x, axis="x", fold_guides=guides,
        geometry=_profile_geometry(profiles_x),
    )
    map_y = _prepare_profile_mapper(
        profiles_y, axis="y", fold_guides=guides,
        geometry=_profile_geometry(profiles_y),
    )

    polys = ([material] if getattr(material, "geom_type", "") == "Polygon"
             else tuple(getattr(material, "geoms", ()) or ()))
    segments = []
    for poly in polys:
        if getattr(poly, "geom_type", "") != "Polygon":
            continue
        for inner_ring in poly.interiors:
            positions = []
            for x, y in inner_ring.coords:
                ux, zx = map_x(float(x), float(y))
                uy, zy = map_y(float(y), float(x))
                local = (ux, uy, zx + zy)
                positions.append((
                    w0[0] + float(local[0]) - p0[0],
                    w0[1] + sign * (float(local[2]) - p0[2]),
                    w0[2] + sign * (float(local[1]) - p0[1]),
                ))
            segments.extend(
                (a, b) for a, b in zip(positions, positions[1:])
                if any(abs(a[i] - b[i]) > 1e-9 for i in range(3))
            )
    return tuple(segments)
