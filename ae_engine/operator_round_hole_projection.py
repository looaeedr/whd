# -*- coding: utf-8 -*-
"""Headless Engine physical round-hole preview; GUI owns only session actions."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

from .sheetmetal_features import (
    CircleFeature, align_circle_to_neighbor, feature_finished_point,
    feature_is_within_surface, generate_round_fill, generate_round_refill,
)


def operator_round_hole_default_center_distance(diameter: object) -> float:
    """Resolve the existing operator round-fill center pitch from physical diameter.

    This is a default for the editable operator field, not a manufactured
    hole or an approval to export; the preview planner remains authoritative.
    """
    if isinstance(diameter, bool):
        raise ValueError("圓孔直徑必須為正有限數值")
    try:
        numeric = float(diameter)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("圓孔直徑必須為正有限數值") from exc
    if not isfinite(numeric) or numeric <= 0:
        raise ValueError("圓孔直徑必須為正有限數值")
    pitch = numeric * 2.0
    if not isfinite(pitch):
        raise ValueError("圓孔預設孔心距必須為正有限數值")
    return max(pitch, 50.0)


@dataclass(frozen=True)
class OperatorRoundHolePreview:
    features: tuple[object, ...]
    selected_index: int
    generated_count: int


def nearest_operator_round_hole_neighbor_index(
    features, selected_index, *, width: float, height: float,
) -> int | None:
    """Resolve the nearest existing circle, preserving original tie order."""
    rows = tuple(features)
    if type(selected_index) is not int or not 0 <= selected_index < len(rows):
        raise ValueError("選取的圓孔索引無效")
    seed = rows[selected_index]
    if not isinstance(seed, CircleFeature):
        raise ValueError("選取的板件特徵不是圓孔")
    point = feature_finished_point(seed, width, height)
    nearest, minimum = None, None
    for i, item in enumerate(rows):
        if i == selected_index or not isinstance(item, CircleFeature):
            continue
        other = feature_finished_point(item, width, height)
        distance = (other.x - point.x) ** 2 + (other.y - point.y) ** 2
        if minimum is None or distance < minimum:
            nearest, minimum = i, distance
    return nearest


def plan_operator_round_hole_preview(
    features, selected_index, surface, *,
    width: float, height: float, direction: str,
    driver: str, value: float, alignment: str = "center",
    neighbor_index: int | None = None, refill: bool = False,
) -> OperatorRoundHolePreview:
    """Plan actual finished-face holes without mutating workspace or session."""
    rows = tuple(features)
    if type(selected_index) is not int or not 0 <= selected_index < len(rows):
        raise ValueError("選取的圓孔索引無效")
    selected = rows[selected_index]
    if not isinstance(selected, CircleFeature):
        raise ValueError("選取的板件特徵不是圓孔")
    seed = selected
    if neighbor_index is not None:
        if (type(neighbor_index) is not int
                or not 0 <= neighbor_index < len(rows)
                or neighbor_index == selected_index
                or not isinstance(rows[neighbor_index], CircleFeature)):
            raise ValueError("鄰近圓孔索引無效")
        axis = "x" if direction in {"left", "right", "both_horizontal"} else "y"
        aligned = align_circle_to_neighbor(
            seed, rows[neighbor_index], alignment, axis, width, height,
        )
        if feature_is_within_surface(surface, aligned, width, height):
            seed = aligned
    generator = generate_round_refill if refill else generate_round_fill
    generated = generator(
        seed, surface, width=width, height=height,
        direction=direction, driver=driver, value=value,
    )
    if not generated:
        raise ValueError("目前設定無法在合法板面內產生圓孔排列")
    origin = feature_finished_point(selected, width, height)
    replacement = min(generated, key=lambda feature: (
        (feature_finished_point(feature, width, height).x - origin.x) ** 2
        + (feature_finished_point(feature, width, height).y - origin.y) ** 2
    ))
    projected = list(rows)
    projected[selected_index] = replacement
    projected.extend(feature for feature in generated if feature is not replacement)
    return OperatorRoundHolePreview(
        features=tuple(projected), selected_index=selected_index,
        generated_count=len(generated),
    )
