# -*- coding: utf-8 -*-
"""Corner-type policy semantics and assembly-height projections."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .sheetmetal_geometry_core import (
    DEFAULT_TOLERANCE,
    GeometryError,
    CornerTypeResidual,
    CornerTypeId,
    CrossCornerMode,
    CornerDirection,
    EDITABLE_CORNER_TYPE_IDS,
    CornerTypeSelection,
    ResolvedCornerRelief,
)

def normalize_corner_selection(selection: CornerTypeSelection) -> CornerTypeSelection:
    """將舊 C01..C04 資料轉換成正式製造語意模型。"""
    if not isinstance(selection, CornerTypeSelection):
        selection = CornerTypeSelection(selection)
    type_id = selection.type_id
    if type_id in EDITABLE_CORNER_TYPE_IDS:
        return selection
    if type_id is CornerTypeId.C01:
        return CornerTypeSelection(CornerTypeId.CROSS, cross_mode=CrossCornerMode.STANDARD)
    if type_id is CornerTypeId.C02:
        direction = CornerDirection.HEIGHT if selection.rotation_quadrants % 2 else CornerDirection.WIDTH
        return CornerTypeSelection(
            CornerTypeId.CROSS,
            cross_mode=CrossCornerMode.RETAIN,
            direction=direction,
            amount_t=1.0,
        )
    if type_id is CornerTypeId.C03:
        return CornerTypeSelection(
            CornerTypeId.CROSS,
            cross_mode=CrossCornerMode.EXTRA_CUT,
            direction=CornerDirection.BOTH,
            amount_t=0.5,
        )
    if type_id is CornerTypeId.C04:
        return CornerTypeSelection(
            CornerTypeId.INSERT_OVERLAY,
            amount_t=1.0,
            secondary_retain_t=0.5,
            secondary_depth_t=2.0,
        )
    raise GeometryError(f"不支援的截角類型：{type_id}")


def _directional_delta(direction: CornerDirection, amount: float) -> tuple[float, float]:
    if direction is CornerDirection.WIDTH:
        return amount, 0.0
    if direction is CornerDirection.HEIGHT:
        return 0.0, amount
    if direction is CornerDirection.BOTH:
        return amount, amount
    raise GeometryError(f"不支援的截角方向：{direction}")


def corner_selection_residual(
    selection: CornerTypeSelection,
    *,
    thickness: float,
    fw: float,
) -> CornerTypeResidual:
    """把單一截角製造語意解析成不含折邊基底的截角尺寸。"""
    selection = normalize_corner_selection(selection)
    t = float(thickness)
    frame_width = float(fw)
    if t <= 0:
        raise GeometryError("板厚必須大於 0")
    if frame_width < 0:
        raise GeometryError("FW 不可小於 0")

    if selection.type_id is CornerTypeId.CROSS:
        if selection.cross_mode is CrossCornerMode.STANDARD:
            return CornerTypeResidual(
                (0.0, 0.0),
                slot_width=selection.slot_width,
                slot_straight_depth=selection.slot_straight_depth,
                slot_radius=selection.slot_radius,
            )
        amount = float(selection.amount_t) * t
        du, dv = _directional_delta(selection.direction, amount)
        if selection.cross_mode is CrossCornerMode.RETAIN:
            du, dv = -du, -dv
        return CornerTypeResidual(
            (du, dv),
            slot_width=selection.slot_width,
            slot_straight_depth=selection.slot_straight_depth,
            slot_radius=selection.slot_radius,
        )

    if selection.type_id is CornerTypeId.OVERLAY:
        # 貼外：一級截角；高方向固定留肉 xT。
        retain = float(selection.amount_t) * t
        return CornerTypeResidual((frame_width, frame_width - retain))

    if selection.type_id is CornerTypeId.INSERT:
        # 純嵌入：一級截角；不能留肉，固定在高方向多切 xT。
        extra = float(selection.amount_t) * t
        return CornerTypeResidual((frame_width, frame_width + extra))

    if selection.type_id is CornerTypeId.INSERT_OVERLAY:
        # 一級做貼外留肉。UI 的「嵌入留肉 xT」是操作語意；
        # 實際 C04 二級切線維持既有製造幾何：側折 + xT。
        # 也就是兩級之間真正剩下的材料寬度由程式自行推導為 FW - xT。
        primary_retain = float(selection.amount_t) * t
        secondary_offset = float(selection.secondary_retain_t) * t
        return CornerTypeResidual(
            (frame_width, frame_width - primary_retain),
            secondary_u=secondary_offset,
            secondary_depth=float(selection.secondary_depth_t) * t,
        )

    raise GeometryError(f"不支援的截角製造語意：{selection.type_id}")


def corner_type_residual(
    type_id: CornerTypeId,
    *,
    thickness: float,
    fw: float,
) -> CornerTypeResidual:
    """舊呼叫端只有 type ID 時使用的相容入口。"""
    return corner_selection_residual(
        CornerTypeSelection(type_id), thickness=thickness, fw=fw,
    )


def compose_corner_residual(
    residual: CornerTypeResidual,
    *,
    fold_u: float,
    fold_v: float,
    rotation_quadrants: int = 0,
    allow_axis_swap: bool = False,
) -> ResolvedCornerRelief:
    """Compose an already-defined intrinsic corner rule with fold geometry."""
    fu = abs(float(fold_u))
    fv = abs(float(fold_v))
    du, dv = residual.primary
    if allow_axis_swap and int(rotation_quadrants) % 2:
        du, dv = dv, du
    primary_u = fu + du
    primary_v = fv + dv
    actual_secondary_u = None if residual.secondary_u is None else fu + residual.secondary_u
    if primary_u < 0 or primary_v < 0:
        raise GeometryError("折邊與截角類型組合後，第一級截角尺寸不可為負值")
    if actual_secondary_u is not None and actual_secondary_u < 0:
        raise GeometryError("第二級截角尺寸不可為負值")
    if residual.secondary_depth is not None and residual.secondary_depth < 0:
        raise GeometryError("第二級截角深度不可為負值")
    if residual.slot_width is not None:
        if residual.slot_width > primary_u + DEFAULT_TOLERANCE:
            raise GeometryError("十字截角槽寬不可超過主截角寬")
        if residual.slot_straight_depth is None or residual.slot_radius is None:
            raise GeometryError("十字截角槽參數不完整")
    return ResolvedCornerRelief(
        primary_u=primary_u,
        primary_v=primary_v,
        secondary_u=actual_secondary_u,
        secondary_depth=residual.secondary_depth,
        slot_width=residual.slot_width,
        slot_straight_depth=residual.slot_straight_depth,
        slot_radius=residual.slot_radius,
    )


def resolve_corner_relief(
    selection: CornerTypeSelection,
    *,
    fold_u: float,
    fold_v: float,
    thickness: float,
    fw: float,
) -> ResolvedCornerRelief:
    """將折邊幾何與單一截角製造語意組合成實際截角。"""
    normalized = normalize_corner_selection(selection)
    residual = corner_selection_residual(normalized, thickness=thickness, fw=fw)
    return compose_corner_residual(residual, fold_u=fold_u, fold_v=fold_v)


@dataclass(frozen=True)
class FourCornerTypePolicy:
    bottom_left: CornerTypeSelection
    bottom_right: CornerTypeSelection
    top_left: CornerTypeSelection
    top_right: CornerTypeSelection
    fw: float
    bottom_fw: float | None = None
    top_fw: float | None = None

    def fw_for(self, corner_name: str) -> float:
        name = str(corner_name or "")
        if name.startswith("bottom") and self.bottom_fw is not None:
            return float(self.bottom_fw)
        if name.startswith("top") and self.top_fw is not None:
            return float(self.top_fw)
        return float(self.fw)


@dataclass(frozen=True)
class EndCapAssemblySemantics:
    """由封頭／封尾上方 CornerType 衍生的唯讀裝配機械語意。"""

    type_id: CornerTypeId
    outer_thickness_factor: float
    x_topology: Literal["folded", "flat"]
    has_box_side_outer_fold: bool
    has_outer_contact: bool = False
    has_inner_insertion: bool = False
    outer_contact_target: str | None = None
    inner_insertion_target: str | None = None
    mating_relation: str = ""


def resolve_endcap_assembly_semantics(
    selection: CornerTypeSelection,
) -> EndCapAssemblySemantics:
    """把單一上方 CornerType 解析成 EndCap 裝配語意，不建立第二份狀態。"""
    normalized = normalize_corner_selection(selection)
    factor = corner_outer_thickness_factor(normalized)
    if factor is None:
        raise GeometryError("封頭尾上方截角必須使用箱體裝配 CornerType")
    if normalized.type_id is CornerTypeId.OVERLAY:
        return EndCapAssemblySemantics(
            normalized.type_id, factor, "flat", False,
            has_outer_contact=True,
            has_inner_insertion=False,
            outer_contact_target="BOX_OUTER_SURFACE",
            mating_relation="OUTER_OVERLAY",
        )
    if normalized.type_id is CornerTypeId.INSERT:
        return EndCapAssemblySemantics(
            normalized.type_id, factor, "folded", True,
            has_outer_contact=False,
            has_inner_insertion=True,
            inner_insertion_target="BOX_INNER_MATING_ZONE",
            mating_relation="INNER_INSERT",
        )
    return EndCapAssemblySemantics(
        normalized.type_id, factor, "folded", True,
        has_outer_contact=True,
        has_inner_insertion=True,
        outer_contact_target="BOX_OUTER_SURFACE",
        inner_insertion_target="BOX_INNER_MATING_ZONE",
        mating_relation="OUTER_OVERLAY_AND_INNER_INSERT",
    )


def resolve_endcap_policy_assembly_semantics(
    policy: FourCornerTypePolicy,
) -> EndCapAssemblySemantics:
    """由四角 policy 取得唯一 EndCap 裝配語意；左右上方類型不得互相矛盾。"""
    left = resolve_endcap_assembly_semantics(policy.top_left)
    right = resolve_endcap_assembly_semantics(policy.top_right)
    if left.type_id is not right.type_id:
        raise GeometryError("封頭尾上方左右 CornerType 的裝配類型必須一致")
    return left


# 舊常數仍保留，供既有保存資料與固定箱型映射使用。
VAULT_C01 = CornerTypeSelection(CornerTypeId.C01)
VAULT_C02 = CornerTypeSelection(CornerTypeId.C02)
VAULT_C03 = CornerTypeSelection(CornerTypeId.C03)
VAULT_C04 = CornerTypeSelection(CornerTypeId.C04)

VAULT_ENDCAP_CORNER_POLICY = FourCornerTypePolicy(
    bottom_left=VAULT_C03,
    bottom_right=VAULT_C03,
    top_left=VAULT_C04,
    top_right=VAULT_C04,
    fw=25.0,
)


def corner_outer_thickness_factor(selection: CornerTypeSelection) -> float | None:
    """回傳單一截角語意所代表的外部高度占用倍率。

    ``None`` 表示十字截角本身不定義封頭尾的裝配占用。
    """
    selection = normalize_corner_selection(selection)
    if selection.type_id is CornerTypeId.INSERT:
        return 0.0
    if selection.type_id in (CornerTypeId.OVERLAY, CornerTypeId.INSERT_OVERLAY):
        return 1.0
    return None


def endcap_outer_thickness_factor(policy: FourCornerTypePolicy) -> float:
    """由唯一 EndCap 裝配語意推導該板件占用的外部高度。"""
    return resolve_endcap_policy_assembly_semantics(policy).outer_thickness_factor


def box_body_vertical_offsets(
    thickness: float,
    *,
    head_corner_policy: FourCornerTypePolicy | None = None,
    tail_corner_policy: FourCornerTypePolicy | None = None,
) -> tuple[float, float]:
    """只由截角類型推導並回傳 ``(下方, 上方)`` 外高偏移。"""
    t = float(thickness)
    if t <= 0:
        raise GeometryError("板厚必須大於 0")
    head = head_corner_policy or VAULT_ENDCAP_CORNER_POLICY
    tail = tail_corner_policy or VAULT_ENDCAP_CORNER_POLICY
    return (
        endcap_outer_thickness_factor(tail) * t,
        endcap_outer_thickness_factor(head) * t,
    )


def box_body_height_from_corner_policies(
    height: float,
    thickness: float,
    *,
    head_corner_policy: FourCornerTypePolicy | None = None,
    tail_corner_policy: FourCornerTypePolicy | None = None,
) -> float:
    """由封頭／封尾截角裝配語意推導箱身實際高度。"""
    h = float(height)
    bottom, top = box_body_vertical_offsets(
        thickness,
        head_corner_policy=head_corner_policy,
        tail_corner_policy=tail_corner_policy,
    )
    result = h - bottom - top
    if result <= 0:
        raise GeometryError("箱身高度計算後必須大於 0")
    return result
