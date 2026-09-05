# -*- coding: utf-8 -*-
"""Phase6 箱身多結構型態的單一狀態模型。"""
from __future__ import annotations

from copy import deepcopy
from enum import Enum
from typing import Mapping


class BoxBodyStructureType(str, Enum):
    """箱身正式結構型態。"""

    INTEGRAL = "integral"
    TWO_PIECE_W_SPLIT = "two_piece_w_split"
    THREE_PIECE_W_SPLIT = "three_piece_w_split"
    THREE_PIECE_SIDE_BACK_SPLIT = "three_piece_side_back_split"


DEFAULT_STRUCTURE_TYPE = BoxBodyStructureType.INTEGRAL


def _default_join_settings() -> dict:
    return {
        "seam_bend": 12.0,
        "endcap_extra_relief": 5.0,
        "endcap_single_side_meat_t": 0.5,
        "baseplate_relief_length": 20.0,
        "baseplate_single_side_meat_t": 0.5,
    }


def default_box_body_structure_state() -> dict:
    """建立可持久化的 canonical structure state。

    尺寸分配留空代表尚無該型態的使用者歷史值；真正第一次啟用時由
    resolved geometry 依當下 W 建立預設，避免在讀檔階段複製 W Source of Truth。
    """
    return {
        "active_type": DEFAULT_STRUCTURE_TYPE.value,
        "locked": True,
        "configs": {
            BoxBodyStructureType.INTEGRAL.value: {},
            BoxBodyStructureType.TWO_PIECE_W_SPLIT.value: {
                "left_w": None,
                "right_w": None,
                **_default_join_settings(),
            },
            BoxBodyStructureType.THREE_PIECE_W_SPLIT.value: {
                "left_w": None,
                "middle_w": None,
                "right_w": None,
                **_default_join_settings(),
            },
            BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value: {
                "side_rear_bend": 15.0,
                "back_width_comp_t": 0.5,
                # Receiving EndCap lower-face WRAP manufacturing defaults.
                # Family adapters may override these per Head/Tail before building
                # a PartSpec; keeping them here makes old/headless snapshots stable.
                "bottom_external_wrap": True,
                "bottom_relief_reserve_u": 2.0,
                "bottom_relief_reserve_v": 1.0,
                "baseplate_relief_length": 20.0,
                "baseplate_single_side_meat_t": 0.5,
            },
        },
    }


def _structure_type(value) -> BoxBodyStructureType:
    if isinstance(value, BoxBodyStructureType):
        return value
    try:
        return BoxBodyStructureType(str(value))
    except (TypeError, ValueError):
        return DEFAULT_STRUCTURE_TYPE


def legacy_box_body_structure_locked(model_name) -> bool:
    """Legacy-only lock fallback for snapshots that predate structure state.

    New projects still default to locked.  This helper is consulted only when an
    old snapshot has no explicit structure lock, preserving the existing model
    editability convention without turning it into a permanent model rule.
    """
    name = str(model_name or "").strip()
    return name not in {"自訂", "未知類型"}


def normalize_box_body_structure_state(
    value: Mapping[str, object] | None, *, legacy_locked: bool | None = None
) -> dict:
    """合併舊專案/部分 snapshot 與目前預設，輸出純 dict canonical state。"""
    result = default_box_body_structure_state()
    if not isinstance(value, Mapping):
        if legacy_locked is not None:
            result["locked"] = bool(legacy_locked)
        return result

    result["active_type"] = _structure_type(value.get("active_type")).value
    if "locked" in value:
        result["locked"] = bool(value.get("locked"))
    elif legacy_locked is not None:
        result["locked"] = bool(legacy_locked)

    incoming_configs = value.get("configs")
    if isinstance(incoming_configs, Mapping):
        for type_id in BoxBodyStructureType:
            incoming = incoming_configs.get(type_id.value)
            if isinstance(incoming, Mapping):
                result["configs"][type_id.value].update(deepcopy(dict(incoming)))
    return result


def set_active_structure(state: Mapping[str, object] | None, type_id) -> dict:
    """只切換 active configuration，不清除任何其他型態歷史值。"""
    result = normalize_box_body_structure_state(state)
    result["active_type"] = _structure_type(type_id).value
    return result


