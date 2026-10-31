# -*- coding: utf-8 -*-
"""Engine-owned EndCap Head/Tail X/Y material Fold and Family/Assembly inputs.

This is the original Phase6 formula moved into the headless Engine. Original
operator FW four-state, legacy corner fallback, Vault 3T/Receiving 2T material
compensation and Head/Tail Y orientation are preserved exactly. No alternate
relief/CUTTING or new mechanical constants.
"""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from .assembly_intent import normalize_assembly_intent_id
from .box_body_fold_profile import (
    _num, _ui_len, _common_dimension_len, apply_outside_dimension_compensation,
)
from .cabinet_types import policy as cabinet_family_policy
from .corner_type_ui import assembly_type_from_corner_state
from .sheetmetal_geometry import CornerTypeId, CornerTypeSelection, normalize_corner_selection

ENDCAP_FW_PARTS = ("head", "tail")
FW_FOLLOW_BODY = "FOLLOW_BODY"
FW_FOLLOW_HEAD = "FOLLOW_HEAD"
FW_FOLLOW_TAIL = "FOLLOW_TAIL"
FW_INDEPENDENT = "INDEPENDENT"
ENDCAP_FW_MODES = (FW_FOLLOW_BODY, FW_FOLLOW_HEAD, FW_FOLLOW_TAIL, FW_INDEPENDENT)

def selection_from_raw(raw):
    if not isinstance(raw, Mapping):
        return CornerTypeSelection(CornerTypeId.CROSS)
    try:
        selection = CornerTypeSelection(
            CornerTypeId(str(raw.get("type_id", "CROSS")).upper()),
            int(raw.get("rotation_quadrants", 0) or 0),
            cross_mode=raw.get("cross_mode"),
            direction=raw.get("direction"),
            amount_t=raw.get("amount_t"),
            secondary_retain_t=raw.get("secondary_retain_t"),
            secondary_depth_t=raw.get("secondary_depth_t"),
        )
        return normalize_corner_selection(selection)
    except (TypeError, ValueError):
        return CornerTypeSelection(CornerTypeId.CROSS)


def normalize_endcap_fw_state(snapshot: Mapping[str, object]) -> dict[str, object]:
    """Return the canonical Head/Tail FW control state.

    Operator semantics are four-state:
    ``FOLLOW_BODY`` -> box FW controls both end caps;
    ``FOLLOW_HEAD`` / ``FOLLOW_TAIL`` -> the first edited end cap controls the pair;
    ``INDEPENDENT`` -> after the opposite end cap is edited, each keeps its own value.

    Legacy files had only per-part ``follow_box`` flags.  Mixed legacy state is
    preserved as independent values/flags instead of inventing a pair leader.
    """
    box_fw = _num(snapshot.get("fw", 25), 25)
    raw = snapshot.get("endcap_fw")
    if raw is None:
        workspace = snapshot.get("workspace")
        if isinstance(workspace, Mapping):
            raw = workspace.get("endcap_fw")
    raw = raw if isinstance(raw, Mapping) else {}

    raw_items = {}
    for part in ENDCAP_FW_PARTS:
        item = raw.get(part) if isinstance(raw, Mapping) else None
        item = item if isinstance(item, Mapping) else {}
        raw_items[part] = {
            "follow_box": bool(item.get("follow_box", True)),
            "value": _num(item.get("value", box_fw), box_fw),
        }

    requested_mode = str(raw.get("mode", "") or "").upper()
    if requested_mode in ENDCAP_FW_MODES:
        mode = requested_mode
    elif all(raw_items[p]["follow_box"] for p in ENDCAP_FW_PARTS):
        mode = FW_FOLLOW_BODY
    else:
        # Old files cannot express which end cap became the pair leader, so do
        # not guess.  Keep their numerical/follow-box behaviour as independent.
        mode = FW_INDEPENDENT

    result = {"mode": mode, **raw_items}
    if mode == FW_FOLLOW_BODY:
        for part in ENDCAP_FW_PARTS:
            result[part]["follow_box"] = True
            result[part]["value"] = box_fw
    elif mode == FW_FOLLOW_HEAD:
        value = _num(result["head"].get("value", box_fw), box_fw)
        for part in ENDCAP_FW_PARTS:
            result[part]["follow_box"] = False
            result[part]["value"] = value
    elif mode == FW_FOLLOW_TAIL:
        value = _num(result["tail"].get("value", box_fw), box_fw)
        for part in ENDCAP_FW_PARTS:
            result[part]["follow_box"] = False
            result[part]["value"] = value
    return result


