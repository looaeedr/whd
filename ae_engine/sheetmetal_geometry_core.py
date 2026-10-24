# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Core sheet-metal geometry value types and corner-selection values."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math

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
    slot_width: float | None = None
    slot_straight_depth: float | None = None
    slot_radius: float | None = None


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
    slot_width: float | None = None
    slot_straight_depth: float | None = None
    slot_radius: float | None = None

    def __post_init__(self):
        type_id = CornerTypeId(self.type_id)
        object.__setattr__(self, "type_id", type_id)
        if isinstance(self.rotation_quadrants, bool):
            raise GeometryError("corner rotation must not be bool")
        rotation = float(self.rotation_quadrants)
        if not math.isfinite(rotation) or not rotation.is_integer():
            raise GeometryError("corner rotation must be a finite integer")
        object.__setattr__(self, "rotation_quadrants", int(rotation) % 4)

        def numeric(value, field):
            if value is None:
                return None
            if isinstance(value, bool):
                raise GeometryError(f"{field}不可為布林值")
            result = float(value)
            if not math.isfinite(result):
                raise GeometryError(f"{field}必須為有限數值")
            return result

        mode = None if self.cross_mode is None else CrossCornerMode(self.cross_mode)
        direction = None if self.direction is None else CornerDirection(self.direction)
        amount = numeric(self.amount_t, "截角量")
        secondary_retain = numeric(self.secondary_retain_t, "二級留肉量")
        secondary_depth = numeric(self.secondary_depth_t, "二級深度")
        slot_width = numeric(self.slot_width, "槽寬")
        slot_straight_depth = numeric(self.slot_straight_depth, "槽直段深度")
        slot_radius = numeric(self.slot_radius, "槽R")

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
            slot_values = (slot_width, slot_straight_depth, slot_radius)
            if any(value is not None for value in slot_values):
                if not all(value is not None for value in slot_values):
                    raise GeometryError("十字截角槽參數必須同時提供寬度、直段深度與R")
                if slot_width <= 0 or slot_straight_depth <= 0 or slot_radius <= 0:
                    raise GeometryError("十字截角槽參數必須大於 0")
                if 2.0 * slot_radius > slot_width + DEFAULT_TOLERANCE:
                    raise GeometryError("十字截角槽 R 不可大於槽寬的一半")
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
        if type_id is not CornerTypeId.CROSS:
            slot_width = None
            slot_straight_depth = None
            slot_radius = None

        object.__setattr__(self, "cross_mode", mode)
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "amount_t", amount)
        object.__setattr__(self, "secondary_retain_t", secondary_retain)
        object.__setattr__(self, "secondary_depth_t", secondary_depth)
        object.__setattr__(self, "slot_width", slot_width)
        object.__setattr__(self, "slot_straight_depth", slot_straight_depth)
        object.__setattr__(self, "slot_radius", slot_radius)


@dataclass(frozen=True)
class ResolvedCornerRelief:
    """Actual cut extents after fold base + intrinsic CornerType are composed."""
    primary_u: float
    primary_v: float
    secondary_u: float | None = None
    secondary_depth: float | None = None
    slot_width: float | None = None
    slot_straight_depth: float | None = None
    slot_radius: float | None = None
