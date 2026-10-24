# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Phase6 箱身多結構型態的單一狀態模型。"""
from __future__ import annotations

from copy import deepcopy
import math
from enum import Enum
from typing import Mapping


class BoxBodyStructureType(str, Enum):
    """箱身正式結構型態。"""

    INTEGRAL = "integral"
    TWO_PIECE_W_SPLIT = "two_piece_w_split"
    THREE_PIECE_W_SPLIT = "three_piece_w_split"
    THREE_PIECE_SIDE_BACK_SPLIT = "three_piece_side_back_split"


class BackPanelMode(str, Enum):
    """Receiving side/back-split rear-panel manufacturing mode."""

    FULL = "FULL"
    HALF = "HALF"
    BACK_OPENING = "BACK_OPENING"


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
                # Physical-piece Fold editors persist here. The aggregate
                # box_body Fold Chain remains the source for shared D/FW/W
                # dimensions; piece profiles own piece-local topology/angles.
                "piece_profiles": {},
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


def _structure_locked_bool(value):
    """Decode serialized operator booleans without bool("false") == True."""
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"false", "0", "off", "no", ""}:
            return False
        if text in {"true", "1", "on", "yes"}:
            return True
    return bool(value)


def normalize_box_body_structure_state(
    value: Mapping[str, object] | None, *, legacy_locked: bool | None = None
) -> dict:
    """合併舊專案/部分 snapshot 與目前預設，輸出純 dict canonical state。"""
    result = default_box_body_structure_state()
    if not isinstance(value, Mapping):
        if legacy_locked is not None:
            result["locked"] = _structure_locked_bool(legacy_locked)
        return result

    result["active_type"] = _structure_type(value.get("active_type")).value
    if "locked" in value:
        result["locked"] = _structure_locked_bool(value.get("locked"))
    elif legacy_locked is not None:
        result["locked"] = bool(legacy_locked)

    incoming_configs = value.get("configs")
    if isinstance(incoming_configs, Mapping):
        for type_id in BoxBodyStructureType:
            incoming = incoming_configs.get(type_id.value)
            if isinstance(incoming, Mapping):
                copied = deepcopy(dict(incoming))
                if type_id is BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT:
                    # A malformed saved Fold dictionary is not a valid
                    # manufacturing source for any side/back physical piece.
                    if not isinstance(copied.get("piece_profiles", {}), Mapping):
                        copied["piece_profiles"] = {}
                result["configs"][type_id.value].update(copied)
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
    result["locked"] = _structure_locked_bool(locked)
    return result


def _back_panel_mode(value) -> BackPanelMode:
    if isinstance(value, BackPanelMode):
        return value
    text = str(value or "").strip().upper()
    try:
        return BackPanelMode(text)
    except ValueError:
        return BackPanelMode.FULL


def back_panel_mode(state: Mapping[str, object] | None) -> BackPanelMode:
    """Return the canonical Receiving rear-panel mode; legacy projects are FULL."""
    normalized = normalize_box_body_structure_state(state)
    cfg = normalized["configs"][BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]
    return _back_panel_mode(cfg.get("back_panel_mode"))


def set_side_back_back_panel_mode(
    state: Mapping[str, object] | None,
    mode,
) -> dict:
    """Persist one of the three mutually-exclusive rear-panel modes."""
    resolved = _back_panel_mode(mode)
    return update_structure_config(
        state,
        BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT,
        {"back_panel_mode": resolved.value},
    )


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


def _finite_dimension(value, *, field: str) -> float:
    """Preserve supplied physical dimensions; never silently store bool/NaN/Inf."""
    if isinstance(value, bool):
        raise ValueError(f"{field} 必須是有限數值")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} 必須是有限數值") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field} 必須是有限數值")
    return number


def _manual_integer(value, *, field: str) -> float:
    number = _finite_dimension(value, field=field)
    if not number.is_integer():
        raise ValueError(f"{field} 人工輸入只接受整數")
    return number


