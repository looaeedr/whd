"""#2517 Engine authority for legacy Fold Designer non-core numeric settings.

Only ABSENT legacy fold/gap values inherit the original AE defaults.
Present raw bool/NaN/Inf/unparseable source cannot become valid manufacturing
numbers. W/H/D/T/FW are physical inputs and are NEVER resolved by this port.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

from . import ae

_LEGACY_PART_KEYS = {
    "door": ("door_gap_w", "door_gap_h", "door_fold_l", "door_fold_r",
             "door_fold_t", "door_fold_b"),
    "box_body": ("zl1", "zl2", "zr1", "zr2", "z_comp",
                 "head_ybottom1", "tail_ybottom1"),
    "head": ("yl1", "yr1", "ytop1", "ybottom1", "zl1", "zr1"),
    "tail": ("yl1", "yr1", "ytop1", "ybottom1", "zl1", "zr1"),
    "indicator_door": ("door_gap_w", "door_gap_h", "indicator_door_fold"),
}


def _legacy_defaults() -> dict[str, object]:
    return {
        "door_gap_w": ae.door_gap_w_def,
        "door_gap_h": ae.door_gap_h_def,
        "door_fold_l": ae.door_fold_left_def,
        "door_fold_r": ae.door_fold_right_def,
        "door_fold_t": ae.door_fold_top_def,
        "door_fold_b": ae.door_fold_bottom_def,
        "zl1": ae.zl1_def, "zl2": ae.zl2_def,
        "zr1": ae.zr1_def, "zr2": ae.zr2_def,
        "z_comp": getattr(ae, "z_comp_def", 0.0),
        "yl1": ae.yl1_def, "yr1": ae.yr1_def,
        "ytop1": ae.ytop1_def, "ybottom1": ae.ybottom1_def,
        "indicator_door_fold": getattr(ae, "indicator_small_door_fold_def", 19.0),
    }


def _finite_legacy_number(value: object, *, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} 製造來源必須是有限數值，不能是布林值")
    try:
        parsed = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} 製造來源必須是有限數值") from exc
    if not math.isfinite(parsed):
        raise ValueError(f"{field} 製造來源必須是有限數值")
    return parsed



def project_operator_fold_designer_snapshot_numeric_defaults() -> dict[str, float]:
    """Engine-owned current legacy Fold/Gap seeds for the GUI input snapshot.

    These are optional operator settings, NOT W/H/D/T/FW physical defaults.
    Read at call time so edited runtime defaults are observed on the same
    terms as the original AE-backed snapshot, and reject corrupt defaults.
    """
    values = _legacy_defaults()
    values.update({
        "base_plate_shrink_top": 0.0,
        "base_plate_shrink_bottom": 0.0,
        "base_plate_shrink_left": 0.0,
        "base_plate_shrink_right": 0.0,
        "base_plate_bend": 20.0,
        "indicator_box_fold": getattr(ae, "indicator_box_fold_def", 49.0),
    })
    keys = (
        "zl1", "zl2", "zr2", "zr1", "yl1", "yr1", "ytop1", "ybottom1",
        "door_gap_w", "door_gap_h",
        "door_fold_l", "door_fold_r", "door_fold_t", "door_fold_b",
        "base_plate_shrink_top", "base_plate_shrink_bottom",
        "base_plate_shrink_left", "base_plate_shrink_right",
        "base_plate_bend", "indicator_box_fold", "indicator_door_fold",
    )
    return {key: _finite_legacy_number(values[key], field=key) for key in keys}


def fold_designer_legacy_source_default(field: str) -> float:
    """Read an Engine-approved *legacy* D/T default for old UI compatibility.

    This function must not be used as a substitute for missing operator
    W/H/D/T/FW in a certified manufacturing request.
    """
    if field not in ("d", "t"):
        raise ValueError(f"未支援的舊版相容欄位：{field}")
    return _finite_legacy_number(getattr(ae, field.upper()), field=field)


def resolve_fold_designer_legacy_numeric_settings(
    data: Mapping[str, object], *, part_name: str,
) -> dict[str, float]:
    """Resolve exact saved Fold/Gap source or original family-neutral defaults.

    Different Families share this operator port. Physical PartSpec construction
    and Family/Policy compensation stay in existing canonical Engine owners.
    """
    if part_name not in _LEGACY_PART_KEYS:
        raise ValueError(f"未支援的 Fold Designer 板件：{part_name}")
    if not isinstance(data, Mapping):
        raise ValueError("Fold Designer 製造來源須為對應表")
    defaults = _legacy_defaults()
    result: dict[str, float] = {}
    for key in _LEGACY_PART_KEYS[part_name]:
        if key in {"head_ybottom1", "tail_ybottom1"}:
            raw = data[key] if key in data else (
                data["ybottom1"] if "ybottom1" in data else defaults["ybottom1"]
            )
        else:
            raw = data[key] if key in data else defaults[key]
        result[key] = _finite_legacy_number(raw, field=key)
    return result
