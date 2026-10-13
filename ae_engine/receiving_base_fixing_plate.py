# -*- coding: utf-8 -*-
"""Receiving Base Plate > Base Fixing Plate (formerly 'ear') source preview.

The physical plates are welded to the inside of the left/right cabinet sides.
They are NOT material belonging to the Base Plate blank. This module exposes
independent, stable *pending-manufacture* part identities and an authentic
source-flat 2D silhouette, without inventing the missing certified bend and
weld-Z manufacturing geometry.

The nominal 256x105 outline, R5 top corners, and four 25x11 slots were measured
from the user's original 受電耳朵.dxf (SHA256:
2d8b96ff88882c033a08da223f112e2d7573f787fb13fa056cf71626bfeec8a8).
Do not use the preview geometry as manufacturing CUTTING/BEND authority:
the source and material may be edited and must be re-read and recertified for
each actual production request.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .receiving_base_plate_config import RECEIVING_FAMILIES
from .receiving_weld_ear_policy import resolve_receiving_large_weld_ear_fit

BASE_FIXING_PLATE_PARENT_ID = "base_plate"
BASE_FIXING_PLATE_PREFIX = "base_plate:fixing_plate:"
BASE_FIXING_PLATE_DISPLAY_NAME = "底板固定片"
SOURCE_FLAT_SIZE_MM = (256.0, 105.0)
SOURCE_TOP_CORNER_RADIUS_MM = 5.0
SOURCE_SLOT_SIZE_MM = (25.0, 11.0)
SOURCE_SLOT_CENTERS_MM = ((23.0, 86.0), (58.0, 86.0),
                          (198.0, 86.0), (233.0, 86.0))
MANUFACTURING_STATUS = "EAR_BEND_WELD_Z_UNVERIFIED"


@dataclass(frozen=True)
class BaseFixingPlatePreview:
    part_id: str
    parent_part_id: str
    display_name: str
    side: str
    stock_thickness_mm: float
    nominal_source_outline_mm: tuple[float, float]
    nominal_source_slot_centers_mm: tuple[tuple[float, float], ...]
    source_slot_size_mm: tuple[float, float]
    source_top_corner_radius_mm: float
    nominal_fold_from_weld_edge_mm: float
    applicable_slot_pair_indexes: tuple[int, int] | None
    manufacturing_status: str = MANUFACTURING_STATUS

    @property
    def manufacturing_ready(self) -> bool:
        return False


def receiving_base_fixing_plate_previews(
    snapshot: Mapping[str, object] | None,
    *,
    available_parts=(),
) -> tuple[BaseFixingPlatePreview, ...]:
    """Read-only part preview; never changes physical scene or BOM.

    We only expose the W800/T2 source-verified variant. Other dimensions need
    an independently verified physical source and must not silently inherit
    these two W800 plates. A missing explicit base variant is previewable with
    the 210-mm outer slot pair, but remains *unconfigured* and never releasable.
    """
    data = dict(snapshot or {})
    model = str(data.get("model") or data.get("baseline_model") or "").strip()
    if model not in RECEIVING_FAMILIES or BASE_FIXING_PLATE_PARENT_ID not in set(available_parts):
        return ()
    try:
        w = float(data.get("w", 0))
        side_t = float(data.get("t", 0))
    except (TypeError, ValueError, OverflowError):
        return ()
    config = data.get("receiving_base_plate")
    pattern = str(config.get("pattern") or "") if isinstance(config, Mapping) else ""
    from .sheetmetal_part_adapters import (
        RECEIVING_BASE_PATTERN_CENTER, RECEIVING_BASE_PATTERN_LEFT,
        RECEIVING_BASE_PATTERN_RIGHT,
    )
    # Source plate offers both slot pairs, but an unconfigured bottom plate
    # cannot silently claim to mate the 210-mm pair.
    chosen_pair = (
        (1, 2) if pattern == RECEIVING_BASE_PATTERN_CENTER else
        (0, 3) if pattern in (RECEIVING_BASE_PATTERN_LEFT, RECEIVING_BASE_PATTERN_RIGHT)
        else None
    )
    pitch_y = 140.0 if chosen_pair == (1, 2) else 210.0
    try:
        fit = resolve_receiving_large_weld_ear_fit(
            box_outer_width_mm=w,
            box_side_thickness_mm=side_t,
            fixing_hole_pitch_x_mm=670.0,
            fixing_hole_pitch_y_mm=pitch_y,
        )
    except (TypeError, ValueError, OverflowError):
        return ()
    return tuple(
        BaseFixingPlatePreview(
            part_id=BASE_FIXING_PLATE_PREFIX + side,
            parent_part_id=BASE_FIXING_PLATE_PARENT_ID,
            display_name=BASE_FIXING_PLATE_DISPLAY_NAME + ("（左）" if side == "left" else "（右）"),
            side=side,
            stock_thickness_mm=fit.ear_thickness_mm,
            nominal_source_outline_mm=SOURCE_FLAT_SIZE_MM,
            nominal_source_slot_centers_mm=SOURCE_SLOT_CENTERS_MM,
            source_slot_size_mm=SOURCE_SLOT_SIZE_MM,
            source_top_corner_radius_mm=SOURCE_TOP_CORNER_RADIUS_MM,
            nominal_fold_from_weld_edge_mm=fit.nominal_fold_from_weld_edge_mm,
            applicable_slot_pair_indexes=chosen_pair,
        )
        for side in ("left", "right")
    )
