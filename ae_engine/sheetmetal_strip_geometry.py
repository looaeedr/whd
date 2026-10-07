# -*- coding: utf-8 -*-
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
        x += float(segment.length) + float(segment.compensation)
        bends.append(BendLine(segment.name, Vec2(x, 0.0), Vec2(x, float(chain.height))))
    return bends
