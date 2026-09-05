# -*- coding: utf-8 -*-
"""Pure 2D sheet-metal geometry primitives and relief generation.

This module deliberately has no ezdxf dependency.  DXF exporters consume the
closed exterior point list produced here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Iterable, Literal

try:
    from shapely.geometry import Polygon, box, LineString
    from shapely.geometry.polygon import orient
    from shapely.ops import unary_union
except Exception:  # pragma: no cover - exercised only on minimal deployments
    Polygon = None
    box = None
    LineString = None
    orient = None
    unary_union = None


DEFAULT_TOLERANCE = 1e-9


class GeometryError(ValueError):
    """Raised when a sheet-metal geometry definition is invalid."""


@dataclass(frozen=True)
class Vec2:
    x: float
    y: float

    def __add__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Vec2":
        return Vec2(self.x * scalar, self.y * scalar)

    __rmul__ = __mul__

    def length(self) -> float:
        return math.hypot(self.x, self.y)


@dataclass(frozen=True)
class BendLine:
    name: str
    p1: Vec2
    p2: Vec2


@dataclass
class Flange:
    name: str
    bend: BendLine
    length: float
    parent: "Flange | None" = None
    child_bends: list[BendLine] = field(default_factory=list)
    role: str | None = None


@dataclass(frozen=True)
class Corner:
    name: str
    point: Vec2
    u: Vec2
    v: Vec2
    bends: tuple[BendLine, BendLine]


@dataclass(frozen=True)
class ReliefPolygon:
    rule_name: str
    source_corner: str
    polygon: object
    metadata: dict[str, float]


@dataclass(frozen=True)
class ReliefConfig:
    top_secondary_x_factor: float = 0.5
    top_secondary_depth_factor: float = 2.0
    bottom_x_factor: float = 0.5
    bottom_y_factor: float = 0.5

    # Absolute millimetre overrides.  None -> use factor * T.
    top_secondary_x_left: float | None = None
    top_secondary_x_right: float | None = None
    top_secondary_depth_left: float | None = None
    top_secondary_depth_right: float | None = None
    bottom_x_left: float | None = None
    bottom_x_right: float | None = None
    bottom_y: float | None = None




@dataclass(frozen=True)
class CornerTypeResidual:
    """Intrinsic corner rule after fold dimensions are removed."""
    primary: tuple[float, float]
    secondary_u: float | None = None
    secondary_depth: float | None = None


class CornerTypeId(str, Enum):
    """正式製造／裝配截角語意，並保留舊 C01..C04 相容代碼。"""

    CROSS = "CROSS"
    OVERLAY = "OVERLAY"
    INSERT = "INSERT"
    INSERT_OVERLAY = "INSERT_OVERLAY"

    # 舊資料保存代碼只允許在引擎邊界轉換；新 GUI 必須顯示上方正式製造語意，
    # 不得再把這些代碼當成使用者操作名稱。
    C01 = "C01"
    C02 = "C02"
    C03 = "C03"
    C04 = "C04"


class CrossCornerMode(str, Enum):
    STANDARD = "standard"
    RETAIN = "retain"
    EXTRA_CUT = "extra_cut"


class CornerDirection(str, Enum):
    WIDTH = "width"
    HEIGHT = "height"
    BOTH = "both"


EDITABLE_CORNER_TYPE_IDS = (
    CornerTypeId.CROSS,
    CornerTypeId.OVERLAY,
    CornerTypeId.INSERT,
    CornerTypeId.INSERT_OVERLAY,
)


CORNER_TYPE_LABELS = {
    CornerTypeId.CROSS: "十字截角",
    CornerTypeId.OVERLAY: "貼外型",
    CornerTypeId.INSERT: "嵌入型",
    CornerTypeId.INSERT_OVERLAY: "嵌入貼外型",
    CornerTypeId.C01: "標準截角",
    CornerTypeId.C02: "單邊留肉 1T",
    CornerTypeId.C03: "雙向多切 0.5T",
    CornerTypeId.C04: "雙段截角",
}


@dataclass(frozen=True)
class CornerTypeSelection:
    """單一角落的製造語意。

    ``rotation_quadrants`` 只保留給舊 C02 資料相容；新的選擇直接保存
    ``direction``，使用者不需要再用 X/Y 或 0°/90° 推理截角方向。
    """

    type_id: CornerTypeId
    rotation_quadrants: int = 0
    cross_mode: CrossCornerMode | None = None
    direction: CornerDirection | None = None
    amount_t: float | None = None
    secondary_retain_t: float | None = None
    secondary_depth_t: float | None = None

    def __post_init__(self):
        type_id = CornerTypeId(self.type_id)
        object.__setattr__(self, "type_id", type_id)
        object.__setattr__(self, "rotation_quadrants", int(self.rotation_quadrants) % 4)

        mode = None if self.cross_mode is None else CrossCornerMode(self.cross_mode)
        direction = None if self.direction is None else CornerDirection(self.direction)
        amount = None if self.amount_t is None else float(self.amount_t)
        secondary_retain = None if self.secondary_retain_t is None else float(self.secondary_retain_t)
        secondary_depth = None if self.secondary_depth_t is None else float(self.secondary_depth_t)

        if type_id is CornerTypeId.CROSS:
            mode = mode or CrossCornerMode.STANDARD
            if mode is CrossCornerMode.STANDARD:
                direction = None
                amount = None
            elif mode is CrossCornerMode.RETAIN:
                direction = direction or CornerDirection.WIDTH
                if direction is CornerDirection.BOTH:
                    raise GeometryError("十字截角單邊留肉方向只能是寬或高")
                amount = 1.0 if amount is None else amount
                if amount <= 0:
                    raise GeometryError("十字截角留肉量必須大於 0")
            else:
                direction = direction or CornerDirection.BOTH
                amount = 0.5 if amount is None else amount
                if amount <= 0:
                    raise GeometryError("十字截角多切量必須大於 0")
        elif type_id is CornerTypeId.OVERLAY:
            if direction not in (None, CornerDirection.HEIGHT):
                raise GeometryError("貼外型留肉方向固定為高")
            direction = CornerDirection.HEIGHT
            amount = 1.0 if amount is None else amount
            if amount <= 0:
                raise GeometryError("貼外型留肉量必須大於 0")
        elif type_id is CornerTypeId.INSERT:
            if direction not in (None, CornerDirection.HEIGHT):
                raise GeometryError("嵌入型多切方向固定為高")
            direction = CornerDirection.HEIGHT
            amount = 1.0 if amount is None else amount
            if amount <= 0:
                raise GeometryError("嵌入型多切量必須大於 0")
        elif type_id is CornerTypeId.INSERT_OVERLAY:
            if direction not in (None, CornerDirection.HEIGHT):
                raise GeometryError("嵌入貼外型第一級貼外留肉方向固定為高")
            direction = CornerDirection.HEIGHT
            amount = 1.0 if amount is None else amount
            secondary_retain = 0.5 if secondary_retain is None else secondary_retain
            secondary_depth = 2.0 if secondary_depth is None else secondary_depth
            if amount <= 0:
                raise GeometryError("嵌入貼外型貼外留肉量必須大於 0")
            if secondary_retain < 0:
                raise GeometryError("嵌入貼外型嵌入留肉量不可小於 0")
            if secondary_depth <= 0:
                raise GeometryError("嵌入貼外型嵌入深度必須大於 0")

        # 二級參數只屬於 INSERT_OVERLAY。舊檔/切換狀態即使殘留
        # secondary_* 欄位，也不得讓 INSERT / OVERLAY / CROSS 成為非法
        # 的「單級語意 + 二級參數」混合狀態。
        if type_id is not CornerTypeId.INSERT_OVERLAY:
            secondary_retain = None
            secondary_depth = None

        object.__setattr__(self, "cross_mode", mode)
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "amount_t", amount)
        object.__setattr__(self, "secondary_retain_t", secondary_retain)
        object.__setattr__(self, "secondary_depth_t", secondary_depth)


@dataclass(frozen=True)
class ResolvedCornerRelief:
    """Actual cut extents after fold base + intrinsic CornerType are composed."""
    primary_u: float
    primary_v: float
    secondary_u: float | None = None
    secondary_depth: float | None = None


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
            return CornerTypeResidual((0.0, 0.0))
        amount = float(selection.amount_t) * t
        du, dv = _directional_delta(selection.direction, amount)
        if selection.cross_mode is CrossCornerMode.RETAIN:
            du, dv = -du, -dv
        return CornerTypeResidual((du, dv))

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
    return ResolvedCornerRelief(
        primary_u=primary_u,
        primary_v=primary_v,
        secondary_u=actual_secondary_u,
        secondary_depth=residual.secondary_depth,
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


@dataclass(frozen=True)
class FourSideFlangeGeometry:
    total_width: float
    total_height: float
    thickness: float
    left_fold: float
    right_fold: float
    top_fold: float
    bottom_fold: float


@dataclass(frozen=True)
class RectCornerReliefPolicy:
    bottom_left_x: float
    bottom_right_x: float
    top_left_x: float
    top_right_x: float
    bottom_y: float
    top_y: float

@dataclass(frozen=True)
class FourSideBendExtentPolicy:
    horizontal_to_blank_edges: bool = False


def _validate_four_side_geometry(g: FourSideFlangeGeometry) -> None:
    if g.total_width <= 0 or g.total_height <= 0:
        raise GeometryError("blank dimensions must be greater than zero")
    if g.thickness <= 0:
        raise GeometryError("板厚必須大於 0")
    if any(v < 0 for v in (g.left_fold, g.right_fold, g.top_fold, g.bottom_fold)):
        raise GeometryError("fold dimensions must not be negative")


def _validate_four_side(g: FourSideFlangeGeometry, policy: RectCornerReliefPolicy) -> None:
    _validate_four_side_geometry(g)
    values = (
        policy.bottom_left_x, policy.bottom_right_x,
        policy.top_left_x, policy.top_right_x,
        policy.bottom_y, policy.top_y,
    )
    if any(v < 0 for v in values):
        raise GeometryError("relief dimensions must not be negative")
    if policy.bottom_left_x + policy.bottom_right_x >= g.total_width:
        raise GeometryError("bottom corner reliefs consume blank width")
    if policy.top_left_x + policy.top_right_x >= g.total_width:
        raise GeometryError("top corner reliefs consume blank width")
    if policy.bottom_y + policy.top_y >= g.total_height:
        raise GeometryError("corner reliefs consume blank height")


def _placed_corner_cut_polygons(
    *,
    corner_name: str,
    relief: ResolvedCornerRelief,
    width: float,
    height: float,
):
    """Place a canonical inward +U/+V corner cut at one physical blank corner."""
    pu, pv = relief.primary_u, relief.primary_v
    if corner_name == "bottom_left":
        primary = box(0.0, 0.0, pu, pv)
        secondary = (
            None if relief.secondary_u is None or relief.secondary_depth is None
            else box(0.0, pv, relief.secondary_u, pv + relief.secondary_depth)
        )
    elif corner_name == "bottom_right":
        primary = box(width - pu, 0.0, width, pv)
        secondary = (
            None if relief.secondary_u is None or relief.secondary_depth is None
            else box(width - relief.secondary_u, pv, width, pv + relief.secondary_depth)
        )
    elif corner_name == "top_left":
        primary = box(0.0, height - pv, pu, height)
        secondary = (
            None if relief.secondary_u is None or relief.secondary_depth is None
            else box(0.0, height - pv - relief.secondary_depth, relief.secondary_u, height - pv)
        )
    elif corner_name == "top_right":
        primary = box(width - pu, height - pv, width, height)
        secondary = (
            None if relief.secondary_u is None or relief.secondary_depth is None
            else box(
                width - relief.secondary_u,
                height - pv - relief.secondary_depth,
                width,
                height - pv,
            )
        )
    else:
        raise GeometryError(f"unknown physical corner: {corner_name}")
    return [poly for poly in (primary, secondary) if poly is not None and not poly.is_empty]


def _four_side_type_cut_polygons(g: FourSideFlangeGeometry, policy: FourCornerTypePolicy):
    _validate_four_side_geometry(g)
    specs = {
        "bottom_left": (policy.bottom_left, g.left_fold, g.bottom_fold),
        "bottom_right": (policy.bottom_right, g.right_fold, g.bottom_fold),
        "top_left": (policy.top_left, g.left_fold, g.top_fold),
        "top_right": (policy.top_right, g.right_fold, g.top_fold),
    }
    cuts = []
    for name, (selection, fold_u, fold_v) in specs.items():
        relief = resolve_corner_relief(
            selection, fold_u=fold_u, fold_v=fold_v, thickness=g.thickness,
            fw=policy.fw_for(name),
        )
        if relief.primary_u > g.total_width or relief.primary_v > g.total_height:
            raise GeometryError("corner relief exceeds blank dimensions")
        if relief.secondary_u is not None and relief.secondary_u > g.total_width:
            raise GeometryError("secondary corner relief exceeds blank dimensions")
        if relief.secondary_depth is not None and relief.primary_v + relief.secondary_depth > g.total_height:
            raise GeometryError("secondary corner relief exceeds blank dimensions")
        cuts.extend(_placed_corner_cut_polygons(
            corner_name=name, relief=relief, width=g.total_width, height=g.total_height
        ))
    return cuts


def _four_side_material_polygon(
    g: FourSideFlangeGeometry,
    policy: RectCornerReliefPolicy | FourCornerTypePolicy,
):
    _require_shapely()
    w, h = g.total_width, g.total_height
    blank = box(0.0, 0.0, w, h)
    if isinstance(policy, RectCornerReliefPolicy):
        _validate_four_side(g, policy)
        cuts = [
            box(0.0, 0.0, policy.bottom_left_x, policy.bottom_y),
            box(w - policy.bottom_right_x, 0.0, w, policy.bottom_y),
            box(0.0, h - policy.top_y, policy.top_left_x, h),
            box(w - policy.top_right_x, h - policy.top_y, w, h),
        ]
    elif isinstance(policy, FourCornerTypePolicy):
        cuts = _four_side_type_cut_polygons(g, policy)
    else:
        raise TypeError(f"unsupported corner policy: {type(policy).__name__}")
    cut_union = unary_union(cuts) if cuts else None
    result = blank if cut_union is None else blank.difference(cut_union)
    if result.geom_type != "Polygon" or result.is_empty or not result.is_valid:
        raise GeometryError("invalid four-side flange outline")
    return orient(result, sign=1.0)


def build_four_side_outline(
    g: FourSideFlangeGeometry,
    policy: RectCornerReliefPolicy | FourCornerTypePolicy,
) -> list[Vec2]:
    result = _four_side_material_polygon(g, policy)
    return _normalize_ring(result.exterior.coords)


def _clip_axis_bend(name: str, line: LineString, material, vertical: bool) -> BendLine:
    clipped = material.intersection(line)
    if clipped.is_empty:
        raise GeometryError(f"bend {name} does not intersect material")
    if clipped.geom_type == "MultiLineString":
        clipped = max(clipped.geoms, key=lambda geom: geom.length)
    if clipped.geom_type != "LineString":
        raise GeometryError(f"bend {name} did not clip to a line")
    coords = list(clipped.coords)
    a = Vec2(float(coords[0][0]), float(coords[0][1]))
    b = Vec2(float(coords[-1][0]), float(coords[-1][1]))
    if vertical:
        if a.y > b.y:
            a, b = b, a
    elif a.x > b.x:
        a, b = b, a
    return BendLine(name, a, b)


def build_four_side_bend_segments(
    g: FourSideFlangeGeometry,
    policy: RectCornerReliefPolicy | FourCornerTypePolicy,
    extent: FourSideBendExtentPolicy = FourSideBendExtentPolicy(),
) -> list[BendLine]:
    _require_shapely()
    material = _four_side_material_polygon(g, policy)
    w, h = g.total_width, g.total_height
    vertical = [
        _clip_axis_bend("left", LineString([(g.left_fold, 0.0), (g.left_fold, h)]), material, True),
        _clip_axis_bend("right", LineString([(w - g.right_fold, 0.0), (w - g.right_fold, h)]), material, True),
    ]
    if extent.horizontal_to_blank_edges:
        horizontal = [
            BendLine("bottom", Vec2(0.0, g.bottom_fold), Vec2(w, g.bottom_fold)),
            BendLine("top", Vec2(0.0, h - g.top_fold), Vec2(w, h - g.top_fold)),
        ]
    else:
        horizontal = [
            _clip_axis_bend("bottom", LineString([(0.0, g.bottom_fold), (w, g.bottom_fold)]), material, False),
            _clip_axis_bend("top", LineString([(0.0, h - g.top_fold), (w, h - g.top_fold)]), material, False),
        ]
    return vertical + horizontal


@dataclass(frozen=True)
class EndCapGeometry:
    total_width: float
    total_depth: float
    thickness: float
    fw: float
    left_fold: float
    right_fold: float
    top_first_fold: float
    bottom_fold: float


@dataclass(frozen=True)
class EndCapReliefDimensions:
    top_primary_left: float
    top_primary_right: float
    top_primary_height: float
    top_secondary_left: float
    top_secondary_right: float
    top_secondary_depth_left: float
    top_secondary_depth_right: float
    bottom_left: float
    bottom_right: float
    bottom_height: float


@dataclass(frozen=True)
class EndCapTopology:
    left_bend: BendLine
    right_bend: BendLine
    bottom_bend: BendLine
    top_chain_bend_1: BendLine
    top_chain_bend_2: BendLine
    bottom_left: Corner
    bottom_right: Corner
    top_chain_left_1: Corner
    top_chain_right_1: Corner
    top_chain_left_2: Corner
    top_chain_right_2: Corner


def _cross(a: Vec2, b: Vec2) -> float:
    return a.x * b.y - a.y * b.x


def _normalized(v: Vec2, tol: float = DEFAULT_TOLERANCE) -> Vec2:
    length = v.length()
    if length <= tol:
        raise GeometryError("zero-length direction vector")
    return Vec2(v.x / length, v.y / length)


def line_intersection(
    a: BendLine,
    b: BendLine,
    tol: float = DEFAULT_TOLERANCE,
) -> Vec2:
    """Return the intersection of the two infinite bend lines."""
    p = a.p1
    r = a.p2 - a.p1
    q = b.p1
    s = b.p2 - b.p1
    denominator = _cross(r, s)
    if abs(denominator) <= tol:
        raise GeometryError("bend lines are parallel or degenerate")
    t = _cross(q - p, s) / denominator
    return Vec2(p.x + t * r.x, p.y + t * r.y)


def _validate_endcap(g: EndCapGeometry) -> None:
    if g.thickness <= 0:
        raise GeometryError("板厚必須大於 0")
    if g.total_width <= 0 or g.total_depth <= 0:
        raise GeometryError("blank dimensions must be greater than zero")
    if g.fw < 0:
        raise GeometryError("FW must not be negative")


def _factor_or_override(
    override: float | None,
    factor: float,
    thickness: float,
    name: str,
) -> float:
    value = override if override is not None else factor * thickness
    if value < 0:
        raise GeometryError(f"{name} must not be negative")
    return float(value)


def calculate_endcap_relief_dimensions(
    g: EndCapGeometry,
    cfg: ReliefConfig = ReliefConfig(),
) -> EndCapReliefDimensions:
    """Resolve the fixed Vault EndCap mapping through CornerType composition.

    Vault is intentionally not user-selectable: bottom corners are C03 and top
    corners are C04.  ReliefConfig remains a narrow Factory Policy override for
    the C03/C04 residual clearances; fold dimensions stay outside the type rule.
    """
    _validate_endcap(g)
    left = abs(g.left_fold)
    right = abs(g.right_fold)
    top = abs(g.top_first_fold)
    bottom = abs(g.bottom_fold)

    left_secondary_extra = _factor_or_override(
        cfg.top_secondary_x_left,
        cfg.top_secondary_x_factor,
        g.thickness,
        "top_secondary_x_left",
    )
    right_secondary_extra = _factor_or_override(
        cfg.top_secondary_x_right,
        cfg.top_secondary_x_factor,
        g.thickness,
        "top_secondary_x_right",
    )
    left_secondary_depth = _factor_or_override(
        cfg.top_secondary_depth_left,
        cfg.top_secondary_depth_factor,
        g.thickness,
        "top_secondary_depth_left",
    )
    right_secondary_depth = _factor_or_override(
        cfg.top_secondary_depth_right,
        cfg.top_secondary_depth_factor,
        g.thickness,
        "top_secondary_depth_right",
    )
    left_bottom_extra = _factor_or_override(
        cfg.bottom_x_left,
        cfg.bottom_x_factor,
        g.thickness,
        "bottom_x_left",
    )
    right_bottom_extra = _factor_or_override(
        cfg.bottom_x_right,
        cfg.bottom_x_factor,
        g.thickness,
        "bottom_x_right",
    )
    bottom_y_extra = _factor_or_override(
        cfg.bottom_y,
        cfg.bottom_y_factor,
        g.thickness,
        "bottom_y",
    )

    # 舊 C04 現在會轉成「嵌入貼外型」。UI 仍以「嵌入留肉」表達，
    # 但實際二級 CUTTING 必須維持原本 C04 幾何：側折 + xT，深度 2T。
    # FW - xT 是兩級切線之間剩下的材料寬度，不是第二級 CUTTING 座標。
    c04 = corner_selection_residual(VAULT_C04, thickness=g.thickness, fw=g.fw)
    top_left = compose_corner_residual(
        CornerTypeResidual(
            c04.primary,
            left_secondary_extra,
            left_secondary_depth,
        ),
        fold_u=left, fold_v=top,
    )
    top_right = compose_corner_residual(
        CornerTypeResidual(
            c04.primary,
            right_secondary_extra,
            right_secondary_depth,
        ),
        fold_u=right, fold_v=top,
    )

    # C03 intrinsic rule is (+0.5T, +0.5T). ReliefConfig can override those
    # residual clearances while the actual fold sizes remain topology data.
    bottom_left = compose_corner_residual(
        CornerTypeResidual((left_bottom_extra, bottom_y_extra)),
        fold_u=left, fold_v=bottom,
    )
    bottom_right = compose_corner_residual(
        CornerTypeResidual((right_bottom_extra, bottom_y_extra)),
        fold_u=right, fold_v=bottom,
    )

    dims = EndCapReliefDimensions(
        top_primary_left=top_left.primary_u,
        top_primary_right=top_right.primary_u,
        top_primary_height=top_left.primary_v,
        top_secondary_left=top_left.secondary_u or 0.0,
        top_secondary_right=top_right.secondary_u or 0.0,
        top_secondary_depth_left=top_left.secondary_depth or 0.0,
        top_secondary_depth_right=top_right.secondary_depth or 0.0,
        bottom_left=bottom_left.primary_u,
        bottom_right=bottom_right.primary_u,
        bottom_height=bottom_left.primary_v,
    )
    for name, value in dims.__dict__.items():
        if value < 0:
            raise GeometryError(f"relief dimension {name} must not be negative")
    if dims.top_primary_height <= 0:
        raise GeometryError("top primary relief height must be greater than zero")
    return dims


def _corner(name: str, a: BendLine, b: BendLine) -> Corner:
    point = line_intersection(a, b)
    u = _normalized(a.p2 - a.p1)
    v = _normalized(b.p2 - b.p1)
    return Corner(name=name, point=point, u=u, v=v, bends=(a, b))


def build_endcap_topology(g: EndCapGeometry) -> EndCapTopology:
    """Build fold/bend topology without assigning a panel-type-specific outline."""
    _validate_endcap(g)
    left_x = abs(g.left_fold)
    right_x = g.total_width - abs(g.right_fold)
    bottom_y = abs(g.bottom_fold)

    # Existing flat-pattern chain:
    # total_depth = bottom + body_depth_minus_3T + FW + top_first_fold
    top_chain_y1 = g.total_depth - abs(g.top_first_fold) - g.fw
    top_chain_y2 = g.total_depth - abs(g.top_first_fold)

    left_bend = BendLine("left", Vec2(left_x, 0.0), Vec2(left_x, g.total_depth))
    right_bend = BendLine("right", Vec2(right_x, 0.0), Vec2(right_x, g.total_depth))
    bottom_bend = BendLine("bottom", Vec2(0.0, bottom_y), Vec2(g.total_width, bottom_y))
    top_1 = BendLine("top_chain_1", Vec2(0.0, top_chain_y1), Vec2(g.total_width, top_chain_y1))
    top_2 = BendLine("top_chain_2", Vec2(0.0, top_chain_y2), Vec2(g.total_width, top_chain_y2))

    return EndCapTopology(
        left_bend=left_bend,
        right_bend=right_bend,
        bottom_bend=bottom_bend,
        top_chain_bend_1=top_1,
        top_chain_bend_2=top_2,
        bottom_left=_corner("bottom_left", left_bend, bottom_bend),
        bottom_right=_corner("bottom_right", right_bend, bottom_bend),
        top_chain_left_1=_corner("top_chain_left_1", left_bend, top_1),
        top_chain_right_1=_corner("top_chain_right_1", right_bend, top_1),
        top_chain_left_2=_corner("top_chain_left_2", left_bend, top_2),
        top_chain_right_2=_corner("top_chain_right_2", right_bend, top_2),
    )



def _endcap_manual_material_polygon(
    g: EndCapGeometry,
    policy: FourCornerTypePolicy,
    *,
    relief_left_fold: float | None = None,
    relief_right_fold: float | None = None,
    bottom_relief_left_fold: float | None = None,
    bottom_relief_right_fold: float | None = None,
):
    """Material polygon for manual/unknown EndCap using CornerType selections."""
    _require_shapely()
    _validate_endcap(g)
    left_basis = abs(g.left_fold if relief_left_fold is None else float(relief_left_fold))
    right_basis = abs(g.right_fold if relief_right_fold is None else float(relief_right_fold))
    bottom_left_basis = abs(
        left_basis if bottom_relief_left_fold is None else float(bottom_relief_left_fold)
    )
    bottom_right_basis = abs(
        right_basis if bottom_relief_right_fold is None else float(bottom_relief_right_fold)
    )
    specs = {
        "bottom_left": (policy.bottom_left, bottom_left_basis, abs(g.bottom_fold)),
        "bottom_right": (policy.bottom_right, bottom_right_basis, abs(g.bottom_fold)),
        "top_left": (policy.top_left, left_basis, abs(g.top_first_fold)),
        "top_right": (policy.top_right, right_basis, abs(g.top_first_fold)),
    }
    cuts = []
    for name, (selection, fold_u, fold_v) in specs.items():
        relief = resolve_corner_relief(
            selection,
            fold_u=fold_u,
            fold_v=fold_v,
            thickness=g.thickness,
            fw=policy.fw_for(name),
        )
        cuts.extend(_placed_corner_cut_polygons(
            corner_name=name,
            relief=relief,
            width=g.total_width,
            height=g.total_depth,
        ))
    blank = box(0.0, 0.0, g.total_width, g.total_depth)
    result = blank.difference(unary_union(cuts)) if cuts else blank
    if result.is_empty or result.geom_type != "Polygon" or not result.is_valid:
        raise GeometryError("invalid manual EndCap corner reliefs")
    return orient(result, sign=1.0)


def build_endcap_outline_from_corner_types(
    g: EndCapGeometry,
    policy: FourCornerTypePolicy,
    *,
    relief_left_fold: float | None = None,
    relief_right_fold: float | None = None,
    bottom_relief_left_fold: float | None = None,
    bottom_relief_right_fold: float | None = None,
) -> list[Vec2]:
    """Build unknown/manual EndCap CUTTING from fold geometry + CornerType only."""
    material = _endcap_manual_material_polygon(
        g, policy,
        relief_left_fold=relief_left_fold,
        relief_right_fold=relief_right_fold,
        bottom_relief_left_fold=bottom_relief_left_fold,
        bottom_relief_right_fold=bottom_relief_right_fold,
    )
    return _normalize_ring(material.exterior.coords)


def build_endcap_bend_segments_from_corner_types(
    g: EndCapGeometry,
    policy: FourCornerTypePolicy,
    *,
    relief_left_fold: float | None = None,
    relief_right_fold: float | None = None,
    bottom_relief_left_fold: float | None = None,
    bottom_relief_right_fold: float | None = None,
) -> list[BendLine]:
    """Clip EndCap bends against CornerType material using an optional nominal relief basis."""
    material = _endcap_manual_material_polygon(
        g, policy,
        relief_left_fold=relief_left_fold,
        relief_right_fold=relief_right_fold,
        bottom_relief_left_fold=bottom_relief_left_fold,
        bottom_relief_right_fold=bottom_relief_right_fold,
    )
    topo = build_endcap_topology(g)
    return [
        _clip_axis_bend(
            "left",
            LineString([(topo.left_bend.p1.x, 0.0), (topo.left_bend.p1.x, g.total_depth)]),
            material,
            True,
        ),
        _clip_axis_bend(
            "right",
            LineString([(topo.right_bend.p1.x, 0.0), (topo.right_bend.p1.x, g.total_depth)]),
            material,
            True,
        ),
        _clip_axis_bend(
            "bottom",
            LineString([(0.0, topo.bottom_bend.p1.y), (g.total_width, topo.bottom_bend.p1.y)]),
            material,
            False,
        ),
        _clip_axis_bend(
            "top_chain_1",
            LineString([(0.0, topo.top_chain_bend_1.p1.y), (g.total_width, topo.top_chain_bend_1.p1.y)]),
            material,
            False,
        ),
        _clip_axis_bend(
            "top_chain_2",
            LineString([(0.0, topo.top_chain_bend_2.p1.y), (g.total_width, topo.top_chain_bend_2.p1.y)]),
            material,
            False,
        ),
    ]


def build_endcap_bend_segments(
    g: EndCapGeometry,
    cfg: ReliefConfig = ReliefConfig(),
) -> list[BendLine]:
    """Return the five physical bend segments clipped to remaining material."""
    topo = build_endcap_topology(g)
    dims = calculate_endcap_relief_dimensions(g, cfg)

    left_x = topo.left_bend.p1.x
    right_x = topo.right_bend.p1.x
    bottom_y = topo.bottom_bend.p1.y
    top_1_y = topo.top_chain_bend_1.p1.y
    top_2_y = topo.top_chain_bend_2.p1.y

    top_primary_bottom = g.total_depth - dims.top_primary_height
    left_top = top_primary_bottom - dims.top_secondary_depth_left
    right_top = top_primary_bottom - dims.top_secondary_depth_right

    return [
        BendLine("left", Vec2(left_x, dims.bottom_height), Vec2(left_x, left_top)),
        BendLine("right", Vec2(right_x, dims.bottom_height), Vec2(right_x, right_top)),
        BendLine(
            "bottom",
            Vec2(dims.bottom_left, bottom_y),
            Vec2(g.total_width - dims.bottom_right, bottom_y),
        ),
        BendLine(
            "top_chain_1",
            Vec2(dims.top_secondary_left, top_1_y),
            Vec2(g.total_width - dims.top_secondary_right, top_1_y),
        ),
        BendLine(
            "top_chain_2",
            Vec2(dims.top_primary_left, top_2_y),
            Vec2(g.total_width - dims.top_primary_right, top_2_y),
        ),
    ]


def _validate_reliefs_fit_blank(
    g: EndCapGeometry,
    dims: EndCapReliefDimensions,
) -> None:
    if (
        dims.bottom_left > g.total_width
        or dims.bottom_right > g.total_width
        or dims.top_primary_left > g.total_width
        or dims.top_primary_right > g.total_width
        or dims.top_secondary_left > g.total_width
        or dims.top_secondary_right > g.total_width
        or dims.bottom_height > g.total_depth
        or dims.top_primary_height > g.total_depth
        or dims.top_primary_height + dims.top_secondary_depth_left > g.total_depth
        or dims.top_primary_height + dims.top_secondary_depth_right > g.total_depth
    ):
        raise GeometryError("relief exceeds blank dimensions")

    # Opposing reliefs must leave some material at each affected level.
    if (
        dims.bottom_left + dims.bottom_right >= g.total_width
        or dims.top_primary_left + dims.top_primary_right >= g.total_width
        or dims.top_secondary_left + dims.top_secondary_right >= g.total_width
    ):
        raise GeometryError("relief exceeds blank dimensions")


def _require_shapely() -> None:
    if Polygon is None or box is None or unary_union is None:
        raise GeometryError(
            "Shapely is required for boolean outline generation in this build"
        )


def build_endcap_reliefs(
    g: EndCapGeometry,
    cfg: ReliefConfig = ReliefConfig(),
) -> list[ReliefPolygon]:
    """Return material-removal polygons for the current assembly rule."""
    _require_shapely()
    dims = calculate_endcap_relief_dimensions(g, cfg)
    _validate_reliefs_fit_blank(g, dims)
    w, h = g.total_width, g.total_depth
    top_primary_y = h - dims.top_primary_height

    specs = [
        ("bottom_left", "assembly_bottom", box(0, 0, dims.bottom_left, dims.bottom_height)),
        (
            "bottom_right",
            "assembly_bottom",
            box(w - dims.bottom_right, 0, w, dims.bottom_height),
        ),
        (
            "top_primary_left",
            "flush_front_primary",
            box(0, top_primary_y, dims.top_primary_left, h),
        ),
        (
            "top_primary_right",
            "flush_front_primary",
            box(w - dims.top_primary_right, top_primary_y, w, h),
        ),
        (
            "top_secondary_left",
            "assembly_insertion_secondary",
            box(
                0,
                top_primary_y - dims.top_secondary_depth_left,
                dims.top_secondary_left,
                top_primary_y,
            ),
        ),
        (
            "top_secondary_right",
            "assembly_insertion_secondary",
            box(
                w - dims.top_secondary_right,
                top_primary_y - dims.top_secondary_depth_right,
                w,
                top_primary_y,
            ),
        ),
    ]
    return [
        ReliefPolygon(
            rule_name=rule,
            source_corner=name,
            polygon=poly,
            metadata={"area": float(poly.area)},
        )
        for name, rule, poly in specs
    ]


def _normalize_ring(points: Iterable[tuple[float, float]]) -> list[Vec2]:
    coords = [Vec2(float(x), float(y)) for x, y in points]
    if len(coords) < 4:
        raise GeometryError("outline exterior has too few points")
    if coords[0] == coords[-1]:
        coords = coords[:-1]

    # Deterministic start: left-most surviving point on the bottom edge.
    min_y = min(p.y for p in coords)
    bottom_indices = [
        i for i, p in enumerate(coords) if math.isclose(p.y, min_y, abs_tol=DEFAULT_TOLERANCE)
    ]
    start = min(bottom_indices, key=lambda i: coords[i].x)

    rotated = coords[start:] + coords[:start]
    rotated.append(rotated[0])
    return rotated


def build_endcap_outline(
    g: EndCapGeometry,
    cfg: ReliefConfig = ReliefConfig(),
) -> list[Vec2]:
    """Build the final CUTTING exterior by subtracting relief polygons."""
    _require_shapely()
    _validate_endcap(g)

    blank = box(0.0, 0.0, g.total_width, g.total_depth)
    reliefs = build_endcap_reliefs(g, cfg)
    cut_union = unary_union([r.polygon for r in reliefs])
    result = blank.difference(cut_union)

    if result.is_empty:
        raise GeometryError("relief removes the entire blank")
    if result.geom_type != "Polygon":
        raise GeometryError(
            f"expected one exterior polygon after relief, got {result.geom_type}"
        )
    if not result.is_valid:
        raise GeometryError("generated outline is invalid")
    if result.area <= DEFAULT_TOLERANCE:
        raise GeometryError("generated outline has no positive area")

    # Make orientation deterministic before rotating the start vertex.
    result = orient(result, sign=1.0)
    return _normalize_ring(result.exterior.coords)

@dataclass(frozen=True)
class FoldSegment:
    name: str
    length: float
    compensation: float = 0.0


@dataclass(frozen=True)
class StripFoldChain:
    segments: tuple[FoldSegment, ...]
    height: float

    @property
    def total_width(self) -> float:
        return sum(float(s.length) + float(s.compensation) for s in self.segments)


def _validate_strip_chain(chain: StripFoldChain) -> None:
    if chain.height <= 0:
        raise GeometryError("strip height must be greater than zero")
    if len(chain.segments) < 2:
        raise GeometryError("strip chain requires at least two segments")
    for segment in chain.segments:
        if segment.length < 0:
            raise GeometryError(f"segment {segment.name} length must not be negative")
        if segment.length + segment.compensation <= 0:
            raise GeometryError(f"segment {segment.name} effective length must be positive")


def build_strip_outline(chain: StripFoldChain) -> list[Vec2]:
    _validate_strip_chain(chain)
    w = chain.total_width
    h = float(chain.height)
    return [Vec2(0.0, 0.0), Vec2(w, 0.0), Vec2(w, h), Vec2(0.0, h), Vec2(0.0, 0.0)]


def build_strip_bend_segments(chain: StripFoldChain) -> list[BendLine]:
    _validate_strip_chain(chain)
    x = 0.0
    bends: list[BendLine] = []
    for segment in chain.segments[:-1]:
        x += float(segment.length) + float(segment.compensation)
        bends.append(BendLine(segment.name, Vec2(x, 0.0), Vec2(x, float(chain.height))))
    return bends
