# -*- coding: utf-8 -*-
"""Receiving Base Plate true folded X/Y profile, shared by 3D and placement.

This projection is derived only from the *same* canonical Receiving physical
CUTTING/BEND adapter as the FinalScene, never from another legacy 3-fold
base-plate formula.  Flat 33 and formed 35 are distinct source datums.
"""
from __future__ import annotations

from .sheetmetal_part_adapters import (
    RECEIVING_BASE_PATTERN_CENTER, build_receiving_base_plate_result,
)


def receiving_base_plate_3d_profiles(snapshot, physical=None):
    """Return the real X/Y profiles; None means no configured physical plate."""
    if physical is None:
        from .receiving_base_plate_config import receiving_base_plate_values
        physical = receiving_base_plate_values(snapshot)
    if physical is None:
        return None
    t = float(snapshot["t"])
    actual = build_receiving_base_plate_result(
        w=float(snapshot["w"]), h=float(physical["h"]), t=t,
        shrink_top=physical["base_plate_shrink_top"],
        shrink_bottom=physical["base_plate_shrink_bottom"],
        shrink_left=physical["base_plate_shrink_left"],
        shrink_right=physical["base_plate_shrink_right"],
        bend=physical["base_plate_bend"],
        pattern=physical["receiving_bend_pattern"],
        nfb_depth_pair_mm=physical["receiving_nfb_depth_pair_mm"],
    )
    if physical["receiving_bend_pattern"] == RECEIVING_BASE_PATTERN_CENTER:
        stations = sorted({
            float(b.p1.x) for b in actual.bends
            if abs(float(b.p1.x) - float(b.p2.x)) <= 1e-8
        })
        if len(stations) != 4 or stations[0] <= 0 or stations[-1] >= actual.width:
            raise ValueError("Receiving CENTER requires exactly four actual side bends")
        lengths = (
            stations[0], stations[1]-stations[0], stations[2]-stations[1],
            stations[3]-stations[2], actual.width-stations[3],
        )
        if min(lengths) <= 0:
            raise ValueError("Receiving CENTER invalid source-side material stations")
        # Brand-anchored CENTER supports must be farther inward than the
        # two equal shallow NFBs' middle mounting web. Reverse the signed
        # side-fold orientation, preserving the original CUTTING/BEND stations.
        sign = -1 if physical.get("receiving_center_brand_anchor_inverted") else 1
        rows_x = [
            {"len":lengths[0], "angle":90*sign, "phase6_key":"receiving_left_first_40"},
            {"len":lengths[1], "formed_length": lengths[1]+t, "angle":-90*sign,
             "phase6_key":"receiving_left_second"},
            {"len":lengths[2], "angle":-90*sign, "core":"W",
             "phase6_key":"receiving_nfb_deep_base_face"},
            {"len":lengths[3], "formed_length":lengths[3]+t, "angle":90*sign,
             "phase6_key":"receiving_right_second"},
            {"len":lengths[4], "phase6_key":"receiving_right_first_40"},
        ]
    else:
        rows_x = [{"len":float(actual.width), "core":"W",
                   "phase6_key":"receiving_flat_side_face"}]
    bend_y = float(physical["base_plate_bend"])
    if actual.height <= 2*bend_y:
        raise ValueError("Receiving base top/bottom folds consume physical sheet")
    rows_y = [
        {"len":bend_y, "angle":-90, "phase6_key":"receiving_bottom_fold_20"},
        {"len":actual.height-2*bend_y, "angle":-90,
         "core":"H", "phase6_key":"receiving_base_face_height"},
        {"len":bend_y, "phase6_key":"receiving_top_fold_20"},
    ]
    return {"X":rows_x,"Y":rows_y}
