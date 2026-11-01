# -*- coding: utf-8 -*-
"""Canonical GUI/worker independent Door operator → physical PartSpec (#2517).

This module does not infer door size, CornerType policy, or manufacturing
approval. The immutable DoorPartSpec retains each operator input and the
historical explicitly authored material Feature coordinate space.
"""
from __future__ import annotations

from collections.abc import Mapping

from .contracts import DoorPartSpec
from .sheetmetal_part_adapters import DoorFrameEdges


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
    """
    return DoorPartSpec(
        width=float(values["w"]), height=float(values["h"]),
        thickness=float(values["t"]), frame_width=float(values["fw"]),
        model_name=model_name,
        gap_w=float(values["door_gap_w"]),
        gap_h=float(values["door_gap_h"]),
        fold_left=float(values["door_fold_l"]),
        fold_right=float(values["door_fold_r"]),
        fold_top=float(values["door_fold_t"]),
        fold_bottom=float(values["door_fold_b"]),
        frame_edges=frame_edges or DoorFrameEdges(),
        features=tuple(features or ()),
        feature_space="legacy_unfolded",
        indicator_hole=indicator_hole,
        door_indicator=tuple(door_indicator) if door_indicator else None,
        door_indicator_offset=(
            float(door_indicator_offset[0]), float(door_indicator_offset[1]),
        ),
        use_box_distance=bool(use_box_distance),
        corner_policy=corner_policy,
        indicator_window_groups=(
            tuple(indicator_window_groups) if indicator_window_groups else None
        ),
        nameplate_center_datum_top=(
            None if nameplate_center_datum_top is None
            else float(nameplate_center_datum_top)
        ),
    )