def activate_structure_with_defaults(
    state: Mapping[str, object] | None, type_id, total_w: float
) -> dict:
    """切換結構並把「第一次使用」的 W 分配預設寫進 canonical state。

    Resolver 仍負責驗證幾何；此函式只在目標型態從未有任何保存尺寸時，
    將畫面上原本只是暫算的預設值正式 materialize，確保 UI、3D、Save/Reload
    看到同一份狀態。既有使用者歷史值一律不覆蓋。
    """
    result = set_active_structure(state, type_id)
    kind = _structure_type(type_id)
    total = float(total_w)
    cfg = result["configs"][kind.value]

    if kind is BoxBodyStructureType.TWO_PIECE_W_SPLIT:
        if cfg.get("left_w") is None and cfg.get("right_w") is None:
            if total < 100.0:
                raise ValueError("W 二分需要左右兩側都至少 50 mm")
            cfg["left_w"] = total / 2.0
            cfg["right_w"] = total / 2.0
            cfg["driver"] = "default"
    elif kind is BoxBodyStructureType.THREE_PIECE_W_SPLIT:
        keys = ("left_w", "middle_w", "right_w")
        if all(cfg.get(key) is None for key in keys):
            if total < 150.0:
                raise ValueError("W 三分需要左右各至少 50 mm，中央至少 50 mm")
            cfg["left_w"] = 50.0
            cfg["middle_w"] = total - 100.0
            cfg["right_w"] = 50.0
            cfg["driver"] = "default"
    return result


def set_structure_locked(state: Mapping[str, object] | None, locked: bool) -> dict:
    result = normalize_box_body_structure_state(state)
    result["locked"] = bool(locked)
    return result


def update_structure_config(
    state: Mapping[str, object] | None,
    type_id,
    values: Mapping[str, object],
) -> dict:
    """更新單一型態設定；其他型態設定保持不動。"""
    result = normalize_box_body_structure_state(state)
    key = _structure_type(type_id).value
    result["configs"][key].update(deepcopy(dict(values or {})))
    return result


def _manual_integer(value, *, field: str) -> float:
    number = float(value)
    if not number.is_integer():
        raise ValueError(f"{field} 人工輸入只接受整數")
    return number


def resolve_two_piece_widths(state: Mapping[str, object] | None, total_w: float) -> tuple[float, float]:
    """解析 W 二分包外寬；保存值若與總 W 矛盾則 fail closed。"""
    total = float(total_w)
    if total < 100.0:
        raise ValueError("W 二分需要左右兩側都至少 50 mm")
    normalized = normalize_box_body_structure_state(state)
    cfg = normalized["configs"][BoxBodyStructureType.TWO_PIECE_W_SPLIT.value]
    left = cfg.get("left_w")
    right = cfg.get("right_w")
    if left is None and right is None:
        return total / 2.0, total / 2.0
    if left is None:
        right = float(right)
        left = total - right
    elif right is None:
        left = float(left)
        right = total - left
    else:
        left = float(left)
        right = float(right)
        if abs((left + right) - total) > 1e-9:
            raise ValueError("W 二分保存尺寸總和與箱身 W 不一致，拒絕產生幾何")
    if left < 50.0 or right < 50.0:
        raise ValueError("W 二分左右包外寬都不得小於 50 mm")
    return left, right


def set_two_piece_width(
    state: Mapping[str, object] | None,
    total_w: float,
    side: str,
    value,
    *,
    manual: bool = True,
) -> dict:
    """以任一側為驅動端更新 W 二分，另一側立即補足。"""
    side = str(side).lower()
    if side not in {"left", "right"}:
        raise ValueError("W 二分只能修改 left 或 right")
    number = _manual_integer(value, field="W 分配") if manual else float(value)
    total = float(total_w)
    other = total - number
    if number < 50.0 or other < 50.0:
        raise ValueError("W 二分左右包外寬都不得小於 50 mm")
    result = normalize_box_body_structure_state(state)
    cfg = result["configs"][BoxBodyStructureType.TWO_PIECE_W_SPLIT.value]
    if side == "left":
        cfg.update({"left_w": number, "right_w": other, "driver": "left"})
    else:
        cfg.update({"left_w": other, "right_w": number, "driver": "right"})
    return result


def reconcile_box_body_structure_for_total_w_change(
    state: Mapping[str, object] | None, total_w: float
) -> dict:
    """Reconcile saved W-split allocations at a normal total-W commit seam.

    The geometry resolver remains fail-closed for contradictory saved state.
    This helper is only for a legitimate operator edit of the enclosure W: it
    preserves the last explicit driver for each W-split mode and derives the
    complementary dimensions against the new total W.
    """
    result = normalize_box_body_structure_state(state)
    total = float(total_w)

    two_key = BoxBodyStructureType.TWO_PIECE_W_SPLIT.value
    two = result["configs"][two_key]
    if two.get("left_w") is not None or two.get("right_w") is not None:
        driver = str(two.get("driver") or "left")
        if driver == "right" and two.get("right_w") is not None:
            result = set_two_piece_width(result, total, "right", two["right_w"], manual=False)
        else:
            value = two.get("left_w")
            if value is None:
                value = total - float(two["right_w"])
            result = set_two_piece_width(result, total, "left", value, manual=False)

    three_key = BoxBodyStructureType.THREE_PIECE_W_SPLIT.value
    three = result["configs"][three_key]
    if any(three.get(key) is not None for key in ("left_w", "middle_w", "right_w")):
        driver = str(three.get("driver") or "side")
        if driver == "middle" and three.get("middle_w") is not None:
            result = set_three_piece_width(result, total, "middle", three["middle_w"], manual=False)
        else:
            side = three.get("left_w") if three.get("left_w") is not None else three.get("right_w")
            if side is None:
                side = (total - float(three["middle_w"])) / 2.0
            result = set_three_piece_width(result, total, "left", side, manual=False)

    return result


