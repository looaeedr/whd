# -*- coding: utf-8 -*-
"""GUI-compatible Door Layout input adapter; numeric authority is Engine.

The existing Phase7 A2 call signatures remain intact. Only per-cell GUI
selection mapping remains here; no size partition or geometry is calculated.
"""
from __future__ import annotations

from typing import Callable, Mapping, Sequence
from ae_engine.manufacturing_api import (
    DoorLayoutColumnState, DoorLayoutResolvedColumn,
    DoorLayoutRecomputeResult, DoorLayoutCommitValidation,
)
from ae_engine import manufacturing_api


def recompute_door_layout(
    columns: Sequence[DoorLayoutColumnState], *,
    total_width: float, total_height: float, selected_key: str,
) -> DoorLayoutRecomputeResult:
    return manufacturing_api.recompute_door_layout(
        columns, total_width=total_width, total_height=total_height,
        selected_key=selected_key,
    )


def door_layout_cells(columns, *, total_width: float, total_height: float):
    return manufacturing_api.door_layout_cells(
        columns, total_width=total_width, total_height=total_height,
    )


def validate_width_commit(
    columns: Sequence[DoorLayoutColumnState],
    column_index: int, total_width: float, current: float,
) -> DoorLayoutCommitValidation:
    return manufacturing_api.validate_door_layout_width_commit(
        columns, column_index, total_width, current,
    )


def validate_height_commit(
    columns: Sequence[DoorLayoutColumnState],
    column_index: int, row_index: int, total_height: float, current: float,
) -> DoorLayoutCommitValidation:
    return manufacturing_api.validate_door_layout_height_commit(
        columns, column_index, row_index, total_height, current,
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
