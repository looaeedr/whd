# -*- coding: utf-8 -*-
"""#1503: actual side-piece 2D preview from source-owned formed EAR world skins.

Display-only. Never mutate ResolvedManufacturingGeometry, source panels,
production FinalScene, manufacturing DXF, or a weld/MFG certification bit.
"""
from __future__ import annotations

from dataclasses import replace

from ae_engine.manufacturing_scene_access import owner_render_data
from ae_engine.receiving_fixed_plate_side_mark_preview import (
    build_receiving_ear_side_marking_previews,
)
from ae_engine.receiving_fixed_plate_side_uv_marking import (
    resolve_receiving_ear_side_uv_receipts,
)


def project_receiving_ear_side_piece_2d_preview(
    snapshot, source_piece, *, piece_key, geometry,
    dimensions, sheet_thickness, world_geometry=None,
):
    """Return a separate displayed piece, preserving real manufacturing source.

    The 2D renderer consumes returned piece.render_data.scene. The original
    manufacturing geometry/BoxBody structural source remains unchanged.
    """
    key = str(piece_key)
    if key not in {"box_body:left_side", "box_body:right_side"}:
        raise ValueError("EAR_2D_PREVIEW_EXPECTS_PHYSICAL_SIDE")
    if snapshot.get("model") != "受電箱" or snapshot.get("nfb_config_submitted") is not True:
        raise ValueError("EAR_2D_PREVIEW_REQUIRES_SUBMITTED_RECEIVING")
    if str(getattr(source_piece, "role", "") or "").lower() != key.split(":", 1)[1]:
        raise ValueError("EAR_2D_PREVIEW_PIECE_ROLE_MISMATCH")

    real_source = owner_render_data(geometry, key)
    data = source_piece.render_data
    if real_source is None or data is None or data.material is None:
        raise ValueError("EAR_2D_PREVIEW_REAL_SIDE_OWNER_MISSING")
    # Both paths must represent the SAME authored source flat, not a stale
    # alternate preview, different CUTTING, or a side borrowed from another bay.
    if (not data.material.equals(real_source.material)
            or tuple(data.scene.primitives or ()) != tuple(real_source.scene.primitives or ())):
        raise ValueError("EAR_2D_PREVIEW_SOURCE_AND_MANUFACTURING_SIDE_DRIFT")

    if world_geometry is None:
        from phase6_manufacturing_geometry import _phase6_build_joint_world_geometry
        world_geometry = _phase6_build_joint_world_geometry(
            tuple(geometry.parts or ()),
            tuple(dimensions),
            float(sheet_thickness),
        )
    receipts = resolve_receiving_ear_side_uv_receipts(
        snapshot, world_geometry=world_geometry, geometry=geometry,
    )
    sides = {
        side: owner_render_data(geometry, side)
        for side in ("box_body:left_side", "box_body:right_side")
    }
    previews = build_receiving_ear_side_marking_previews(receipts, sides)
    if key not in previews:
        raise ValueError("EAR_2D_PREVIEW_NOT_PROJECTED_TO_OWNER")
    before = dict(data.metadata or {})
    # A display-only scene copy. Keep source flags unchanged, particularly
    # manufacturing_ready=False; NEVER turn a preview into a DXF source.
    shown = replace(
        data,
        scene=previews[key],
        metadata={
            **before,
            "ear_side_mark_preview_only": True,
            "ear_side_mark_preview_owner": key,
            "ear_side_mark_preview_count": sum(
                len(r.marking_segments) for r in receipts if r.side_piece_id == key
            ),
        },
    )
    return replace(source_piece, render_data=shown)
