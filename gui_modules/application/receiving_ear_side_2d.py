# -*- coding: utf-8 -*-
"""#1503: actual side-piece 2D preview from source-owned formed EAR world skins.

Display-only. Never mutate ResolvedManufacturingGeometry, source panels,
production FinalScene, manufacturing DXF, or a weld/MFG certification bit.
"""
from __future__ import annotations

from ae_engine import manufacturing_api


def project_receiving_ear_side_piece_2d_preview(
    snapshot, source_piece, *, piece_key, geometry,
    dimensions, sheet_thickness, world_geometry=None,
    display_only_marking_overlap=False,
):
    """Compatibility: UI delegates real side source checks to the public Engine."""
    return manufacturing_api.project_receiving_ear_side_piece_2d_preview(
        snapshot, source_piece, piece_key=piece_key, geometry=geometry,
        dimensions=dimensions, sheet_thickness=sheet_thickness,
        world_geometry=world_geometry,
        display_only_marking_overlap=display_only_marking_overlap,
    )


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

    key = str(piece_key)
    original = source_piece.render_data
    if (key not in {"box_body:left_side", "box_body:right_side"}
            or snapshot.get("model") not in ("受電箱", "RECEIVING")
            or snapshot.get("nfb_config_submitted") is not True):
        host.last_receiving_ear_single_piece_blocker = None
        return original
    aggregate = geometry.part("box_body").render_data
    owners = tuple(
        (
            row.role,
            (row.render_data.metadata or {}).get("baseline_source_sha256"),
            repr(tuple(row.render_data.scene.primitives or ())),
        )
        for row in tuple(getattr(aggregate, "pieces", ()) or ())
    )
    stamp = sha256(repr((snapshot, key, owners)).encode("utf-8")).hexdigest()
    cache = getattr(host, "_receiving_ear_single_piece_display_cache", None)
    if not isinstance(cache, dict):
        cache = {}
    row = cache.get(key)
    if row is not None and row[0] == stamp:
        host.last_receiving_ear_single_piece_blocker = row[2]
        return row[1]
    try:
        displayed = project_receiving_ear_side_piece_2d_preview(
            snapshot, source_piece, piece_key=key,
            geometry=geometry,
            dimensions=(float(snapshot["w"]), float(snapshot["h"]), float(snapshot["d"])),
            sheet_thickness=float(snapshot["t"]),
            display_only_marking_overlap=True,
        ).render_data
        blocker = None
    except (ValueError, TypeError, RuntimeError, KeyError) as exc:
        # Never fabricate a contact line or block ordinary material inspection
        # if a real source/UV/bend conflict exists. Preserve the reason.
        displayed, blocker = original, str(exc)
    host.last_receiving_ear_single_piece_blocker = blocker
    cache[key] = (stamp, displayed, blocker)
    host._receiving_ear_single_piece_display_cache = cache
    return displayed
