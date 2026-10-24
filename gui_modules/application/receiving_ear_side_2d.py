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

def present_receiving_ear_side_piece_2d(
    host, aggregate_render_data, source_piece, piece_key, *,
    geometry_provider=None,
):
    """Live GUI side-piece seam; keep the operator's source scene on failure."""
    key = str(piece_key)
    if key not in {"box_body:left_side", "box_body:right_side"}:
        return source_piece, None
    try:
        # The primary window's snapshot is only an editable projection.
        # In the actual WHD GUI, NFB Confirm All commits to FoldDesigner,
        # leaving the primary mirror without nfb_config_submitted. Reading
        # that mirror silently discarded all SIDE EAR MARKING. The same
        # FoldDesigner now owns BOTH the NFB source and its resolved geometry.
        designer = getattr(host, "fold_designer_app", None)
        if designer is not None:
            canonical = getattr(designer, "_phase6_input_snapshot", None)
            if not isinstance(canonical, dict):
                raise ValueError("EAR_2D_PREVIEW_DESIGNER_SOURCE_NOT_AVAILABLE")
            snapshot = dict(canonical)
        else:
            snapshot = dict(host._compose_phase6_project_snapshot_from_main_gui() or {})
        if snapshot.get("model") not in ("受電箱", "RECEIVING"):
            return source_piece, None
        if snapshot.get("nfb_config_submitted") is not True:
            # A legacy/unconfigured Receiving side has no EAR weld footprint;
            # do not borrow a stale submitted NFB from the main GUI mirror.
            main = (dict(host._compose_phase6_project_snapshot_from_main_gui() or {})
                    if designer is not None else snapshot)
            if main.get("nfb_config_submitted") is True:
                raise ValueError("EAR_2D_PREVIEW_PRIMARY_SOURCE_DRIFT")
            return source_piece, None

        import hashlib
        from math import isfinite
        if any(
            isinstance(snapshot.get(k), bool)
            or not isinstance(snapshot.get(k), (int, float))
            or not isfinite(float(snapshot[k]))
            or float(snapshot[k]) <= 0
            for k in ("w", "h", "d", "t")
        ):
            raise ValueError("EAR_2D_PREVIEW_INVALID_DIMENSIONS")
        # The source-stamp and rendered primitives participate in the cache.
        # A changed Bay, actual source hole, baseline or layer invalidates it.
        source_data = getattr(source_piece, "render_data", None)
        source_sig = (
            getattr(source_piece, "role", None),
            (getattr(source_data, "metadata", None) or {}).get("baseline_source_sha256"),
            repr(tuple(getattr(getattr(source_data, "scene", None), "primitives", None) or ())),
            getattr(getattr(source_data, "material", None), "wkt", None),
        )
        owners = tuple(
            (p.role, (p.render_data.metadata or {}).get("baseline_source_sha256"),
             repr(tuple(p.render_data.scene.primitives or ())))
            for p in tuple(getattr(aggregate_render_data, "pieces", ()) or ())
        )
        stamp = hashlib.sha256(
            repr((snapshot, key, source_sig, owners)).encode("utf-8")
        ).hexdigest()
        cached = getattr(host, "_receiving_ear_side_2d_display_cache", None)
        if cached is not None and cached[0] == stamp:
            return cached[1], cached[2]

        if geometry_provider is None:
            resolver = getattr(designer, "_phase6_resolve_manufacturing_geometry", None)
            if callable(resolver):
                geometry = resolver()
            else:
                from phase6_manufacturing_adapter import resolve_for_app
                geometry = resolve_for_app(designer if designer is not None else host)
        else:
            geometry = geometry_provider(designer if designer is not None else host)
        displayed = project_receiving_ear_side_piece_2d_preview(
            snapshot, source_piece, piece_key=key, geometry=geometry,
            dimensions=(float(snapshot["w"]), float(snapshot["h"]), float(snapshot["d"])),
            sheet_thickness=float(snapshot["t"]),
            display_only_marking_overlap=True,
        )
        result = displayed, None
    except Exception as exc:
        # Operator can inspect and edit the original plate even when EAR
        # placement has a real unresolved source/UV/CUTTING conflict.
        result = source_piece, str(exc)
    if "stamp" in locals():
        host._receiving_ear_side_2d_display_cache = (stamp, *result)
    return result


def present_receiving_ear_side_designer_piece_3d(
    host, snapshot, geometry, source_piece, piece_key,
):
    """FoldDesigner single-piece view uses the SAME source 2D EAR UV lines.

    Assembly already has true contact marks. The selected physical SIDE
    previously returned its raw FinalScene, so the independent part displayed
    no EAR MARKING despite a valid submitted NFB. This is a cached, read-only
    VIEW copy only; actual manufacturing and DXF owners stay unchanged.
    """
    from hashlib import sha256
    from math import isfinite

    key = str(piece_key)
    original = source_piece.render_data
    if (key not in {"box_body:left_side", "box_body:right_side"}
            or snapshot.get("model") not in ("受電箱", "RECEIVING")
            or snapshot.get("nfb_config_submitted") is not True):
        host.last_receiving_ear_single_piece_blocker = None
        return original
    try:
        if any(
            isinstance(snapshot.get(k), bool)
            or not isinstance(snapshot.get(k), (int, float))
            or not isfinite(float(snapshot[k]))
            or float(snapshot[k]) <= 0
            for k in ("w", "h", "d", "t")
        ):
            raise ValueError("EAR_2D_PREVIEW_INVALID_DIMENSIONS")
        aggregate = geometry.part("box_body").render_data
        source_sig = (
            getattr(source_piece, "role", None),
            (getattr(original, "metadata", None) or {}).get("baseline_source_sha256"),
            repr(tuple(getattr(getattr(original, "scene", None), "primitives", None) or ())),
            getattr(getattr(original, "material", None), "wkt", None),
        )
        owners = tuple(
            (
                row.role,
                (row.render_data.metadata or {}).get("baseline_source_sha256"),
                repr(tuple(row.render_data.scene.primitives or ())),
            )
            for row in tuple(getattr(aggregate, "pieces", ()) or ())
        )
        stamp = sha256(repr((snapshot, key, source_sig, owners)).encode("utf-8")).hexdigest()
        cache = getattr(host, "_receiving_ear_single_piece_display_cache", None)
        if not isinstance(cache, dict):
            cache = {}
        row = cache.get(key)
        if row is not None and row[0] == stamp:
            host.last_receiving_ear_single_piece_blocker = row[2]
            return row[1]
        displayed = project_receiving_ear_side_piece_2d_preview(
            snapshot, source_piece, piece_key=key,
            geometry=geometry,
            dimensions=(float(snapshot["w"]), float(snapshot["h"]), float(snapshot["d"])),
            sheet_thickness=float(snapshot["t"]),
            display_only_marking_overlap=True,
        ).render_data
        blocker = None
    except (ValueError, TypeError, RuntimeError, KeyError, AttributeError) as exc:
        # Never fabricate a contact line or block ordinary material inspection
        # if a real source/UV/bend conflict exists. Preserve the reason.
        displayed, blocker = original, str(exc)
    host.last_receiving_ear_single_piece_blocker = blocker
    if "stamp" in locals() and "cache" in locals():
        cache[key] = (stamp, displayed, blocker)
        host._receiving_ear_single_piece_display_cache = cache
    return displayed
