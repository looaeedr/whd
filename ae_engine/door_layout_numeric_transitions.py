# -*- coding: utf-8 -*-
"""Canonical Engine ownership of Door grid W/H partitions and operator edits.

This is a source-for-source migration of the verified Phase7 A2 application
algorithms. No different tolerance, Fold formula or physical manufacturing
capability is introduced. GUI never owns partition/remainder arithmetic.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Sequence

from .operator_settings_transactions import normalize_operator_settings_boolean
from .sheetmetal_part_adapters import (
    complete_partition,
    validate_door_layout_dimensions,
    door_layout_part_key,
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


def validate_operator_door_grid_edit_index(
    index: object, *, count: object, axis: str,
) -> int:
    """Qualify a live Door column/row edit target before any GUI list lookup.

    The existing Engine _physical_cell_index owns index identity. Callers
    supply only the number of currently present GUI controls, never fabricate
    a DoorLayoutCell from invalid or partially edited draft dimensions.
    """
    labels = {"column": "門片欄位", "row": "門片層數"}
    if axis not in labels:
        raise ValueError("DOOR_LAYOUT_EDIT_AXIS_INVALID")
    if type(count) is not int or count < 0:
        raise ValueError("DOOR_LAYOUT_EDIT_COUNT_INVALID")
    return _physical_cell_index(labels[axis], index, count)


def normalize_operator_door_grid_dimension(raw: object, *, field: str) -> float:
    """Public raw physical dimension validation for a Door cell/box-axis edit."""
    labels = {
        "w": "W", "h": "H",
        "column_width": "欄寬", "row_height": "高度",
    }
    if field not in labels:
        raise ValueError("不支援的門格尺寸來源")
    return _positive_total(labels[field], raw)


def resolve_operator_door_layout_cell(cells, column_index, row_index):
    """Select only an existing canonical physical Door cell; never invent ID."""
    if type(column_index) is not int or type(row_index) is not int or column_index < 0 or row_index < 0:
        raise ValueError("DOOR_LAYOUT_CELL_ID_INVALID")
    matches = []
    for cell in tuple(cells or ()):
        try:
            door_layout_part_key(cell)  # Existing physical identity owner.
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("DOOR_LAYOUT_CELL_SOURCE_INVALID") from exc
        if cell.column_index == column_index and cell.row_index == row_index:
            matches.append(cell)
    if len(matches) != 1:
        raise ValueError("DOOR_LAYOUT_CELL_ID_UNAVAILABLE")
    return matches[0]


def _normalized_auto_columns(columns: Sequence[DoorLayoutColumnState]) -> tuple[DoorLayoutColumnState, ...]:
    """Trust no raw auto/fixed flags before physical Door partitions are built.

    Reuse the original public Settings boolean source contract, so serialized
    "false" remains fixed rather than Python's bool("false") == True.
    Reject any invalid row flags or arity before using zip() or geometry.
    """
    normalized = []
    try:
        source = tuple(columns)
    except (TypeError, ValueError) as exc:
        raise ValueError("DOOR_LAYOUT_AUTO_SOURCE_INVALID") from exc
    for column in source:
        try:
            heights = tuple(column.heights)
            flags = tuple(column.height_auto)
            width_auto = normalize_operator_settings_boolean(column.width_auto)
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValueError("DOOR_LAYOUT_AUTO_SOURCE_INVALID") from exc
        if not heights or len(heights) != len(flags):
            raise ValueError("DOOR_LAYOUT_AUTO_ROWS_MISMATCH")
        try:
            height_auto = tuple(normalize_operator_settings_boolean(flag) for flag in flags)
        except (TypeError, ValueError) as exc:
            raise ValueError("DOOR_LAYOUT_AUTO_SOURCE_INVALID") from exc
        normalized.append(DoorLayoutColumnState(
            width=column.width, width_auto=width_auto,
            heights=heights, height_auto=height_auto,
        ))
    return tuple(normalized)


def recompute_door_layout(
    columns: Sequence[DoorLayoutColumnState],
    *,
    total_width: float,
    total_height: float,
    selected_key: str,
) -> DoorLayoutRecomputeResult:
    columns = _normalized_auto_columns(columns)
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
    columns = _normalized_auto_columns(columns)
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
    columns = _normalized_auto_columns(columns)
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
