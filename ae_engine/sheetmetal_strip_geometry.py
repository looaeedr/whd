# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Strip-fold geometry owner."""
from __future__ import annotations

from dataclasses import dataclass
import math

from .sheetmetal_geometry_core import GeometryError, Vec2, BendLine

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
    if (isinstance(chain.height, bool) or not math.isfinite(float(chain.height))
            or chain.height <= 0):
        raise GeometryError("strip height must be greater than zero")
    if len(chain.segments) < 2:
        raise GeometryError("strip chain requires at least two segments")
    for segment in chain.segments:
        if (isinstance(segment.length, bool)
                or isinstance(segment.compensation, bool)
                or not math.isfinite(float(segment.length))
                or not math.isfinite(float(segment.compensation))):
            raise GeometryError(f"segment {segment.name} dimensions must be finite numbers")
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
        # BEND 的展開 X 是有效料段的累計終點，不是折後包外邊界；不得在此另外加 T。
        x += float(segment.length) + float(segment.compensation)
        bends.append(BendLine(segment.name, Vec2(x, 0.0), Vec2(x, float(chain.height))))
    return bends
