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

from typing import Mapping
from ae_engine import manufacturing_api

from ae_engine.sheetmetal_geometry import (
    CornerTypeId, CornerTypeSelection, normalize_corner_selection,
)
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

# Compatibility constants mirror the Engine's one state authority.
WRAP_LINKED = manufacturing_api.WRAP_LINKED
WRAP_FOLLOW_HEAD = manufacturing_api.WRAP_FOLLOW_HEAD
WRAP_FOLLOW_TAIL = manufacturing_api.WRAP_FOLLOW_TAIL
WRAP_INDEPENDENT = manufacturing_api.WRAP_INDEPENDENT
ENDCAP_BOTTOM_WRAP_MODES = manufacturing_api.ENDCAP_BOTTOM_WRAP_MODES


def normalize_endcap_bottom_wrap_state(snapshot: Mapping[str, object]) -> dict[str, object]:
    """GUI forwards saved lower-WRAP state to the canonical Engine."""
    return manufacturing_api.normalize_endcap_bottom_wrap_state(snapshot)


def resolve_endcap_bottom_wrap(snapshot: Mapping[str, object], part_key: str, *, state=None) -> dict[str, object]:
    """GUI reads only the Engine's actual Bottom Joint and reserve state."""
    return manufacturing_api.resolve_endcap_bottom_wrap(snapshot, part_key, state=state)


def commit_endcap_bottom_wrap_joint(snapshot: Mapping[str, object], part_key: str, enabled: bool) -> dict[str, object]:
    """GUI sends an explicit Bottom Joint edit to the public Engine API."""
    return manufacturing_api.commit_endcap_bottom_wrap_joint(snapshot, part_key, enabled)


def commit_endcap_bottom_wrap(state, part_key: str, *, enabled=None, reserve_u=None, reserve_v=None) -> dict:
    """GUI forwards the operator edit; Engine owns pair/leader/split logic."""
    return manufacturing_api.commit_endcap_bottom_wrap(
        state, part_key, enabled=enabled, reserve_u=reserve_u, reserve_v=reserve_v,
    )


def _num(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


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
    """Existing UI loader; Engine handles canonical CornerType state."""
    return manufacturing_api.endcap_corner_selection_from_raw(raw)


def normalize_endcap_fw_state(snapshot: Mapping[str, object]) -> dict[str, object]:
    """Operator FW state is owned by the Engine, not recreated by Phase6."""
    return manufacturing_api.normalize_endcap_fw_state(snapshot)


def resolve_endcap_fw(snapshot: Mapping[str, object], part_key: str, *, state=None) -> float:
    """Read the canonical Engine FW four-state contract."""
    return manufacturing_api.resolve_endcap_fw(snapshot, part_key, state=state)


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

def resolve_box_assembly_type(snapshot: Mapping[str, object]) -> CornerTypeId:
    """Legacy GUI name for the Engine-owned Assembly Intent source."""
    return manufacturing_api.resolve_endcap_assembly_type(snapshot)


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

