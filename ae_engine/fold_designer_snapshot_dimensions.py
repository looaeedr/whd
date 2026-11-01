# -*- coding: utf-8 -*-
"""Headless Fold Designer snapshot physical dimension projection (#2517).

The GUI supplies operator controls only.  Canonical Door/Receiving Base Plate
and shared Indicator material dimensions are read from existing Engine owners;
this module does not introduce independent manufacturing geometry.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping, Sequence

from . import ae
from .cabinet_types import policy as cabinet_family_policy
from .contracts import ManufacturingContext
from .manufacturing_baseline_policy import resolve_policy
from .manufacturing_door_indicator import (
    indicator_box_unfolded_size, indicator_small_door_unfolded_size,
)
from .sheetmetal_part_adapters import DoorFrameEdges


@dataclass(frozen=True)
class FoldDesignerSnapshotDimensions:
    part_dimensions: dict[str, dict[str, float]]
    indicator_layer_groups: tuple[int, ...]


def project_fold_designer_snapshot_dimensions(
    snapshot: Mapping[str, object], indicator_layer_groups: Sequence[object],
) -> FoldDesignerSnapshotDimensions:
    """Preserve the existing original Fold Designer snapshot dimension semantics.

    This is a root overview for single parts; the separately authoritative
    multi-door/cell projection remains project_part_dimensions. It must NOT
    silently turn this legacy root 'door' key into per-cell physical IDs.
    """
    source = dict(snapshot)
    w, h, d, t, fw = (
        source["w"], source["h"], source["d"], source["t"], source["fw"]
    )
    door_material_fw = cabinet_family_policy.door_material_frame_width(
        source.get("model"), frame_width=float(fw), thickness=float(t),
    )
    door_w, door_h = ae.calculate_door_finished_size(
        w, h, door_material_fw,
        source["door_gap_w"], source["door_gap_h"], t,
        frame_edges=DoorFrameEdges(),
    )
    door_w, door_h = max(1.0, float(door_w)), max(1.0, float(door_h))
    base_w = max(
        1.0,
        w - source["base_plate_shrink_left"] - source["base_plate_shrink_right"],
    )
    base_h = max(
        1.0,
        h - source["base_plate_shrink_top"] - source["base_plate_shrink_bottom"],
    )
    if source.get("model") in {"受電箱", "RECEIVING"}:
        from .receiving_base_plate_config import receiving_base_plate_blank_dimensions
        physical = receiving_base_plate_blank_dimensions(source)
        if physical is not None:
            base_w, base_h = physical

    # Retain the original GUI's fail-open presentation fallback for corrupt
    # Indicator group/policy source. The returned preview is not DXF approval.
    try:
        groups = tuple(int(v) for v in indicator_layer_groups)
        policy = replace(
            resolve_policy(),
            frame_width=float(fw),
            door_gap_w=float(source["door_gap_w"]),
            door_gap_h=float(source["door_gap_h"]),
            indicator_box_fold=float(source["indicator_box_fold"]),
            indicator_small_door_fold=float(source["indicator_door_fold"]),
        )
        context = ManufacturingContext(policy=policy)
        ib_w, ib_h = indicator_box_unfolded_size(
            groups, thickness=t, context=context,
        )
        id_w, id_h = indicator_small_door_unfolded_size(
            groups, thickness=t, context=context,
        )
    except Exception:
        groups = (1,)
        context = ManufacturingContext()
        ib_w, ib_h = indicator_box_unfolded_size(
            groups, thickness=t, context=context,
        )
        id_w, id_h = indicator_small_door_unfolded_size(
            groups, thickness=t, context=context,
        )

    dimensions = {
        "box_body": {"width": w, "height": h},
        "head": {"width": w, "height": d},
        "tail": {"width": w, "height": d},
        "door": {"width": door_w, "height": door_h},
        "base_plate": {"width": base_w, "height": base_h},
        "indicator_box": {"width": ib_w, "height": ib_h},
        "indicator_door": {"width": id_w, "height": id_h},
    }
    return FoldDesignerSnapshotDimensions(dimensions, groups)