def set_join_seam_bend(state: Mapping[str, object] | None, type_id, value) -> dict:
    """更新 W 分件共用接合折邊；>=50 僅是 warning，不阻擋。"""
    bend = float(value)
    if bend < 12.0:
        raise ValueError("中央接合折邊不得小於 12 mm")
    key = _structure_type(type_id)
    if key not in {BoxBodyStructureType.TWO_PIECE_W_SPLIT, BoxBodyStructureType.THREE_PIECE_W_SPLIT}:
        raise ValueError("此結構型態沒有 W 分件接合折邊")
    return update_structure_config(state, key, {"seam_bend": bend})


def resolve_three_piece_widths(state: Mapping[str, object] | None, total_w: float) -> tuple[float, float, float]:
    """解析 W 三分；左右連動，中間吸收剩餘，未設定時預設 50/(W-100)/50。"""
    total = float(total_w)
    normalized = normalize_box_body_structure_state(state)
    cfg = normalized["configs"][BoxBodyStructureType.THREE_PIECE_W_SPLIT.value]
    left = cfg.get("left_w")
    middle = cfg.get("middle_w")
    right = cfg.get("right_w")
    if left is None and middle is None and right is None:
        left = right = 50.0
        middle = total - 100.0
    elif left is not None and middle is not None and right is not None:
        left = float(left)
        middle = float(middle)
        right = float(right)
        if abs(left - right) > 1e-9:
            raise ValueError("W 三分保存尺寸左右不一致，拒絕產生幾何")
        if abs((left + middle + right) - total) > 1e-9:
            raise ValueError("W 三分保存尺寸總和與箱身 W 不一致，拒絕產生幾何")
    else:
        driver = str(cfg.get("driver") or "side")
        if driver == "middle" and middle is not None:
            middle = float(middle)
            left = right = (total - middle) / 2.0
        else:
            side = left if left is not None else right
            if side is None:
                side = (total - float(middle)) / 2.0
            left = right = float(side)
            middle = total - 2.0 * float(side)
    if float(left) <= 0 or float(right) <= 0 or float(middle) <= 0:
        raise ValueError("W 三分三個包外尺寸都必須大於 0")
    return float(left), float(middle), float(right)


def set_three_piece_width(
    state: Mapping[str, object] | None,
    total_w: float,
    field: str,
    value,
    *,
    manual: bool = True,
) -> dict:
    field = str(field).lower()
    if field not in {"left", "middle", "right"}:
        raise ValueError("W 三分只能修改 left / middle / right")
    number = _manual_integer(value, field="W 分配") if manual else float(value)
    total = float(total_w)
    if field == "middle":
        middle = number
        left = right = (total - middle) / 2.0
        driver = "middle"
    else:
        left = right = number
        middle = total - 2.0 * number
        driver = "side"
    if left <= 0 or middle <= 0 or right <= 0:
        raise ValueError("W 三分三個包外尺寸都必須大於 0")
    result = normalize_box_body_structure_state(state)
    cfg = result["configs"][BoxBodyStructureType.THREE_PIECE_W_SPLIT.value]
    cfg.update({"left_w": left, "middle_w": middle, "right_w": right, "driver": driver})
    return result


def set_side_back_geometry(
    state: Mapping[str, object] | None,
    *,
    side_rear_bend=None,
    back_width_comp_t=None,
) -> dict:
    """更新側背分離專屬參數。"""
    values = {}
    if side_rear_bend is not None:
        bend = float(side_rear_bend)
        if bend <= 0:
            raise ValueError("側板後折必須大於 0")
        values["side_rear_bend"] = bend
    if back_width_comp_t is not None:
        comp = float(back_width_comp_t)
        if comp < 0:
            raise ValueError("後面板寬補償不可小於 0T")
        values["back_width_comp_t"] = comp
    return update_structure_config(state, BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT, values)
