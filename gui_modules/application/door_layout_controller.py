"""Bounded application owner for Door Layout numeric state transitions.

This module is intentionally Tk-free and does not own manufacturing, rendering,
workspace, or project state.  The GUI host adapts Tk variables into immutable
numeric columns, applies these transitions, then performs presentation effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Callable, Mapping, Sequence

from ae_engine.sheetmetal_part_adapters import (
    complete_partition,
    validate_door_layout_dimensions,
)


@dataclass(frozen=True)
class DoorLayoutColumnState:
    width: float
    width_auto: bool
    heights: tuple[float, ...]
    height_auto: tuple[bool, ...]


@dataclass(frozen=True)
class DoorLayoutResolvedColumn:
    width: float
    width_auto: bool
    heights: tuple[float, ...]
    height_auto: tuple[bool, ...]
    height_completion: object


@dataclass(frozen=True)
class DoorLayoutRecomputeResult:
    columns: tuple[DoorLayoutResolvedColumn, ...]
    width_completion: object
    selected_key: str


@dataclass(frozen=True)
class DoorLayoutCommitValidation:
    valid: bool
    maximum: float
    other_fixed: float
    keep_auto: bool


def _positive_total(label: str, value: float) -> float:
    # Public controller mutations must not coerce corrupt saved Boolean/NaN
    # geometry into physical dimensions before the validation boundary.
    if isinstance(value, bool):
        raise ValueError(f"{label} 必須是有限正數")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label} 必須是有限正數") from exc
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{label} 必須是有限正數")
    return value


def _physical_cell_index(label: str, value: int, count: int) -> int:
    # An index refers to a specific physical Door cell, never Python's
    # bool alias, negative-index wrapping or int(0.9) truncation.
    if type(value) is not int or value < 0 or value >= count:
        raise ValueError(f"{label} 必須是目前門片的有效整數索引")
    return value


def recompute_door_layout(
    columns: Sequence[DoorLayoutColumnState],
    *,
    total_width: float,
    total_height: float,
    selected_key: str,
) -> DoorLayoutRecomputeResult:
    total_width = _positive_total("W", total_width)
    total_height = _positive_total("H", total_height)
    fixed_columns = [column for column in columns if not column.width_auto]
    width_completion = complete_partition(
        [float(column.width) for column in fixed_columns],
        total_width,
        tolerance=0.01,
    )
    resolved = []
    for column in fixed_columns:
        fixed_heights = [
            float(value)
            for value, is_auto in zip(column.heights, column.height_auto)
            if not is_auto
        ]
        completion = complete_partition(fixed_heights, total_height, tolerance=0.01)
        auto_flags = [False] * len(completion.values)
        if completion.auto_index is not None:
            auto_flags[completion.auto_index] = True
        resolved.append(
            DoorLayoutResolvedColumn(
                width=float(column.width),
                width_auto=False,
                heights=tuple(float(value) for value in completion.values),
                height_auto=tuple(auto_flags),
                height_completion=completion,
            )
        )

    if width_completion.auto_index is not None:
        auto_width = float(width_completion.values[width_completion.auto_index])
        height_completion = complete_partition([], total_height, tolerance=0.01)
        resolved.append(
            DoorLayoutResolvedColumn(
                width=auto_width,
                width_auto=True,
                heights=(total_height,),
                height_auto=(True,),
                height_completion=height_completion,
            )
        )

    if not resolved:
        raise ValueError("門配置至少需要一欄")

    try:
        c_text, r_text = str(selected_key or "").split(":", 1)
        column_index, row_index = int(c_text), int(r_text)
    except (TypeError, ValueError):
        column_index = row_index = 0
    column_index = min(max(column_index, 0), len(resolved) - 1)
    row_index = min(max(row_index, 0), len(resolved[column_index].heights) - 1)
    return DoorLayoutRecomputeResult(
        columns=tuple(resolved),
        width_completion=width_completion,
        selected_key=f"{column_index}:{row_index}",
    )


def door_layout_cells(columns, *, total_width: float, total_height: float):
    # Do not erase a malformed saved Boolean before the manufacturing
    # validator sees its original type (float(True) would become 1 mm).
    return validate_door_layout_dimensions(
        columns,
        total_width=total_width,
        total_height=total_height,
        tolerance=0.01,
    )


def validate_width_commit(
    columns: Sequence[DoorLayoutColumnState],
    column_index: int,
    total_width: float,
    current: float,
) -> DoorLayoutCommitValidation:
    total_width = _positive_total("W", total_width)
    current = _positive_total("欄寬", current)
    column_index = _physical_cell_index("門片欄位", column_index, len(columns))
    other_fixed = sum(
        float(column.width)
        for index, column in enumerate(columns)
        if index != column_index and not column.width_auto
    )
    maximum = total_width - other_fixed
    column = columns[column_index]
    expected = total_width - other_fixed
    keep_auto = bool(column.width_auto and abs(current - expected) <= 0.01)
    return DoorLayoutCommitValidation(
        valid=current <= maximum + 0.01,
        maximum=maximum,
        other_fixed=other_fixed,
        keep_auto=keep_auto,
    )


def validate_height_commit(
    columns: Sequence[DoorLayoutColumnState],
    column_index: int,
    row_index: int,
    total_height: float,
    current: float,
) -> DoorLayoutCommitValidation:
    total_height = _positive_total("H", total_height)
    current = _positive_total("高度", current)
    column_index = _physical_cell_index("門片欄位", column_index, len(columns))
    column = columns[column_index]
    row_index = _physical_cell_index("門片層數", row_index, len(column.heights))
    other_fixed = sum(
        float(value)
        for index, (value, is_auto) in enumerate(zip(column.heights, column.height_auto))
        if index != row_index and not is_auto
    )
    maximum = total_height - other_fixed
    expected = total_height - other_fixed
    keep_auto = bool(column.height_auto[row_index] and abs(current - expected) <= 0.01)
    return DoorLayoutCommitValidation(
        valid=current <= maximum + 0.01,
        maximum=maximum,
        other_fixed=other_fixed,
        keep_auto=keep_auto,
    )


def remap_owned_data(
    source: Mapping[str, object],
    mapper: Callable[[int, int], tuple[int, int] | None],
) -> dict[str, object]:
    remapped = {}
    for key, value in dict(source or {}).items():
        try:
            c_text, r_text = str(key).split(":", 1)
            mapped = mapper(int(c_text), int(r_text))
        except (TypeError, ValueError):
            mapped = None
        if mapped is None:
            continue
        column, row = mapped
        remapped[f"{int(column)}:{int(row)}"] = value
    return remapped
