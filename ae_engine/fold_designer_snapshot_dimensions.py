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


def normalize_operator_hole_editor_indicator_state(raw: Mapping[str, object]) -> dict[str, object]:
    """Validate CURRENT live Indicator controls before any physical hole commit.

    Persisted saved-state repair is a separate compatibility operation. A live
    enabled hole source may never fabricate the layer count, lamp groups or
    offsets when a Tk read is invalid; all GUI consumers share this Engine gate.
    """
    if not isinstance(raw, Mapping):
        raise ValueError("指示燈即時輸入必須是明確的操作資料")
    mode = raw.get("mode")
    if mode == "none":
        # Disabled controls have no physical geometry; their unused fields need
        # not be valid in order to switch the Indicator off.
        return dict(mode="none", layers=1, groups=[2] * 6,
                    offset_x=0.0, offset_y=0.0, is_box_dist=False)
    if mode not in ("indicator", "indicator_box"):
        raise ValueError("指示燈模式無效")
    layers = normalize_fold_designer_indicator_groups((raw.get("layers"),))[0]
    if layers > 6:
        raise ValueError("指示燈層數／組數無效：最多六層")
    group_source = raw.get("groups")
    if not isinstance(group_source, (tuple, list)) or len(group_source) < layers:
        raise ValueError("指示燈層數／組數無效：缺少實際組數")
    groups = normalize_fold_designer_indicator_groups(group_source[:layers])
    if any(group > 8 for group in groups):
        raise ValueError("指示燈層數／組數無效：單層最多八組")

    def finite_offset(key: str) -> float:
        source = raw.get(key)
        if isinstance(source, bool):
            raise ValueError(f"指示燈 {key} 偏移必須是有限數字")
        try:
            value = float(source)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"指示燈 {key} 偏移必須是有限數字") from exc
        if not math.isfinite(value):
            raise ValueError(f"指示燈 {key} 偏移必須是有限數字")
        return value

    flag = raw.get("is_box_dist")
    if isinstance(flag, bool):
        is_box_dist = flag
    elif type(flag) is int and flag in (0, 1):
        is_box_dist = bool(flag)
    elif isinstance(flag, str) and flag.strip().lower() in ("true", "false", "1", "0"):
        is_box_dist = flag.strip().lower() in ("true", "1")
    else:
        raise ValueError("指示燈箱距設定無效")
    return dict(mode=mode, layers=layers, groups=list(groups) + [2] * (6 - layers),
                offset_x=finite_offset("offset_x"), offset_y=finite_offset("offset_y"),
                is_box_dist=is_box_dist)


def project_operator_door_cell_indicator_manufacturing_source(raw):
    """Validate saved Door-cell indicator inputs before creating physical holes.

    Legacy enabled/box_enabled flags select only the mode; they never supply
    a missing physical layer/group. Disabled old cells remain valid plain doors.
    Active holes use the same strict Engine source gate as the Hole Editor.
    """
    if raw is None:
        return normalize_operator_hole_editor_indicator_state({"mode": "none"})
    if not isinstance(raw, Mapping):
        raise ValueError("門格指示燈製造來源必須是有效物件")
    mode = raw.get("mode")
    if mode not in ("none", "indicator", "indicator_box"):
        # Old saved cells may have only explicit enabled flags. Preserve that
        # legacy identity, but never repair the physical groups or dimensions.
        def legacy_flag(key):
            value = raw.get(key, False)
            if isinstance(value, bool):
                return value
            if type(value) is int and value in (0, 1):
                return bool(value)
            if isinstance(value, str):
                normalized = value.strip().lower()
                if normalized in ("1", "true", "yes", "on"):
                    return True
                if normalized in ("0", "false", "no", "off", ""):
                    return False
            raise ValueError("門格指示燈啟用來源無效")
        box_enabled = legacy_flag("box_enabled")
        direct_enabled = legacy_flag("enabled")
        if box_enabled and direct_enabled:
            raise ValueError("門格指示燈互斥模式來源無效")
        mode = ("indicator_box" if box_enabled else
                "indicator" if direct_enabled else "none")
    return normalize_operator_hole_editor_indicator_state({
        "mode": mode,
        "layers": raw.get("layers"),
        "groups": raw.get("groups"),
        # Old saved offsets defaulted to zero on missing keys, never on bad
        # present data. Their physical meaning stays Engine validated.
        "offset_x": raw.get("offset_x", 0.0),
        "offset_y": raw.get("offset_y", 0.0),
        "is_box_dist": raw.get("is_box_dist", False),
    })


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
