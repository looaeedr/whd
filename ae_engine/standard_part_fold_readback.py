# -*- coding: utf-8 -*-
"""Engine-owned reverse mapping of material Fold rows into persisted Settings.

Preserve the approved standard Door/BasePlate/Indicator semantic rules while
preventing the GUI adapter from interpreting manufacturing Fold profiles.
"""
from __future__ import annotations

from .standard_part_fold_profiles import _is_door_part_key, _is_base_plate_part_key


def _profile_value(profile, key, default=0):
    for seg in profile or ():
        if seg.get("phase6_key") == key:
            return float(seg.get("len") or 0)
    return float(default or 0)


def read_standard_part_fold_profiles(part_key, profiles, original_snapshot):
    """Canonical reverse mapping for standard saved-part fold profiles."""
    x = list((profiles or {}).get("X", ()))
    y = list((profiles or {}).get("Y", ()))
    if _is_door_part_key(part_key):
        return {
            "door_fold_l": _profile_value(x, "door_fold_l", original_snapshot.get("door_fold_l", 20)),
            "door_fold_r": _profile_value(x, "door_fold_r", original_snapshot.get("door_fold_r", 20)),
            "door_fold_b": _profile_value(y, "door_fold_b", original_snapshot.get("door_fold_b", 20)),
            "door_fold_t": _profile_value(y, "door_fold_t", original_snapshot.get("door_fold_t", 20)),
        }
    if (str(part_key) == "base_plate"
            and str(original_snapshot.get("model") or "").strip()
            in {"受電箱", "RECEIVING"}):
        # The Receiving root base is NOT the generic four-flange plate.
        # Its X can contain four physical bends (or none for a flat side),
        # while Y still has the source BEND20. The true source is the
        # committed NFB/CSV-derived FinalScene, not base_plate_bend.
        # Never reverse-project the physical profile or a stale workspace
        # cache back into the generic four-equal-bends setting.
        from .receiving_base_plate_3d_profiles import (
            receiving_base_plate_3d_profiles,
        )
        if receiving_base_plate_3d_profiles(original_snapshot) is not None:
            return {}
    if _is_base_plate_part_key(part_key):
        vals = [
            _profile_value(x, "base_bend_l", original_snapshot.get("base_plate_bend", 20)),
            _profile_value(x, "base_bend_r", original_snapshot.get("base_plate_bend", 20)),
            _profile_value(y, "base_bend_b", original_snapshot.get("base_plate_bend", 20)),
            _profile_value(y, "base_bend_t", original_snapshot.get("base_plate_bend", 20)),
        ]
        if len(set(vals)) != 1:
            raise ValueError("底板四邊折彎目前由 Phase6 共用一個 bend 值，四邊必須相同")
        return {"base_plate_bend": vals[0]}
    if part_key == "indicator_box":
        vals = [
            _profile_value(x, "ib_fold_l", original_snapshot.get("indicator_box_fold", 49)),
            _profile_value(x, "ib_fold_r", original_snapshot.get("indicator_box_fold", 49)),
            _profile_value(y, "ib_fold_b", original_snapshot.get("indicator_box_fold", 49)),
            _profile_value(y, "ib_fold_t", original_snapshot.get("indicator_box_fold", 49)),
        ]
        if len(set(vals)) != 1:
            raise ValueError("指示燈盒四邊折彎必須相同")
        return {"indicator_box_fold": vals[0]}
    if part_key == "indicator_door":
        vals = [
            _profile_value(x, "id_fold_l", original_snapshot.get("indicator_door_fold", 19)),
            _profile_value(x, "id_fold_r", original_snapshot.get("indicator_door_fold", 19)),
            _profile_value(y, "id_fold_b", original_snapshot.get("indicator_door_fold", 19)),
            _profile_value(y, "id_fold_t", original_snapshot.get("indicator_door_fold", 19)),
        ]
        if len(set(vals)) != 1:
            raise ValueError("指示燈小門四邊折彎必須相同")
        return {"indicator_door_fold": vals[0]}
    return {}
