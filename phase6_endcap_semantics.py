# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Phase6 封頭／封尾裝配與 CornerType 狀態語意。

此模組不依賴 Tk、renderer、ProjectSession 或 SettingsService。
"""
from __future__ import annotations

import math
from typing import Mapping

from ae_engine.sheetmetal_geometry import (
    CornerTypeId, CornerTypeSelection, normalize_corner_selection,
)
from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.corner_type_ui import (
    apply_box_assembly_type, assembly_type_from_corner_state,
)

ASSEMBLY_TYPE_LABELS = {
    CornerTypeId.INSERT: "嵌入",
    CornerTypeId.OVERLAY: "貼外",
    CornerTypeId.INSERT_OVERLAY: "嵌入貼外",
    "WRAP_OVERLAY": "包覆貼外",
}
ASSEMBLY_LABEL_TO_TYPE = {label: type_id for type_id, label in ASSEMBLY_TYPE_LABELS.items()}


def assembly_intent_value(value) -> str:
    raw = getattr(value, "value", value)
    from ae_engine.assembly_intent import normalize_assembly_intent_id
    return normalize_assembly_intent_id(raw)


def assembly_intent_label(value) -> str:
    stable = assembly_intent_value(value)
    for key, label in ASSEMBLY_TYPE_LABELS.items():
        if getattr(key, "value", key) == stable:
            return label
    raise ValueError(f"不支援的箱體組合方式：{stable}")


def legacy_corner_projection_for_intent(value) -> CornerTypeId:
    stable = assembly_intent_value(value)
    if stable == "WRAP_OVERLAY":
        return CornerTypeId.OVERLAY
    return CornerTypeId(stable)
ENDCAP_FW_PARTS = ("head", "tail")

FW_FOLLOW_BODY = "FOLLOW_BODY"
FW_FOLLOW_HEAD = "FOLLOW_HEAD"
FW_FOLLOW_TAIL = "FOLLOW_TAIL"
FW_INDEPENDENT = "INDEPENDENT"
ENDCAP_FW_MODES = (FW_FOLLOW_BODY, FW_FOLLOW_HEAD, FW_FOLLOW_TAIL, FW_INDEPENDENT)

WRAP_LINKED = "LINKED"
WRAP_FOLLOW_HEAD = "FOLLOW_HEAD"
WRAP_FOLLOW_TAIL = "FOLLOW_TAIL"
WRAP_INDEPENDENT = "INDEPENDENT"
ENDCAP_BOTTOM_WRAP_MODES = (WRAP_LINKED, WRAP_FOLLOW_HEAD, WRAP_FOLLOW_TAIL, WRAP_INDEPENDENT)


def _default_bottom_wrap_item(snapshot: Mapping[str, object]) -> dict[str, object]:
    return {
        "enabled": cabinet_family_policy.default_bottom_wrap_enabled(snapshot),
        "reserve_u": 2.0,
        "reserve_v": 1.0,
    }


def _bool_flag(raw, default: bool = False) -> bool:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int):
        return raw != 0
    if isinstance(raw, str):
        token = raw.strip().lower()
        if token in {"1", "true", "yes", "on"}:
            return True
        if token in {"0", "false", "no", "off", ""}:
            return False
    return bool(raw)


def _strict_finite_float(raw, field_name: str) -> float:
    if isinstance(raw, bool):
        raise ValueError(f"{field_name} 不可為布林值")
    value = float(raw)
    if not math.isfinite(value):
        raise ValueError(f"{field_name} 必須為有限數值")
    return value


def _normalize_bottom_wrap_item(raw, default):
    raw = raw if isinstance(raw, Mapping) else {}
    raw_u = raw.get("reserve_u", default["reserve_u"])
    if isinstance(raw_u, bool):
        reserve_u = float(default["reserve_u"])
    else:
        try:
            val_u = float(raw_u)
            reserve_u = max(0.0, val_u) if math.isfinite(val_u) else float(default["reserve_u"])
        except (TypeError, ValueError):
            reserve_u = float(default["reserve_u"])
    raw_v = raw.get("reserve_v", default["reserve_v"])
    if isinstance(raw_v, bool):
        reserve_v = float(default["reserve_v"])
    else:
        try:
            val_v = float(raw_v)
            reserve_v = max(0.0, val_v) if math.isfinite(val_v) else float(default["reserve_v"])
        except (TypeError, ValueError):
            reserve_v = float(default["reserve_v"])
    return {
        "enabled": _bool_flag(raw.get("enabled", default["enabled"]), default=bool(default["enabled"])),
        "reserve_u": reserve_u,
        "reserve_v": reserve_v,
    }


def normalize_endcap_bottom_wrap_state(snapshot: Mapping[str, object]) -> dict[str, object]:
    """Canonical Head/Tail lower-WRAP pair state.

    Default receiving behaviour is linked.  Editing one side makes it the pair
    leader; editing the opposite side afterwards splits the pair to independent
    values, matching the existing EndCap FW linkage semantics.
    """
    raw = snapshot.get("endcap_bottom_wrap")
    if raw is None:
        workspace = snapshot.get("workspace")
        if isinstance(workspace, Mapping):
            raw = workspace.get("endcap_bottom_wrap")
    raw = raw if isinstance(raw, Mapping) else {}
    default = _default_bottom_wrap_item(snapshot)
    head = _normalize_bottom_wrap_item(raw.get("head"), default)
    tail = _normalize_bottom_wrap_item(raw.get("tail"), default)
    mode = str(raw.get("mode", WRAP_LINKED) or WRAP_LINKED).upper()
    if mode not in ENDCAP_BOTTOM_WRAP_MODES:
        mode = WRAP_LINKED
    result = {"mode": mode, "head": head, "tail": tail}
    if mode == WRAP_LINKED:
        # A linked snapshot stores one effective value; prefer Head as stable source.
        result["tail"] = dict(result["head"])
    elif mode == WRAP_FOLLOW_HEAD:
        result["tail"] = dict(result["head"])
    elif mode == WRAP_FOLLOW_TAIL:
        result["head"] = dict(result["tail"])
    return result


def resolve_endcap_bottom_wrap(snapshot: Mapping[str, object], part_key: str, *, state=None) -> dict[str, object]:
    part_key = str(part_key)
    if part_key not in ENDCAP_FW_PARTS:
        raise ValueError(f"不支援的封頭尾板件: {part_key}")
    normalized = normalize_endcap_bottom_wrap_state(snapshot) if state is None else state
    item = dict((normalized or {}).get(part_key) or _default_bottom_wrap_item(snapshot))
    enabled = bool(item.get("enabled", False))
    # Once an explicit Joint Graph exists, UI state is only a projection of the
    # BOTTOM relation.  The legacy enabled mirror may still carry reserve/link
    # persistence but may not override the graph.
    if "assembly_joints" in snapshot or "assembly_joint_schema_version" in snapshot:
        try:
            from ae_engine.assembly_joint import AssemblyJointRelation, edge_relation_for_part
            relation = edge_relation_for_part(snapshot, part_key, "BOTTOM")
            if relation is not None:
                enabled = relation is AssemblyJointRelation.WRAP
        except Exception:
            pass
    return {
        "enabled": enabled,
        "reserve_u": max(0.0, _num(item.get("reserve_u", 2.0), 2.0)),
        "reserve_v": max(0.0, _num(item.get("reserve_v", 1.0), 1.0)),
    }


def commit_endcap_bottom_wrap_joint(snapshot: Mapping[str, object], part_key: str, enabled: bool) -> dict[str, object]:
    """Write the receiving switch to the canonical BOTTOM AssemblyJoint."""
    from ae_engine.assembly_joint import AssemblyJointRelation, set_part_edge_relation
    return set_part_edge_relation(
        snapshot, str(part_key), "BOTTOM",
        AssemblyJointRelation.WRAP if bool(enabled) else AssemblyJointRelation.INSERT,
    )


def commit_endcap_bottom_wrap(state, part_key: str, *, enabled=None, reserve_u=None, reserve_v=None) -> dict:
    part_key = str(part_key)
    if part_key not in ENDCAP_FW_PARTS:
        raise ValueError(f"不支援的封頭尾板件: {part_key}")
    mode = str(state.get("mode", WRAP_LINKED) or WRAP_LINKED)
    leader = WRAP_FOLLOW_HEAD if part_key == "head" else WRAP_FOLLOW_TAIL
    opposite = WRAP_FOLLOW_TAIL if part_key == "head" else WRAP_FOLLOW_HEAD
    base = dict(state.get(part_key) or {"enabled": True, "reserve_u": 2.0, "reserve_v": 1.0})
    if enabled is not None:
        base["enabled"] = _bool_flag(enabled, default=False)
    if reserve_u is not None:
        base["reserve_u"] = max(0.0, _strict_finite_float(reserve_u, "reserve_u"))
    if reserve_v is not None:
        base["reserve_v"] = max(0.0, _strict_finite_float(reserve_v, "reserve_v"))
    if mode in {WRAP_LINKED, leader}:
        state["mode"] = leader
        state["head"] = dict(base)
        state["tail"] = dict(base)
    elif mode == opposite:
        state["mode"] = WRAP_INDEPENDENT
        state.setdefault("head", dict(base))
        state.setdefault("tail", dict(base))
        state[part_key] = dict(base)
    else:
        state["mode"] = WRAP_INDEPENDENT
        state.setdefault("head", dict(base))
        state.setdefault("tail", dict(base))
        state[part_key] = dict(base)
    return state


def _num(value, default=0.0):
    if isinstance(value, bool):
        return float(default)
    try:
        result = float(value)
    except (TypeError, ValueError):
        return float(default)
    return result if math.isfinite(result) else float(default)


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
            "follow_box": _bool_flag(item.get("follow_box", True), default=True),
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
    if part_key not in ENDCAP_FW_PARTS:
        raise ValueError(f"不支援的封頭尾板件: {part_key}")
    box_fw = _num(snapshot.get("fw", 25), 25)
    state = normalize_endcap_fw_state(snapshot) if state is None else state
    mode = str((state or {}).get("mode", FW_INDEPENDENT))
    item = dict((state or {}).get(part_key) or {})
    if mode == FW_FOLLOW_BODY or bool(item.get("follow_box", False)):
        return box_fw
    return _num(item.get("value", box_fw), box_fw)


def commit_box_fw(state, value: float) -> dict:
    """Explicit box-FW operator commit: box immediately retakes both end caps."""
    value = _strict_finite_float(value, "value")
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
    value = _strict_finite_float(value, "value")
    resolved_box_fw = None if box_fw is None else _strict_finite_float(box_fw, "box_fw")
    if "mode" not in state:
        normalized = normalize_endcap_fw_state(
            {"fw": 25.0 if resolved_box_fw is None else resolved_box_fw, "endcap_fw": state}
        )
        state.clear()
        state.update(normalized)

    mode = str(state.get("mode", FW_INDEPENDENT))
    leader_mode = FW_FOLLOW_HEAD if part_key == "head" else FW_FOLLOW_TAIL
    opposite_leader = FW_FOLLOW_TAIL if part_key == "head" else FW_FOLLOW_HEAD

    default_part_fw = value if resolved_box_fw is None else resolved_box_fw
    for part in ENDCAP_FW_PARTS:
        state.setdefault(part, {"follow_box": False, "value": default_part_fw})

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
    resolved_box_fw = _strict_finite_float(box_fw, "box_fw")
    follow_flag = _bool_flag(follow_box, default=True)
    item = state.setdefault(part_key, {})
    if not follow_flag and _bool_flag(item.get("follow_box", True), default=True):
        item["value"] = resolved_box_fw
    item["follow_box"] = follow_flag
    item.setdefault("value", resolved_box_fw)
    if all(_bool_flag((state.get(p) or {}).get("follow_box", True), default=True) for p in ENDCAP_FW_PARTS):
        state["mode"] = FW_FOLLOW_BODY
    else:
        state["mode"] = FW_INDEPENDENT
    return item


def set_endcap_fw_override(state, part_key: str, value: float) -> dict:
    """Legacy per-part override; new operator UI should use ``commit_endcap_fw``."""
    part_key = str(part_key)
    if part_key not in ENDCAP_FW_PARTS:
        raise ValueError(f"不支援的封頭尾板件: {part_key}")
    resolved_value = _strict_finite_float(value, "value")
    item = state.setdefault(part_key, {"follow_box": False})
    item["follow_box"] = False
    item["value"] = resolved_value
    state["mode"] = FW_INDEPENDENT
    return item

def resolve_box_assembly_type(snapshot: Mapping[str, object]) -> CornerTypeId:
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
            stable = assembly_intent_value(raw)
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

