# -*- coding: utf-8 -*-
"""#1503 provisional SIDE-owned EAR MARKING; never production DXF approval."""
from __future__ import annotations

from collections import defaultdict
from typing import Mapping

from shapely.geometry import LineString, Point, Polygon

from .receiving_fixed_plate_side_uv_marking import ReceivingEarSideUVReceipt
from .sheetmetal_drawing import (
    CirclePrimitive, DrawingScene, LinePrimitive, PolylinePrimitive,
)


def _geometry_of_source_primitive(item):
    if isinstance(item, CirclePrimitive):
        return Point(float(item.center.x), float(item.center.y)).buffer(
            float(item.radius), resolution=32,
        )
    if isinstance(item, LinePrimitive):
        return LineString(((item.p1.x, item.p1.y), (item.p2.x, item.p2.y)))
    if isinstance(item, PolylinePrimitive):
        points = [(p.x, p.y) for p in item.points]
        if item.closed and points:
            points.append(points[0])
        if len(points) >= 2:
            return LineString(points)
    return None


def _check_source_conflicts(patch, render_data, *, display_only_marking_overlap=False):
    if not render_data.material.covers(patch):
        raise ValueError("EAR_MARK_PREVIEW_FINAL_MATERIAL_CONFLICT")
    for guide in tuple(render_data.fold_guides or ()):
        axis = str(guide.axis)
        p, lo, hi = float(guide.position), float(guide.span_start), float(guide.span_end)
        if axis == "x":
            feature = LineString(((p, lo), (p, hi)))
        elif axis == "y":
            feature = LineString(((lo, p), (hi, p)))
        else:
            raise ValueError("EAR_MARK_PREVIEW_INVALID_BEND")
        if patch.intersects(feature):
            raise ValueError("EAR_MARK_PREVIEW_BEND_CONFLICT")
    for item in tuple(render_data.scene.primitives or ()):
        layer = str(getattr(item, "layer", "") or "").upper()
        if layer not in {"CUTTING", "BLIND_HOLE", "BEND", "MARKING"}:
            continue
        feature = _geometry_of_source_primitive(item)
        if feature is not None and patch.intersects(feature):
            if layer == "MARKING" and display_only_marking_overlap:
                # Native operator 2D visualization only. Existing source
                # markings (e.g. a true joint X inside the EAR footprint) do
                # not erase the separate true EAR outline from the screen.
                # Independent manufacturing/MFG and CUTTING/BEND guards are
                # intentionally unchanged and this returns NO approval.
                continue
            raise ValueError("EAR_MARK_PREVIEW_EXISTING_" + layer + "_CONFLICT")


def build_receiving_ear_side_marking_previews(
    receipts: tuple[ReceivingEarSideUVReceipt, ...],
    side_render_data: Mapping[str, object],
    *,
    display_only_marking_overlap: bool = False,
) -> dict[str, DrawingScene]:
    """Read-only preview, copying existing side drawing without modifying it.

    The input is the actual side-owner world-to-UV receipt. Welding and MFG
    readiness remain false; this must not be fed to a production DXF sink.
    """
    rows = tuple(receipts or ())
    if len(rows) not in (2, 4):
        raise ValueError("EAR_MARK_PREVIEW_INCOMPLETE_TIER_COUNT")
    if len({r.ear_part_id for r in rows}) != len(rows):
        raise ValueError("EAR_MARK_PREVIEW_DUPLICATE_PART_ID")
    by_side = defaultdict(list)
    for row in rows:
        if not isinstance(row, ReceivingEarSideUVReceipt):
            raise TypeError("EAR_MARK_PREVIEW_TYPED_RECEIPT_REQUIRED")
        if (row.side_piece_id not in {"box_body:left_side", "box_body:right_side"}
                or not row.side_flat_uv_backprojection_verified
                or not row.side_final_material_coverage_verified
                or not row.side_bend_intersection_rejected
                or row.weld_contact_verified or row.manufacturing_ready):
            raise ValueError("EAR_MARK_PREVIEW_UNVERIFIED_RECEIPT")
        by_side[row.side_piece_id].append(row)
    if set(by_side) != {"box_body:left_side", "box_body:right_side"}:
        raise ValueError("EAR_MARK_PREVIEW_BOTH_SIDE_OWNERS_REQUIRED")

    result = {}
    for side, side_rows in sorted(by_side.items()):
        owner = side_render_data.get(side)
        if owner is None or getattr(owner, "material", None) is None:
            raise ValueError("EAR_MARK_PREVIEW_SIDE_SOURCE_MISSING")
        if len({r.nfb_layer_index for r in side_rows}) != len(side_rows):
            raise ValueError("EAR_MARK_PREVIEW_REUSED_TIER_ID")
        patches = []
        scene = DrawingScene()
        scene.extend(tuple(owner.scene.primitives or ()))
        for row in sorted(side_rows, key=lambda r: (r.nfb_layer_index, r.ear_part_id)):
            patch = Polygon(row.side_source_flat_boundary)
            if patch.is_empty or not patch.is_valid or abs(patch.area - 5632.) > 1.:
                raise ValueError("EAR_MARK_PREVIEW_SOURCE_PATCH_INVALID")
            if any(patch.intersects(previous) for previous in patches):
                raise ValueError("EAR_MARK_PREVIEW_TIER_COLLISION")
            _check_source_conflicts(
                patch, owner,
                display_only_marking_overlap=display_only_marking_overlap,
            )
            for p1, p2 in row.marking_segments:
                if not patch.covers(LineString((p1, p2))):
                    raise ValueError("EAR_MARK_PREVIEW_MARK_OUTSIDE_RECEIPT")
                scene.add_line(p1, p2, layer="MARKING")
            patches.append(patch)
        result[side] = scene
    return result
