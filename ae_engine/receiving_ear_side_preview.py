# -*- coding: utf-8 -*-
"""#2517 / #1503: Engine-owned source-verified, DISPLAY-ONLY EAR side preview.

This never upgrades a CHECK-only EAR source to welding, manufacturing or DXF
approval. It consumes the same canonical ResolvedManufacturingGeometry and
world/UV receipts used by WHD's established physical side validation.
"""
from __future__ import annotations

from dataclasses import replace

from .assembly_geometry import build_joint_world_geometry
from .manufacturing_scene_access import owner_render_data
from .receiving_fixed_plate_side_mark_preview import (
    build_receiving_ear_side_marking_previews,
)
from .receiving_fixed_plate_side_uv_marking import (
    resolve_receiving_ear_side_uv_receipts,
)


def project_receiving_ear_side_piece_2d_preview(
    snapshot, source_piece, *, piece_key, geometry,
    dimensions, sheet_thickness, world_geometry=None,
    display_only_marking_overlap=False,
):
    """Return a separate displayed piece, preserving real manufacturing source.

    The 2D renderer consumes returned piece.render_data.scene. The original
    manufacturing geometry/BoxBody structural source remains unchanged.
    """
    key = str(piece_key)
    if key not in {"box_body:left_side", "box_body:right_side"}:
        raise ValueError("EAR_2D_PREVIEW_EXPECTS_PHYSICAL_SIDE")
    if snapshot.get("model") not in ("受電箱", "RECEIVING") or snapshot.get("nfb_config_submitted") is not True:
        raise ValueError("EAR_2D_PREVIEW_REQUIRES_SUBMITTED_RECEIVING")
    if str(getattr(source_piece, "role", "") or "").lower() != key.split(":", 1)[1]:
        raise ValueError("EAR_2D_PREVIEW_PIECE_ROLE_MISMATCH")

    real_source = owner_render_data(geometry, key)
    data = source_piece.render_data
    if real_source is None or data is None or data.material is None:
        raise ValueError("EAR_2D_PREVIEW_REAL_SIDE_OWNER_MISSING")
    # Both paths must represent the SAME authored source flat, not a stale
    # alternate preview, different CUTTING, or a side borrowed from another bay.
    if not data.material.equals(real_source.material):
        raise ValueError("EAR_2D_PREVIEW_SOURCE_AND_MANUFACTURING_SIDE_DRIFT")
    # Joint-placement marks may be added on the canonical manufacturing path;
    # only source material and baseline identity have to remain the same.
    source_stamp = (data.metadata or {}).get("baseline_source_sha256")
    canonical_stamp = (real_source.metadata or {}).get("baseline_source_sha256")
    if source_stamp is not None and canonical_stamp is not None and source_stamp != canonical_stamp:
        raise ValueError("EAR_2D_PREVIEW_SIDE_BASELINE_SOURCE_DRIFT")

    if world_geometry is None:
        world_geometry = build_joint_world_geometry(
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
    previews = build_receiving_ear_side_marking_previews(
        receipts, sides,
        display_only_marking_overlap=bool(display_only_marking_overlap),
    )
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
            # A display-only mode that can expose real EAR contact even
            # when unrelated original joint MARKING crosses its weld zone.
            # Do not treat this as manufacturing conflict certification.
            "ear_side_existing_marking_overlap_display_mode": bool(
                display_only_marking_overlap
            ),
        },
    )
    return replace(source_piece, render_data=shown)