def resolve_endcap_fw(snapshot: Mapping[str, object], part_key: str, *, state=None) -> float:
    part_key = str(part_key)
    box_fw = _num(snapshot.get("fw", 25), 25)
    state = normalize_endcap_fw_state(snapshot) if state is None else state
    mode = str((state or {}).get("mode", FW_INDEPENDENT))
    item = dict((state or {}).get(part_key) or {})
    if mode == FW_FOLLOW_BODY or bool(item.get("follow_box", False)):
        return box_fw
    return _num(item.get("value", box_fw), box_fw)


def resolve_endcap_assembly_type(snapshot: Mapping[str, object]) -> CornerTypeId:
    """Resolve the persisted high-level intent mirror first.

    Top CornerType is a legacy projection only.  It is consulted solely when
    old data has no persisted Assembly Intent mirror.
    """
    raw = snapshot.get("assembly_type")
    if raw is None:
        workspace = snapshot.get("workspace")
        if isinstance(workspace, Mapping):
            raw = workspace.get("assembly_type")
    if raw is not None:
        try:
            stable = normalize_assembly_intent_id(raw)
            return CornerTypeId(stable) if stable != "WRAP_OVERLAY" else stable
        except (TypeError, ValueError):
            pass

    converted = {}
    for part, corners in dict(snapshot.get("corner_state") or {}).items():
        converted[part] = {
            key: selection_from_raw(value)
            for key, value in dict(corners or {}).items()
        }
    return assembly_type_from_corner_state(converted)

def build_endcap_xy_fold_profiles(snapshot: Mapping[str, object], *, part_key: str = "head") -> dict[str, list[dict]]:
    """Map authoritative EndCap bends into the editor without mirroring tail.

    Head manufacturing scenes are Y-normalized once by AE, while tail scenes stay
    in their native orientation.  Therefore the editor Y-chain order must be
    part-aware: head walks top->bottom after normalization; tail walks the native
    bottom->top scene.  Lengths remain authoritative material lengths.
    """
    w = _num(snapshot.get("w", 500), 500)
    d = _num(snapshot.get("d", 200), 200)
    t = _num(snapshot.get("t", 2), 2)
    fw = resolve_endcap_fw(snapshot, part_key)
    material_fw = cabinet_family_policy.endcap_fw_profile_uses_material_dimensions(snapshot)
    if material_fw:
        # Receiving operator FW is outside 29; canonical Y Fold Profile stores material 25.
        fw = max(0.0, float(fw) - 2.0 * t)
    x_core = max(0.0, w - 4.0 * t)
    depth_comp_t = cabinet_family_policy.endcap_depth_comp_t(snapshot)
    y_core = max(0.0, d - depth_comp_t * t)
    outside_add = max(0.0, 2.0 * t)
    x_profile = [
        {"len": _ui_len(snapshot.get("yl1", 15)), "angle": -90, "phase6_key": "yl1"},
        {"len": _common_dimension_len(snapshot, x_core), "angle": -90, "phase6_key": "endcap_w_core",
         "core": "W-2T"},
        {"len": _ui_len(snapshot.get("yr1", 15)), "phase6_key": "yr1"},
    ]
    if resolve_endcap_assembly_type(snapshot) is CornerTypeId.OVERLAY:
        # 貼外型封頭／封尾沒有左右 X 折彎，因此整片 X 向材料寬就是 W。
        # 下方 CROSS + EXTRA_CUT 的 1.5T 只改角落 CUTTING，不得把
        # 原本 INSERT 型的 yl1 / yr1 折邊寬度加回整張材料外框。
        x_profile = [
            {"len": _common_dimension_len(snapshot, w), "phase6_key": "endcap_w_flat", "core": "W-FLAT"}
        ]

    profiles = {
        "X": x_profile,
        "Y": (
            [
                {"len": _ui_len(snapshot.get("ybottom1", 15)), "angle": -90, "phase6_key": "ybottom1"},
                {"len": _common_dimension_len(snapshot, y_core), "angle": -90, "phase6_key": "endcap_d_core",
                 "core": "D-T"},
                {"len": _ui_len(fw), "angle": -90, "phase6_key": "fw"},
                {"len": _ui_len(snapshot.get("ytop1", 16)), "phase6_key": "ytop1"},
            ]
            if str(part_key) == "tail" else
            [
                {"len": _ui_len(snapshot.get("ytop1", 16)), "angle": -90, "phase6_key": "ytop1"},
                {"len": _ui_len(fw), "angle": -90, "phase6_key": "fw"},
                {"len": _common_dimension_len(snapshot, y_core), "angle": -90, "phase6_key": "endcap_d_core",
                 "core": "D-T"},
                {"len": _ui_len(snapshot.get("ybottom1", 15)), "phase6_key": "ybottom1"},
            ]
        ),
    }
    profiles["X"] = apply_outside_dimension_compensation(profiles["X"], t)
    profiles["Y"] = apply_outside_dimension_compensation(profiles["Y"], t)
    return profiles

