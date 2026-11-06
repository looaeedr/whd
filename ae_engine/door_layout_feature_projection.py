# -*- coding: utf-8 -*-
"""Headless Fold Designer Door-grid Feature ownership projection (#2517).

Existing source topology and stable Door part IDs belong to
sheetmetal_part_adapters. This transaction only reconciles the authored
per-cell Feature source with already-saved per-part Feature rows.
"""
from __future__ import annotations

from typing import Mapping

from .sheetmetal_part_adapters import door_layout_feature_map_to_part_features


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
    if not source.get("multi_door_enabled") or not source.get("door_layout_columns"):
        return projected

    authored = dict(door_layout_features or {})
    columns = tuple(
        (float(row[0]), tuple(float(value) for value in row[1]))
        for row in source["door_layout_columns"]
    )
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