def resolve_two_piece_widths(state: Mapping[str, object] | None, total_w: float) -> tuple[float, float]:
    """解析 W 二分包外寬；保存值若與總 W 矛盾則 fail closed。"""
    total = _finite_dimension(total_w, field="W 二分箱身總寬")
    if total < 100.0:
        raise ValueError("W 二分需要左右兩側都至少 50 mm")
    normalized = normalize_box_body_structure_state(state)
    cfg = normalized["configs"][BoxBodyStructureType.TWO_PIECE_W_SPLIT.value]
    left = cfg.get("left_w")
    right = cfg.get("right_w")
    if left is None and right is None:
        return total / 2.0, total / 2.0
    if left is None:
        right = _finite_dimension(right, field="W 二分右側")
        left = total - right
    elif right is None:
        left = _finite_dimension(left, field="W 二分左側")
        right = total - left
    else:
        left = _finite_dimension(left, field="W 二分左側")
        right = _finite_dimension(right, field="W 二分右側")
        if abs((left + right) - total) > 1e-9:
            raise ValueError("W 二分保存尺寸總和與箱身 W 不一致，拒絕產生幾何")
    if not (math.isfinite(left) and math.isfinite(right)):
        raise ValueError("W 二分包外尺寸必須是有限值")
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
    number = (_manual_integer(value, field="W 分配") if manual
              else _finite_dimension(value, field="W 分配"))
    total = _finite_dimension(total_w, field="W 二分箱身總寬")
    other = total - number
    if not math.isfinite(other) or number < 50.0 or other < 50.0:
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
    total = _finite_dimension(total_w, field="箱身總寬")

    two_key = BoxBodyStructureType.TWO_PIECE_W_SPLIT.value
    two = result["configs"][two_key]
    if two.get("left_w") is not None or two.get("right_w") is not None:
        driver = str(two.get("driver") or "left")
        try:
            if driver == "default":
                result = set_two_piece_width(result, total, "left", total / 2.0, manual=False)
                result["configs"][two_key]["driver"] = "default"
            elif driver == "right" and two.get("right_w") is not None:
                result = set_two_piece_width(result, total, "right", two["right_w"], manual=False)
            else:
                value = two.get("left_w")
                if value is None:
                    value = total - float(two["right_w"])
                result = set_two_piece_width(result, total, "left", value, manual=False)
        except ValueError:
            if result.get("active_type") == two_key:
                raise
            result["configs"][two_key].update(
                left_w=None, right_w=None, driver="default"
            )

    three_key = BoxBodyStructureType.THREE_PIECE_W_SPLIT.value
    three = result["configs"][three_key]
    if any(three.get(key) is not None for key in ("left_w", "middle_w", "right_w")):
        driver = str(three.get("driver") or "side")
        try:
            if driver == "default":
                result = set_three_piece_width(result, total, "left", 50.0, manual=False)
                result["configs"][three_key]["driver"] = "default"
            elif driver == "middle" and three.get("middle_w") is not None:
                result = set_three_piece_width(result, total, "middle", three["middle_w"], manual=False)
            else:
                side = three.get("left_w") if three.get("left_w") is not None else three.get("right_w")
                if side is None:
                    side = (total - float(three["middle_w"])) / 2.0
                result = set_three_piece_width(result, total, "left", side, manual=False)
        except ValueError:
            if result.get("active_type") == three_key:
                raise
            result["configs"][three_key].update(
                left_w=None, middle_w=None, right_w=None, driver="default"
            )

    return result


def set_join_seam_bend(state: Mapping[str, object] | None, type_id, value) -> dict:
    """更新 W 分件共用接合折邊；>=50 僅是 warning，不阻擋。"""
    bend = _finite_dimension(value, field="中央接合折邊")
    if bend < 12.0:
        raise ValueError("中央接合折邊不得小於 12 mm")
    key = _structure_type(type_id)
    if key not in {BoxBodyStructureType.TWO_PIECE_W_SPLIT, BoxBodyStructureType.THREE_PIECE_W_SPLIT}:
        raise ValueError("此結構型態沒有 W 分件接合折邊")
    return update_structure_config(state, key, {"seam_bend": bend})


def resolve_three_piece_widths(state: Mapping[str, object] | None, total_w: float) -> tuple[float, float, float]:
    """Resolve explicit side/center constraints without discarding conflicts.

    Left/right are the same physical outside width. The center is the
    complementary residual only when no explicit center was persisted.
    """
    def positive_finite(value, label):
        if isinstance(value, bool):
            raise ValueError(f"W 三分{label}必須是有限正數")
        try:
            result = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"W 三分{label}必須是有限正數") from exc
        if not math.isfinite(result) or result <= 0:
            raise ValueError(f"W 三分{label}必須是有限正數")
        return result

    total = positive_finite(total_w, "箱身總寬")
    normalized = normalize_box_body_structure_state(state)
    cfg = normalized["configs"][BoxBodyStructureType.THREE_PIECE_W_SPLIT.value]
    left, middle, right = (cfg.get(key) for key in ("left_w", "middle_w", "right_w"))
    if left is None and middle is None and right is None:
        side = 50.0
        middle = total - 2.0 * side
    else:
        left = None if left is None else positive_finite(left, "左側寬")
        right = None if right is None else positive_finite(right, "右側寬")
        middle = None if middle is None else positive_finite(middle, "中央寬")
        if left is not None and right is not None and abs(left - right) > 1e-9:
            raise ValueError("W 三分保存尺寸左右不一致，拒絕產生幾何")
        side = left if left is not None else right
        if side is None:
            side = (total - middle) / 2.0
        elif middle is None:
            middle = total - 2.0 * side
        elif abs(2.0 * side + middle - total) > 1e-9:
            raise ValueError("W 三分保存尺寸與箱身總寬不一致，拒絕產生幾何")
    if side <= 0 or middle <= 0 or not math.isfinite(side) or not math.isfinite(middle):
        raise ValueError("W 三分三個包外尺寸都必須大於 0")
    return float(side), float(middle), float(side)

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
    number = (_manual_integer(value, field="W 分配") if manual
              else _finite_dimension(value, field="W 分配"))
    total = _finite_dimension(total_w, field="W 三分箱身總寬")
    if field == "middle":
        middle = number
        left = right = (total - middle) / 2.0
        driver = "middle"
    else:
        left = right = number
        middle = total - 2.0 * number
        driver = "side"
    if not all(math.isfinite(v) and v > 0.0 for v in (left, middle, right)):
        raise ValueError("W 三分三個包外尺寸都必須是有限正數")
    result = normalize_box_body_structure_state(state)
    cfg = result["configs"][BoxBodyStructureType.THREE_PIECE_W_SPLIT.value]
    cfg.update({"left_w": left, "middle_w": middle, "right_w": right, "driver": driver})
    return result



