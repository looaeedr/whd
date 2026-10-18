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
    if not data.material.equals(real_source.material):
        raise ValueError("EAR_2D_PREVIEW_SOURCE_AND_MANUFACTURING_SIDE_DRIFT")
    # Joint-placement marks may be added on the canonical manufacturing path;
    # only source material and baseline identity have to remain the same.
    source_stamp = (data.metadata or {}).get("baseline_source_sha256")
    canonical_stamp = (real_source.metadata or {}).get("baseline_source_sha256")
    if source_stamp is not None and canonical_stamp is not None and source_stamp != canonical_stamp:
        raise ValueError("EAR_2D_PREVIEW_SIDE_BASELINE_SOURCE_DRIFT")

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

def present_receiving_ear_side_piece_2d(
    host, aggregate_render_data, source_piece, piece_key, *,
    geometry_provider=None,
):
    """Live GUI side-piece seam; keep the operator's source scene on failure."""
    key = str(piece_key)
    if key not in {"box_body:left_side", "box_body:right_side"}:
        return source_piece, None
    try:
        snapshot = dict(host._compose_phase6_project_snapshot_from_main_gui() or {})
        if snapshot.get("model") != "受電箱" or snapshot.get("nfb_config_submitted") is not True:
            return source_piece, None

        import hashlib
        # The source-stamp and rendered primitives participate in the cache.
        # A changed Bay, actual source hole, baseline or layer invalidates it.
        owners = tuple(
            (p.role, (p.render_data.metadata or {}).get("baseline_source_sha256"),
             repr(tuple(p.render_data.scene.primitives or ())))
            for p in tuple(getattr(aggregate_render_data, "pieces", ()) or ())
        )
        stamp = hashlib.sha256(
            repr((snapshot, key, owners)).encode("utf-8")
        ).hexdigest()
        cached = getattr(host, "_receiving_ear_side_2d_display_cache", None)
        if cached is not None and cached[0] == stamp:
            return cached[1], cached[2]

        if geometry_provider is None:
            from phase6_manufacturing_adapter import resolve_for_app
            geometry_provider = resolve_for_app
        geometry = geometry_provider(host)
        displayed = project_receiving_ear_side_piece_2d_preview(
            snapshot, source_piece, piece_key=key, geometry=geometry,
            dimensions=(float(snapshot["w"]), float(snapshot["h"]), float(snapshot["d"])),
            sheet_thickness=float(snapshot["t"]),
        )
        result = displayed, None
    except Exception as exc:
        # Operator can inspect and edit the original plate even when EAR
        # placement has a real unresolved source/UV/CUTTING conflict.
        result = source_piece, str(exc)
    if "stamp" in locals():
        host._receiving_ear_side_2d_display_cache = (stamp, *result)
    return result
