# -*- coding: utf-8 -*-
"""One physical outside/inside sheet datum for Receiving assembly and inversion.

All coordinates describe real sheet faces.  The mid-surface is derived ONLY
for folding/render placement; it is never a cutting or MARKING authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class SideSheetDatum:
    """Parallel left/right side sheets derived from the same outside W and T."""

    outside_width: float
    thickness: float
    center_x: float = 0.0

    def __post_init__(self) -> None:
        if (
            isinstance(self.outside_width, bool)
            or isinstance(self.thickness, bool)
            or isinstance(self.center_x, bool)
        ):
            raise ValueError("side-sheet physical datum dimensions cannot be boolean")
        w, t, center = float(self.outside_width), float(self.thickness), float(self.center_x)
        if not all(isfinite(v) for v in (w, t, center)):
            raise ValueError("side-sheet physical datum requires finite W/T/center")
        if t < 0.0 or w <= 2.0 * t:
            raise ValueError("side-sheet outside width must exceed two sheet thicknesses")
        object.__setattr__(self, "outside_width", w)
        object.__setattr__(self, "thickness", t)
        object.__setattr__(self, "center_x", center)

    @classmethod
    def from_outside_width(
        cls, outside_width: float, thickness: float, *, center_x: float = 0.0
    ) -> "SideSheetDatum":
        if isinstance(outside_width, bool) or isinstance(thickness, bool) or isinstance(center_x, bool):
            raise ValueError("side-sheet physical datum dimensions cannot be boolean")
        return cls(outside_width=float(outside_width), thickness=float(thickness), center_x=float(center_x))

    @classmethod
    def from_inner_faces(
        cls, left_inner: float, right_inner: float, thickness: float
    ) -> "SideSheetDatum":
        """Reverse real inside faces using the SAME thickness datum as forward placement."""
        if isinstance(left_inner, bool) or isinstance(right_inner, bool) or isinstance(thickness, bool):
            raise ValueError("side-sheet physical datum dimensions cannot be boolean")
        left, right, t = float(left_inner), float(right_inner), float(thickness)
        return cls(
            outside_width=(right - left) + 2.0 * t,
            thickness=t,
            center_x=(left + right) / 2.0,
        )

    @property
    def inner_clear_width(self) -> float:
        return self.inside_face(+1) - self.inside_face(-1)

    def outside_face(self, side: int) -> float:
        if isinstance(side, bool) or side not in (-1, +1):
            raise ValueError("sheet side must be -1 (left) or +1 (right)")
        return self.center_x + side * self.outside_width / 2.0

    def inside_face(self, side: int) -> float:
        # The true inward-facing solid skin, NOT the sheet's mid-surface.
        return self.outside_face(side) - side * self.thickness

    def mid_surface(self, side: int) -> float:
        # Only renderer/assembly folds use the sheet mid-surface.
        return (self.inside_face(side) + self.outside_face(side)) / 2.0
