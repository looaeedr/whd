# -*- coding: utf-8 -*-
"""Engine-owned pre-solve EndCap fixed-relief interference diagnostics.

The UI supplies the existing source parts and intent. Only authentic restored
fixed-relief *delta*, never the whole mating sheet, is diagnosed. No geometry
is permitted to flow back into manufacturing CUTTING or the persisted Registry.
"""
from __future__ import annotations

from .assembly_geometry import (
    restored_endcap_relief_delta, detect_world_mesh_surface_interference,
)
from .assembly_geometry_folded_mesh import folded_mesh_from_polygon
from .receiving_settings_assembly_mesh import resolve_assembled_endcap_world_skins


def project_assembled_endcap_relief_interference(
    part, probe_part, render_data, *,
    diagnostic_relief_delta, box_body_collision_mesh,
    box_body_world, placement, offset, thickness,
):
    """Use the exact saved pre-solve source or legacy ignore-relief fallback.

    Return a read-only existing MeshInterferenceDiagnostic or None when the
    source is not verified/empty. This is never a CUTTING entitlement.
    """
    probe_data = (
        getattr(probe_part, "render_data", None)
        if probe_part is not None else None
    )
    if probe_data is not None and getattr(probe_data, "material", None) is not None:
        delta_material = restored_endcap_relief_delta(probe_data.material)
        x_profile = tuple(dict(seg) for seg in (getattr(probe_part, "x_profile", ()) or ()))
        y_profile = tuple(dict(seg) for seg in (getattr(probe_part, "y_profile", ()) or ()))
        guides = tuple(getattr(probe_data, "fold_guides", ()) or ())
    elif bool(getattr(render_data, "ignore_fixed_corner_relief", False)):
        delta_material = diagnostic_relief_delta
        x_profile = tuple(dict(seg) for seg in part.x_profile)
        y_profile = tuple(dict(seg) for seg in part.y_profile)
        guides = tuple(getattr(part.render_data, "fold_guides", ()) or ())
    else:
        return None
    if delta_material is None or getattr(delta_material, "is_empty", True):
        return None
    delta_local = folded_mesh_from_polygon(
        delta_material, x_profile, y_profile, fold_guides=guides,
    )
    target = resolve_assembled_endcap_world_skins(
        delta_local, placement=placement, box_body_world=box_body_world,
        offset=offset, thickness=thickness,
        preserve_core_origin=bool(getattr(
            render_data, "preserve_endcap_core_origin", False,
        )),
    ).solid_triangles
    if not target:
        return None
    return detect_world_mesh_surface_interference(
        box_body_collision_mesh, target,
    )
