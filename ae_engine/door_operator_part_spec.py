# -*- coding: utf-8 -*-
"""Canonical GUI/worker independent Door operator → physical PartSpec (#2517).

This module does not infer door size, CornerType policy, or manufacturing
approval. The immutable DoorPartSpec retains each operator input and the
historical explicitly authored material Feature coordinate space.
"""
from __future__ import annotations

from collections.abc import Mapping
from math import isfinite

from .contracts import DoorPartSpec
from .fold_designer_snapshot_dimensions import (
    normalize_fold_designer_indicator_groups,
    normalize_fold_designer_indicator_offsets,
)
from .operator_settings_transactions import (
    normalize_operator_settings_boolean,
    normalize_operator_source_dimension,
)
from .sheetmetal_part_adapters import DoorFrameEdges


def _finite_operator_number(raw: object, field: str) -> float:
    """Preserve legacy signed Gap/Fold numbers; reject nonphysical coercions."""
    if isinstance(raw, bool):
        raise ValueError(f"DOOR_OPERATOR_SOURCE_INVALID: {field}")
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"DOOR_OPERATOR_SOURCE_INVALID: {field}") from exc
    if not isfinite(value):
        raise ValueError(f"DOOR_OPERATOR_SOURCE_INVALID: {field}")
    return value


def build_door_operator_part_spec(
    values: Mapping[str, object],
    *,
    model_name: str | None,
    features=(),
    indicator_hole=None,
    door_indicator=None,
    door_indicator_offset=(0.0, 0.0),
    use_box_distance=False,
    corner_policy=None,
    frame_edges=None,
    indicator_window_groups=None,
    nameplate_center_datum_top=None,
) -> DoorPartSpec:
    """Preserve the existing single/multi-Door Save→Export request contract.

    The incoming row is already the selected per-cell operator W/H for a
    multi-door layout, or the single-door W/H. Physical finished-face sizes,
    corner relief, holes and 2D/3D/DXF are downstream Engine-owned resolvers.
    Source validation must occur before a canonical PartSpec is returned:
    bool, NaN and infinity must never enter a physical request.
    """
    physical = {
        key: normalize_operator_source_dimension(values[key], field=key)
        for key in ("w", "h", "t", "fw")
    }
    details = {
        key: _finite_operator_number(values[key], key)
        for key in (
            "door_gap_w", "door_gap_h", "door_fold_l", "door_fold_r",
            "door_fold_t", "door_fold_b",
        )
    }
    # Disabled Indicator controls are not physical manufacturing sources.
    # Their stale Tk/project values must neither fabricate holes nor block a
    # plain Door. Enabled lamp/box opening inputs are always strict.
    if door_indicator is None and indicator_hole is None:
        offsets = (0.0, 0.0)
        distance_mode = False
    else:
        offsets = normalize_fold_designer_indicator_offsets(
            door_indicator_offset[0], door_indicator_offset[1],
        )
        distance_mode = normalize_operator_settings_boolean(use_box_distance)
    opening = (
        None if indicator_hole is None else (
            normalize_operator_source_dimension(
                indicator_hole[0], field="w",
            ),
            normalize_operator_source_dimension(
                indicator_hole[1], field="h",
            ),
        )
    )
    groups = (
        normalize_fold_designer_indicator_groups(indicator_window_groups)
        if indicator_window_groups else None
    )
    indicator = (
        normalize_fold_designer_indicator_groups(door_indicator)
        if door_indicator else None
    )
    nameplate = (
        None if nameplate_center_datum_top is None
        else _finite_operator_number(
            nameplate_center_datum_top, "nameplate_center_datum_top",
        )
    )
    return DoorPartSpec(
        width=physical["w"], height=physical["h"],
        thickness=physical["t"], frame_width=physical["fw"],
        model_name=model_name,
        gap_w=details["door_gap_w"],
        gap_h=details["door_gap_h"],
        fold_left=details["door_fold_l"],
        fold_right=details["door_fold_r"],
        fold_top=details["door_fold_t"],
        fold_bottom=details["door_fold_b"],
        frame_edges=frame_edges or DoorFrameEdges(),
        features=tuple(features or ()),
        feature_space="legacy_unfolded",
        indicator_hole=opening,
        door_indicator=indicator,
        door_indicator_offset=offsets,
        use_box_distance=distance_mode,
        corner_policy=corner_policy,
        indicator_window_groups=groups,
        nameplate_center_datum_top=nameplate,
    )
