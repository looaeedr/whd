# -*- coding: utf-8 -*-
# WHD 製造／3D 共用尺寸不變式（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 包外是折後外側面的成形尺寸；料段 len = 其包外段尺寸 −（實際相鄰折彎數 0/1/2 × T），已轉成料長的資料不得重扣 T。
# 展開 CUTTING = 料段累加；BEND 線位 = 同一料鏈的前綴和，不可直接拿包外尺寸充當展開折彎座標。
# 3D 須依相同 Fold Profile／料鏈／BEND 與角度成形；角度正負只決定方向，禁止從 3D bbox 反推料長。
# 這是板厚尺寸語意，非折彎展開補償；WRAP／OVERLAY 是裝配關係，不等於包外。

"""Strip-fold geometry owner."""
from __future__ import annotations

from dataclasses import dataclass

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
        # BEND 的展開 X 是有效料段的累計終點，不是折後包外邊界；不得在此另外加 T。
        x += float(segment.length) + float(segment.compensation)
        bends.append(BendLine(segment.name, Vec2(x, 0.0), Vec2(x, float(chain.height))))
    return bends
