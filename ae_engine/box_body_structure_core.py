# -*- coding: utf-8 -*-
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
