# -*- coding: utf-8 -*-
"""Engine-owned EndCap Head/Tail X/Y material Fold and Family/Assembly inputs.

This is the original Phase6 formula moved into the headless Engine. Original
operator FW four-state, legacy corner fallback, Vault 3T/Receiving 2T material
compensation and Head/Tail Y orientation are preserved exactly. No alternate
relief/CUTTING or new mechanical constants.
"""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from copy import deepcopy
from .assembly_intent import normalize_assembly_intent_id
from .box_body_fold_profile import (
    _num, _ui_len, _common_dimension_len, apply_outside_dimension_compensation,
)
from .cabinet_types import policy as cabinet_family_policy
from .corner_type_ui import assembly_type_from_corner_state, apply_box_assembly_type
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



def endcap_profiles_for_assembly(
    values: Mapping[str, object], stored_profiles, assembly_type, part_key: str,
) -> dict[str, list[dict]] | None:
    """Resolve current assembly intent into the one Head/Tail manufacturing Fold.

    This moves the unchanged legacy request reconciliation into the same
    Engine owner as build_endcap_xy_fold_profiles. Custom Y is preserved;
    OVERLAY physically has no left/right X bend, and returning from a flat
    X restores the certified Family Fold builder's non-flat source topology.
    """
    intent_id = normalize_assembly_intent_id(
        getattr(assembly_type, "value", assembly_type)
    )
    source = dict(values or {})
    source["assembly_type"] = intent_id
    defaults = build_endcap_xy_fold_profiles(source, part_key=part_key)
    profiles = deepcopy(dict(stored_profiles or {}))

    if not profiles:
        return defaults if intent_id == CornerTypeId.OVERLAY.value else None

    current_x = list(profiles.get("X", ()) or ())
    is_flat_x = len(current_x) == 1 and current_x[0].get("phase6_key") == "endcap_w_flat"
    if intent_id == CornerTypeId.OVERLAY.value or is_flat_x:
        profiles["X"] = deepcopy(defaults["X"])
    if not profiles.get("Y"):
        profiles["Y"] = deepcopy(defaults["Y"])
    return profiles


def endcap_editor_fold_tabs(snapshot: Mapping[str, object], part_key: str) -> list[str] | None:
    """Return only actually supported Fold editor axes for this EndCap topology."""
    key = str(part_key or "")
    if key in ENDCAP_FW_PARTS and resolve_endcap_assembly_type(snapshot) is CornerTypeId.OVERLAY:
        # Overlay EndCaps have no X BEND; do not show an invented X Fold tab.
        return ["Y"]
    return None


def normalize_endcap_profile_order(
    profiles: Mapping[str, Sequence[Mapping[str, object]]] | None,
    snapshot: Mapping[str, object], part_key: str,
) -> dict[str, list[dict]]:
    """Restore the original tail-native Y Fold order on a legacy project reload.

    Only a complete four-key legacy canonical tail may be reordered. Custom
    Fold profiles, operator material lengths and unrelated metadata survive.
    The existing Engine builder owns BEND angle/core/outside annotations.
    """
    copied = {
        "X": deepcopy(list((profiles or {}).get("X", ()))),
        "Y": deepcopy(list((profiles or {}).get("Y", ()))),
    }
    if str(part_key) != "tail":
        return copied
    canonical = ("ybottom1", "endcap_d_core", "fw", "ytop1")
    current = copied.get("Y", [])
    keyed = [seg.get("phase6_key") for seg in current if seg.get("phase6_key")]
    if len(current) != 4 or set(keyed) != set(canonical):
        return copied
    by_key = {seg.get("phase6_key"): dict(seg) for seg in current}
    defaults = build_endcap_xy_fold_profiles(snapshot, part_key="tail")["Y"]
    reordered = []
    for default in defaults:
        key = default.get("phase6_key")
        seg = by_key[key]
        if "angle" in default:
            seg["angle"] = default["angle"]
        else:
            seg.pop("angle", None)
        for name in ("ui_len_add", "core"):
            if name in default:
                seg[name] = default[name]
            else:
                seg.pop(name, None)
        reordered.append(seg)
    copied["Y"] = reordered
    return copied


def commit_box_fw(state, value: float) -> dict:
    """Explicit box-FW operator commit: box immediately retakes both end caps."""
    value = float(value)
    state["mode"] = FW_FOLLOW_BODY
    for part in ENDCAP_FW_PARTS:
        item = state.setdefault(part, {})
        item["follow_box"] = True
        item["value"] = value
    return state


