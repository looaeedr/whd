# -*- coding: utf-8 -*-
"""Headless Fold Designer snapshot physical dimension projection (#2517).

The GUI supplies operator controls only.  Canonical Door/Receiving Base Plate
and shared Indicator material dimensions are read from existing Engine owners;
this module does not introduce independent manufacturing geometry.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math
import re
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


def normalize_fold_designer_indicator_groups(
    values: Sequence[object],
) -> tuple[int, ...]:
    """Validate an enabled Indicator Box/Door layout without source substitution.

    In particular int(1.5), int(True) and int("0") are not valid numbers of
    physical lamp groups. This remains the same Engine validation path for
    snapshot save, preview and the independent Door indicator source.
    """
    result = []
    for raw in values:
        if isinstance(raw, bool):
            raise ValueError("指示燈層數／組數必須是大於 0 的整數")
        if isinstance(raw, str):
            label = raw.strip()
            if not re.fullmatch(r"[+]?[0-9]+", label):
                raise ValueError("指示燈層數／組數必須是大於 0 的整數")
            parsed = int(label)
        elif isinstance(raw, int):
            parsed = raw
        elif isinstance(raw, float) and math.isfinite(raw) and raw.is_integer():
            parsed = int(raw)
        else:
            raise ValueError("指示燈層數／組數必須是大於 0 的整數")
        if parsed <= 0:
            raise ValueError("指示燈層數／組數必須是大於 0 的整數")
        result.append(parsed)
    if not result:
        raise ValueError("指示燈至少需要一層且組數必須大於 0")
    return tuple(result)


def _require_positive_source_length(raw: object, field: str) -> float:
    if isinstance(raw, bool):
        raise ValueError(f"{field} 必須是正數有限的物理尺寸")
    try:
        result = float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{field} 必須是正數有限的物理尺寸") from exc
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{field} 必須是正數有限的物理尺寸")
    return result


def project_fold_designer_snapshot_dimensions(
    snapshot: Mapping[str, object], indicator_layer_groups: Sequence[object],
) -> FoldDesignerSnapshotDimensions:
    """Preserve the existing original Fold Designer snapshot dimension semantics.

    This is a root overview for single parts; the separately authoritative
    multi-door/cell projection remains project_part_dimensions. It must NOT
    silently turn this legacy root 'door' key into per-cell physical IDs.
    """
    source = dict(snapshot)
    groups = normalize_fold_designer_indicator_groups(indicator_layer_groups)
    w, h, d, t, fw = (
        _require_positive_source_length(source[key], key.upper())
        for key in ("w", "h", "d", "t", "fw")
    )
    door_material_fw = cabinet_family_policy.door_material_frame_width(
        source.get("model"), frame_width=float(fw), thickness=float(t),
    )
    door_w, door_h = ae.calculate_door_finished_size(
        w, h, door_material_fw,
        source["door_gap_w"], source["door_gap_h"], t,
        frame_edges=DoorFrameEdges(),
    )
    door_w = _require_positive_source_length(door_w, "門板成品寬")
    door_h = _require_positive_source_length(door_h, "門板成品高")
    base_w = (
        w - source["base_plate_shrink_left"] - source["base_plate_shrink_right"]
    )
    base_h = (
        h - source["base_plate_shrink_top"] - source["base_plate_shrink_bottom"]
    )
    if source.get("model") in {"受電箱", "RECEIVING"}:
        from .receiving_base_plate_config import receiving_base_plate_blank_dimensions
        physical = receiving_base_plate_blank_dimensions(source)
        if physical is not None:
            base_w, base_h = physical
    base_w = _require_positive_source_length(base_w, "底板成品寬")
    base_h = _require_positive_source_length(base_h, "底板成品高")

    # Missing, malformed or contradictory manufacturing policy cannot
    # become a valid-looking default 1-layer Indicator in a saved snapshot.
    policy = replace(
        resolve_policy(),
        frame_width=fw,
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
    ib_w = _require_positive_source_length(ib_w, "指示燈盒展開寬")
    ib_h = _require_positive_source_length(ib_h, "指示燈盒展開高")
    id_w = _require_positive_source_length(id_w, "指示燈小門展開寬")
    id_h = _require_positive_source_length(id_h, "指示燈小門展開高")

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
