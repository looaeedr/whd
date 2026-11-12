# -*- coding: utf-8 -*-
"""Headless Fold Designer Door-grid Feature ownership projection (#2517).

Existing source topology and stable Door part IDs belong to
sheetmetal_part_adapters. This transaction only reconciles the authored
per-cell Feature source with already-saved per-part Feature rows.
"""
from __future__ import annotations

from typing import Mapping

from .operator_settings_transactions import normalize_operator_settings_boolean
from .sheetmetal_part_adapters import (
    door_layout_feature_map_to_part_features,
    derive_door_layout_cells,
)


def project_operator_saved_door_layout_columns(columns: object) -> list[list]:
    """Detach validated physical Door-grid columns for a .p6fold snapshot.

    The original Engine cell resolver owns finite positive W/H and row
    topology; there is no GUI-side float coercion, rounding or second part-ID
    algorithm. A missing/empty grid stays empty for legacy single-Door saves.
    """
    if columns is None:
        return []
    if not isinstance(columns, (list, tuple)):
        raise ValueError("door layout source must be a sequence of columns")
    if not columns:
        return []
    for row in columns:
        if (not isinstance(row, (list, tuple)) or len(row) != 2
                or not isinstance(row[1], (list, tuple))):
            raise ValueError("door layout column must be (width, heights)")
    cells = derive_door_layout_cells(columns)
    projected: list[list] = []
    for cell in cells:
        if cell.row_index == 0:
            projected.append([float(cell.start_width), []])
        projected[-1][1].append(float(cell.start_height))
    return projected



def project_fold_designer_snapshot_part_features(
    snapshot: Mapping[str, object],
    surface_features: Mapping[object, object] | None,
    door_layout_features: Mapping[object, object] | None,
) -> dict[str, list]:
    """Detach committed Feature stores and preserve historical empty-write rules.

    An authored empty cell *clears* its old physical part Features. An absent
    cell keeps existing saved Features even when the live grid presents it as
    empty; that distinction is required for preexisting project Save/Reload.
    Both legacy tuple cell keys and the canonical `col:row` keys are honored
    for this empty-write decision; the existing formal Feature projector
    remains the authority for nonempty values.
    """
    source = dict(snapshot or {})
    projected = {
        str(key): list(features or ())
        for key, features in dict(surface_features or {}).items()
    }
    # A persisted 'false' is disabled, not a truthy instruction to publish
    # stale per-cell physical holes. Invalid serialized flags fail closed via
    # the same public Engine source validator as GUI Save→Reload.
    multi_door_enabled = normalize_operator_settings_boolean(
        source.get("multi_door_enabled", False)
    )
    if not multi_door_enabled:
        return projected

    # A true multi-door mode must consume only strictly validated W/H cell
    # sources. Never let float(True) become a manufactured 1 mm Door row.
    columns = project_operator_saved_door_layout_columns(
        source.get("door_layout_columns"),
    )
    if not columns:
        return projected
    authored = dict(door_layout_features or {})
    formal = door_layout_feature_map_to_part_features(columns, authored)
    for key, features in formal.items():
        if features or key not in projected:
            projected[key] = list(features)
        else:
            tokens = str(key).removeprefix("door_c").split("_r")
            if len(tokens) == 2 and tokens[0].isdigit() and tokens[1].isdigit():
                cell = (int(tokens[0]) - 1, int(tokens[1]) - 1)
                if cell in authored or f"{cell[0]}:{cell[1]}" in authored:
                    projected[key] = list(features)
    return projected
