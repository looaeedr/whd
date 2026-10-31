# -*- coding: utf-8 -*-
"""Engine-owned standard finished-part X/Y Fold material profiles.

Canonical move of the approved Door, BasePlate, IndicatorBox/IndicatorDoor
and fallback 3-panel UI-to-material profile conversion. Custom physical
parts require their separate explicit persisted-contract manufacturing path.
"""
from __future__ import annotations

import re
from typing import Mapping
from .box_body_fold_profile import _num, _ui_len, apply_outside_dimension_compensation

def _is_door_part_key(value: object) -> bool:
    key = str(value or "")
    return key == "door" or re.fullmatch(r"door_c\d+_r\d+", key) is not None


def _is_base_plate_part_key(value: object) -> bool:
    key = str(value or "")
    return (
        key == "base_plate"
        or re.fullmatch(r"base_plate_c\d+_r\d+", key) is not None
    )



def _three_segment_profile(
    left,
    center,
    right,
    *,
    left_key=None,
    center_key=None,
    right_key=None,
):
    items = [
        {"len": _ui_len(left), "angle": -90},
        {"len": _ui_len(center), "angle": -90},
        {"len": _ui_len(right)},
    ]
    for item, key in zip(items, (left_key, center_key, right_key)):
        if key:
            item["phase6_key"] = key
    return items


def build_standard_part_fold_profiles(
    snapshot: Mapping[str, object],
    part_key: str,
) -> dict[str, list[dict]]:
    """Build the existing X/Y profiles for one non-vault panel."""
    # Custom parts have a separate persisted-authority contract.
    # Standard Fold API must not silently fabricate them as generic panels.
    if str(part_key).startswith("custom:"):
        raise ValueError("CUSTOM_FOLD_REQUIRES_CUSTOM_API")
    dims = dict((snapshot.get("part_dimensions") or {}).get(part_key, {}) or {})
    w = _num(dims.get("width", snapshot.get("w", 500)), 500)
    h = _num(dims.get("height", snapshot.get("h", 600)), 600)

    if _is_door_part_key(part_key):
        t = _num(snapshot.get("t", 2), 2)
        outside_add = max(0.0, 2.0 * t)
        profiles = {
            "X": _three_segment_profile(
                snapshot.get("door_fold_l", 20),
                max(0.0, w - outside_add),
                snapshot.get("door_fold_r", 20),
                left_key="door_fold_l",
                center_key="door_face_w",
                right_key="door_fold_r",
            ),
            "Y": _three_segment_profile(
                snapshot.get("door_fold_b", 20),
                max(0.0, h - outside_add),
                snapshot.get("door_fold_t", 20),
                left_key="door_fold_b",
                center_key="door_face_h",
                right_key="door_fold_t",
            ),
        }
        profiles["X"][1]["core"] = "門包外 W"
        profiles["Y"][1]["core"] = "門包外 H"
        profiles["X"] = apply_outside_dimension_compensation(profiles["X"], t)
        profiles["Y"] = apply_outside_dimension_compensation(profiles["Y"], t)
        return profiles

    if part_key == "base_plate" and str(snapshot.get("model") or "").strip() in {"受電箱", "RECEIVING"}:
        # Share the ONE actual FinalScene-derived BEND profile with assembly Z.
        from .receiving_base_plate_3d_profiles import receiving_base_plate_3d_profiles
        physical = receiving_base_plate_3d_profiles(snapshot)
        if physical is not None:
            return physical

    if _is_base_plate_part_key(part_key):
        bend = snapshot.get("base_plate_bend", 20)
        profiles = {
            "X": _three_segment_profile(
                bend,
                w,
                bend,
                left_key="base_bend_l",
                center_key="base_face_w",
                right_key="base_bend_r",
            ),
            "Y": _three_segment_profile(
                bend,
                h,
                bend,
                left_key="base_bend_b",
                center_key="base_face_h",
                right_key="base_bend_t",
            ),
        }
        t = _num(snapshot.get("t", 2), 2)
        profiles["X"] = apply_outside_dimension_compensation(profiles["X"], t)
        profiles["Y"] = apply_outside_dimension_compensation(profiles["Y"], t)
        return profiles

    if part_key == "indicator_box":
        fold = _num(snapshot.get("indicator_box_fold", 49), 49)
        t = _num(snapshot.get("t", 2), 2)
        x_core = max(0.0, w - 2.0 * fold)
        y_core = max(0.0, h - 2.0 * fold)
        profiles = {
            "X": _three_segment_profile(
                fold,
                x_core,
                fold,
                left_key="ib_fold_l",
                center_key="ib_face_w",
                right_key="ib_fold_r",
            ),
            "Y": _three_segment_profile(
                fold,
                y_core,
                fold,
                left_key="ib_fold_b",
                center_key="ib_face_h",
                right_key="ib_fold_t",
            ),
        }
        profiles["X"] = apply_outside_dimension_compensation(profiles["X"], t)
        profiles["Y"] = apply_outside_dimension_compensation(profiles["Y"], t)
        return profiles

    if part_key == "indicator_door":
        fold = _num(snapshot.get("indicator_door_fold", 19), 19)
        t = _num(snapshot.get("t", 2), 2)
        x_core = max(0.0, w - 2.0 * fold)
        y_core = max(0.0, h - 2.0 * fold)
        profiles = {
            "X": _three_segment_profile(
                fold,
                x_core,
                fold,
                left_key="id_fold_l",
                center_key="id_face_w",
                right_key="id_fold_r",
            ),
            "Y": _three_segment_profile(
                fold,
                y_core,
                fold,
                left_key="id_fold_b",
                center_key="id_face_h",
                right_key="id_fold_t",
            ),
        }
        profiles["X"] = apply_outside_dimension_compensation(profiles["X"], t)
        profiles["Y"] = apply_outside_dimension_compensation(profiles["Y"], t)
        return profiles

    t = _num(snapshot.get("t", 2), 2)
    profiles = {
        "X": _three_segment_profile(25, w, 25),
        "Y": _three_segment_profile(25, h, 25),
    }
    profiles["X"] = apply_outside_dimension_compensation(profiles["X"], t)
    profiles["Y"] = apply_outside_dimension_compensation(profiles["Y"], t)
    return profiles


