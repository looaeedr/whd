# -*- coding: utf-8 -*-
"""Canonical IndicatorBox MARKING row defaults, shared by DXF and GUI.

The operator-facing fields are projections of actual Engine marking geometry,
not a second client-owned manufacturing formula.
"""
from __future__ import annotations

from dataclasses import dataclass

from .sheetmetal_features import (
    _normalize_indicator_groups, indicator_box_outer_size,
)


@dataclass(frozen=True)
class IndicatorBoxMarkingLayout:
    group_max: int
    count: int
    start_x: float
    pitch: float
    first_row_y: float

    @property
    def positions_x(self) -> tuple[float, ...]:
        return tuple(self.start_x + index * self.pitch for index in range(self.count))


def project_indicator_box_marking_layout(layer_groups) -> IndicatorBoxMarkingLayout:
    """Return the same actual MARKING row that IndicatorBox manufacturing draws."""
    groups = _normalize_indicator_groups(layer_groups)
    # Reuse validated physical size/limits; no invalid/empty pattern may be
    # presented as an operator marking default.
    indicator_box_outer_size(groups)
    group_max = max(groups)
    count = 1 if group_max <= 1 else 2 if group_max <= 3 else 3 if group_max <= 5 else 4
    if count == 1:
        return IndicatorBoxMarkingLayout(
            group_max=group_max, count=1, start_x=191.0, pitch=150.0,
            first_row_y=178.5,
        )
    left = 171.0
    right = left + 90.0 * (group_max - 1)
    pitch = max(50.0, float(int(((right - left) / (count - 1)) // 50) * 50))
    mid = (left + right) / 2.0
    return IndicatorBoxMarkingLayout(
        group_max=group_max, count=count,
        start_x=mid - (count - 1) * pitch / 2.0,
        pitch=pitch, first_row_y=178.5,
    )
