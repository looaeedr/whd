# -*- coding: utf-8 -*-
# WHD 製造／3D 共用尺寸不變式（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 包外是折後外側面的成形尺寸；料段 len = 其包外段尺寸 −（實際相鄰折彎數 0/1/2 × T），已轉成料長的資料不得重扣 T。
# 展開 CUTTING = 料段累加；BEND 線位 = 同一料鏈的前綴和，不可直接拿包外尺寸充當展開折彎座標。
# 3D 須依相同 Fold Profile／料鏈／BEND 與角度成形；角度正負只決定方向，禁止從 3D bbox 反推料長。
# 這是板厚尺寸語意，非折彎展開補償；WRAP／OVERLAY 是裝配關係，不等於包外。

"""Core resolved box-body structure value types."""
from __future__ import annotations

from dataclasses import dataclass

from phase6_box_body_structure import BoxBodyStructureType
from .contracts import FoldProfileSegment
from .sheetmetal_geometry_core import (
    CornerTypeId,
    CornerTypeSelection,
    CrossCornerMode,
    CornerDirection,
)
from .sheetmetal_corner_policy import corner_selection_residual
from .sheetmetal_part_adapters import StructuralGeometryResult

@dataclass(frozen=True)
class BoxBodyStructureWarning:
    code: str
    message: str
    piece_key: str | None = None


@dataclass(frozen=True)
class ResolvedBoxBodyPiece:
    key: str
    role: str
    formed_w_start: float
    formed_w_end: float
    fold_profile: tuple[FoldProfileSegment, ...]
    structural: StructuralGeometryResult
    formed_outer_width: float | None = None
    formed_outer_height: float | None = None
    formed_y_offset: float = 0.0

    @property
    def formed_width(self) -> float:
        """Legacy enclosure-W placement span; not the side-panel package width."""
        return float(self.formed_w_end) - float(self.formed_w_start)

    @property
    def formed_outer_dimensions(self) -> tuple[float, float]:
        width = self.formed_width if self.formed_outer_width is None else float(self.formed_outer_width)
        height = float(self.structural.height) if self.formed_outer_height is None else float(self.formed_outer_height)
        return width, height

    @property
    def material_width(self) -> float:
        return float(self.structural.width)

    @property
    def material_height(self) -> float:
        return float(self.structural.height)

    @property
    def material_dimensions(self) -> tuple[float, float]:
        return self.material_width, self.material_height


@dataclass(frozen=True)
class ResolvedBoxBodyStructure:
    structure_type: BoxBodyStructureType
    pieces: tuple[ResolvedBoxBodyPiece, ...]
    warnings: tuple[BoxBodyStructureWarning, ...] = ()




def _canonical_cross_retain_mm(*, amount_t: float, thickness: float, direction: CornerDirection) -> float:
    """Resolve single-side meat through the canonical CROSS/RETAIN domain rule."""
    selection = CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode.RETAIN,
        direction=direction,
        amount_t=float(amount_t),
    )
    residual = corner_selection_residual(selection, thickness=float(thickness), fw=0.0)
    du, dv = residual.primary
    value = -float(du if direction is CornerDirection.WIDTH else dv)
    if value <= 0:
        raise ValueError("十字截角單邊留肉必須大於 0")
    return value
