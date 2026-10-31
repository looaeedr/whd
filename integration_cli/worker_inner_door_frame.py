# -*- coding: utf-8 -*-
"""W-08: certified Receiving INNER DOOR physical A/B/D frame source to Worker.

A/B/D come from trusted 受電箱/框.dxf, and the only source geometry adapter is
ae_engine.receiving_frame_baseline + inner_door_frames. A single physical
frame is manufactured, not a whole doorway, C divider, NFB or assembly.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from integration_cli.prepare_evidence import PrepareEvidenceError, _pure_json

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
_PHYSICAL = re.compile(r"^whd-[0-9a-f]{24}$")
_FRAME_FIELDS = frozenset({
    "kind", "cabinet_family", "source_part_ref", "dimension_semantics",
    "dimensions_mm", "inner_door_id", "inner_door_frame_side",
    "inner_door_frame_span_mm",
})
_SIDES = frozenset(("left", "right", "top"))


def source_frame_baseline(resource_root: Path) -> Path:
    """Return the exact installed resource path, not an unrelated repo copy."""
    return Path(resource_root) / "基準檔" / "受電箱" / "框.dxf"


def receiving_inner_door_frame_from_trusted_part(part: Mapping[str, Any]):
    from ae_engine.inner_door_frames import derive_inner_door_frames

    if (not isinstance(part, Mapping) or set(part) != _FRAME_FIELDS
            or part.get("kind") != "inner_door"
            or part.get("cabinet_family") != "受電箱"
            or part.get("dimension_semantics") != "part_formed_outer"):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Receiving A/B/D exact physical source required")
    door_id = part.get("inner_door_id")
    side = part.get("inner_door_frame_side")
    if (not isinstance(door_id, str) or _ID.fullmatch(door_id) is None
            or side not in _SIDES
            or part.get("source_part_ref") != f"inner_door:{door_id}:{side}_frame"):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "unconfirmed inner-door frame ID and A/B/D role")
    dims = part.get("dimensions_mm")
    if not isinstance(dims, Mapping) or set(dims) != {"thickness"}:
        raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "independent frame needs material T only")
    thickness = dims["thickness"]
    span = part.get("inner_door_frame_span_mm")
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
           for v in (thickness, span)):
        raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "finite positive thickness and source span required")
    if span <= 110:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Receiving A/B/D frame span too short")
    try:
        (frame,) = derive_inner_door_frames(
            door_id, spans={side: float(span)}, thickness=float(thickness),
            included_sides=(side,),
        )
        if (frame.stable_id != part["source_part_ref"]
                or len(frame.fold_profile) not in (3, 4)
                or len(frame.fold_profile) != (4 if side == "right" else 3)):
            raise ValueError("frame source signed fold topology changed")
        return frame
    except (TypeError, ValueError, ArithmeticError, OverflowError) as exc:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Receiving inner frame Fold authority unavailable") from exc


def _record(side: str, physical: str, width: float, height: float):
    return {
        "frame_id": f"inner_door:{side}:{physical}:receiving:flat:size-only-v1",
        "coordinate_contract_revision": "1", "units": "mm",
        "origin_definition": (
            "WHD Receiving dedicated 框.dxf A/B/D physical "+
            side+" frame source-only CUTTING/BEND envelope; no source-Feature,"
            " C-divider, NFB or parent assembly mapping"
        ),
        "origin_xyz_mm": [0.0, 0.0, 0.0],
        "axis_x": [1.0, 0.0, 0.0], "axis_y": [0.0, 1.0, 0.0],
        "normal": [0.0, 0.0, 1.0],
        "face_role": "outer", "viewed_from": "along_normal",
        "finished_face_dimensions_mm": {"width": width, "height": height},
        "allowed_feature_types": [],
    }


def receiving_inner_door_frame_size_only_frame(
    frame: Any, resource_root: Path, *, physical_part_id: str,
):
    from ae_engine.inner_door_frames import InnerDoorFramePart
    from ae_engine.manufacturing_api import build_inner_door_frame_render_data

    if (not isinstance(frame, InnerDoorFramePart) or frame.side not in _SIDES
            or not isinstance(physical_part_id, str)
            or _PHYSICAL.fullmatch(physical_part_id) is None):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "unverified Receiving A/B/D frame physical identity")
    try:
        render = build_inner_door_frame_render_data(frame, resource_root=resource_root)
        mat = render.material
        if (mat is None or mat.is_empty or not mat.is_valid
                or not render.fold_guides
                or render.metadata.get("receiving_frame_source_tag") != {
                    "left": "A", "right": "B", "top": "D",
                }[frame.side]
                or render.metadata.get("stable_id") != frame.stable_id):
            raise ValueError("source A/B/D frame FinalScene or baseline missing")
        low_x, low_y, high_x, high_y = map(float, mat.bounds)
        width, height = high_x-low_x, high_y-low_y
        if any(not math.isfinite(v) or v <= 0 for v in (width, height, float(mat.area))):
            raise ValueError("source A/B/D material envelope invalid")
    except (OSError, TypeError, ValueError, ArithmeticError, OverflowError) as exc:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Receiving A/B/D source FinalScene cannot be attested") from exc
    return _record(frame.side, physical_part_id, width, height)


def require_receiving_inner_door_frame_size_only_frame(
    target: Any, *, frame_side: str, physical_part_id: str,
):
    if (frame_side not in _SIDES
            or not isinstance(physical_part_id, str)
            or _PHYSICAL.fullmatch(physical_part_id) is None
            or not isinstance(target, Mapping)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "untrusted Receiving inner-frame")
    dimensions = target.get("finished_face_dimensions_mm")
    if not isinstance(dimensions, Mapping) or set(dimensions) != {"width", "height"}:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "untrusted A/B/D unfolded dimensions")
    width, height = dimensions["width"], dimensions["height"]
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
           for v in (width, height)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "invalid A/B/D unfolded extent")
    if _pure_json(target) != _record(frame_side, physical_part_id, float(width), float(height)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Receiving A/B/D Frame was tampered")