def commit_endcap_fw(state, part_key: str, value: float, *, box_fw: float | None = None) -> dict:
    """Apply one explicit Head/Tail FW edit using the pair-then-split state machine."""
    part_key = str(part_key)
    if part_key not in ENDCAP_FW_PARTS:
        raise ValueError(f"不支援的封頭尾板件: {part_key}")
    if "mode" not in state:
        normalized = normalize_endcap_fw_state({"fw": 25.0 if box_fw is None else box_fw, "endcap_fw": state})
        state.clear()
        state.update(normalized)

    value = float(value)
    mode = str(state.get("mode", FW_INDEPENDENT))
    leader_mode = FW_FOLLOW_HEAD if part_key == "head" else FW_FOLLOW_TAIL
    opposite_leader = FW_FOLLOW_TAIL if part_key == "head" else FW_FOLLOW_HEAD

    for part in ENDCAP_FW_PARTS:
        state.setdefault(part, {"follow_box": False, "value": float(box_fw or value)})

    if mode == FW_FOLLOW_BODY:
        state["mode"] = leader_mode
        for part in ENDCAP_FW_PARTS:
            state[part]["follow_box"] = False
            state[part]["value"] = value
    elif mode == leader_mode:
        for part in ENDCAP_FW_PARTS:
            state[part]["follow_box"] = False
            state[part]["value"] = value
    elif mode == opposite_leader:
        state["mode"] = FW_INDEPENDENT
        for part in ENDCAP_FW_PARTS:
            state[part]["follow_box"] = False
        state[part_key]["value"] = value
    else:
        state["mode"] = FW_INDEPENDENT
        for part in ENDCAP_FW_PARTS:
            state[part]["follow_box"] = False
        state[part_key]["value"] = value
    return state


def set_endcap_fw_follow(state, part_key: str, follow_box: bool, *, box_fw: float) -> dict:
    """Legacy/manual follow control retained for old callers and old projects."""
    part_key = str(part_key)
    if part_key not in ENDCAP_FW_PARTS:
        raise ValueError(f"不支援的封頭尾板件: {part_key}")
    item = state.setdefault(part_key, {})
    if not follow_box and bool(item.get("follow_box", True)):
        item["value"] = float(box_fw)
    item["follow_box"] = bool(follow_box)
    item.setdefault("value", float(box_fw))
    if all(bool((state.get(p) or {}).get("follow_box", True)) for p in ENDCAP_FW_PARTS):
        state["mode"] = FW_FOLLOW_BODY
    else:
        state["mode"] = FW_INDEPENDENT
    return item


def set_endcap_fw_override(state, part_key: str, value: float) -> dict:
    """Legacy per-part override; new operator UI should use ``commit_endcap_fw``."""
    part_key = str(part_key)
    if part_key not in ENDCAP_FW_PARTS:
        raise ValueError(f"不支援的封頭尾板件: {part_key}")
    item = state.setdefault(part_key, {"follow_box": False})
    item["follow_box"] = False
    item["value"] = float(value)
    state["mode"] = FW_INDEPENDENT
    return item


def selection_to_raw(selection):
    selection = normalize_corner_selection(selection)
    raw = {"type_id": selection.type_id.value, "rotation_quadrants": 0}
    if selection.cross_mode is not None:
        raw["cross_mode"] = selection.cross_mode.value
    if selection.direction is not None:
        raw["direction"] = selection.direction.value
    if selection.amount_t is not None:
        raw["amount_t"] = float(selection.amount_t)
    if selection.secondary_retain_t is not None:
        raw["secondary_retain_t"] = float(selection.secondary_retain_t)
    if selection.secondary_depth_t is not None:
        raw["secondary_depth_t"] = float(selection.secondary_depth_t)
    return raw


def apply_box_assembly_type_to_raw_state(
    corner_state, pair_same, type_id, *, reset_bottom_defaults=False
):
    """Apply shared box assembly semantics to the bridge's JSON-safe corner state.

    ``reset_bottom_defaults`` is reserved for an explicit operator assembly
    selection.  Normal load/render synchronization leaves manually edited
    EndCap bottom manufacturing corners untouched.
    """
    typed = {}
    for part in ("head", "tail"):
        typed[part] = {
            key: selection_from_raw(value)
            for key, value in dict((corner_state or {}).get(part) or {}).items()
        }
    apply_box_assembly_type(
        typed, pair_same, CornerTypeId(type_id),
        reset_bottom_defaults=bool(reset_bottom_defaults),
    )
    for part, corners in typed.items():
        target = corner_state.setdefault(part, {})
        target.clear()
        target.update({key: selection_to_raw(value) for key, value in corners.items()})
    return CornerTypeId(type_id)


def legacy_corner_projection_for_intent(value) -> CornerTypeId:
    """Project registered high-level intent to legacy Head/Tail corner mirror.

    WRAP_OVERLAY projects as OVERLAY only in the old corner-state format.
    The real BOTTOM WRAP remains exclusively in Assembly Joint Graph.
    """
    stable = normalize_assembly_intent_id(value)
    if stable == "WRAP_OVERLAY":
        return CornerTypeId.OVERLAY
    return CornerTypeId(stable)