def set_side_back_piece_profile(
    state: Mapping[str, object] | None,
    role: str,
    profile,
) -> dict:
    """Persist one side/back physical piece Fold profile in canonical structure state."""
    role = str(role or "").strip()
    if role not in {"left_side", "back", "right_side"}:
        raise ValueError(f"unsupported side/back physical role: {role}")
    rows = []
    for raw in tuple(profile or ()):
        row = deepcopy(dict(raw))
        length = _finite_dimension(row.get("len", 0.0), field=f"{role} Fold segment length")
        if length <= 0:
            raise ValueError(f"{role} Fold segment length must be > 0")
        row["len"] = length
        rows.append(row)
    if not rows:
        raise ValueError(f"{role} Fold profile must not be empty")

    result = normalize_box_body_structure_state(state)
    cfg = result["configs"][BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]
    profiles = deepcopy(dict(cfg.get("piece_profiles") or {}))
    profiles[role] = rows
    cfg["piece_profiles"] = profiles
    return result

def side_rear_bend_dimension_space(state: Mapping[str, object] | None) -> str:
    """Return the stored side-rear-bend dimension space.

    Legacy projects predate the marker and stored the material flange directly.
    New family policies may explicitly own an operator OUTSIDE value.
    """
    normalized = normalize_box_body_structure_state(state)
    cfg = normalized["configs"][BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]
    space = str(cfg.get("side_rear_bend_dimension_space") or "MATERIAL").strip().upper()
    if space not in {"MATERIAL", "OUTSIDE"}:
        raise ValueError(f"unsupported side rear bend dimension space: {space}")
    return space


def side_rear_bend_material_length(
    state: Mapping[str, object] | None, thickness: float
) -> float:
    """Resolve the physical/material rear flange exactly once."""
    normalized = normalize_box_body_structure_state(state)
    cfg = normalized["configs"][BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]
    value = float(cfg.get("side_rear_bend", 15.0))
    if side_rear_bend_dimension_space(normalized) == "OUTSIDE":
        value -= float(thickness)
    if value <= 0:
        raise ValueError("側板後折換算後料尺寸必須大於 0")
    return value


def side_rear_bend_outside_length(
    state: Mapping[str, object] | None, thickness: float
) -> float:
    """Resolve the operator-facing outside rear flange without changing geometry."""
    normalized = normalize_box_body_structure_state(state)
    cfg = normalized["configs"][BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]
    value = float(cfg.get("side_rear_bend", 15.0))
    if side_rear_bend_dimension_space(normalized) == "MATERIAL":
        value += float(thickness)
    if value <= 0:
        raise ValueError("側板後折包外尺寸必須大於 0")
    return value


def set_side_back_geometry(
    state: Mapping[str, object] | None,
    *,
    side_rear_bend=None,
    side_rear_bend_dimension_space=None,
    back_width_comp_t=None,
) -> dict:
    """更新側背分離專屬參數；dimension space 必須顯式保存。"""
    values = {}
    if side_rear_bend is not None:
        bend = float(side_rear_bend)
        if bend <= 0:
            raise ValueError("側板後折必須大於 0")
        values["side_rear_bend"] = bend
    if side_rear_bend_dimension_space is not None:
        space = str(side_rear_bend_dimension_space).strip().upper()
        if space not in {"MATERIAL", "OUTSIDE"}:
            raise ValueError("側板後折 dimension space 只接受 MATERIAL / OUTSIDE")
        values["side_rear_bend_dimension_space"] = space
    if back_width_comp_t is not None:
        comp = float(back_width_comp_t)
        if comp < 0:
            raise ValueError("後面板寬補償不可小於 0T")
        values["back_width_comp_t"] = comp
    return update_structure_config(state, BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT, values)
