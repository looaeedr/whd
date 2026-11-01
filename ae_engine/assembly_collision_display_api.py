# -*- coding: utf-8 -*-
"""Headless physical-assembly collision display audit, owned by the Engine.

This is fail-closed optional visual evidence, not relief/DXF/MFG approval.
"""
from __future__ import annotations

from .assembly_geometry import build_joint_world_geometry
from .assembly_all_parts_collision import audit_all_physical_part_pairs


def project_assembly_collision_display_audit(
    assembly_parts, finished_dimensions, sheet_thickness, *,
    visible_part_keys=None, visible_box_body_piece_keys=None,
    certified_relief_diagnostics=(),
):
    """Use real world meshes and select only real sheets, not the body proxy."""
    geometry = build_joint_world_geometry(
        assembly_parts, finished_dimensions, sheet_thickness,
    )
    world_parts = geometry["world_triangles_by_part"]
    selected = (
        {key for key in world_parts if key != "box_body"}
        if visible_part_keys is None else
        {
            key for key in world_parts if (
                (key.startswith("box_body:") and "box_body" in visible_part_keys)
                or key in visible_part_keys
            )
        }
    )
    if visible_box_body_piece_keys is not None:
        selected = {
            key for key in selected
            if not key.startswith("box_body:")
            or key.startswith("box_body:divider:")
            or key in visible_box_body_piece_keys
        }
    return audit_all_physical_part_pairs(
        world_parts,
        visible_part_keys=selected,
        certified_relief_diagnostics=tuple(certified_relief_diagnostics or ()),
    )
