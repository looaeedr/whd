# -*- coding: utf-8 -*-
"""#2383: independently specified custom single-axis physical Fold for both families.

No manufacturing formula is reimplemented here. AE's CustomFoldPartSpec,
custom_fold_manufacturing and FinalScene remain the sole geometry authorities.
The only prepared Frame is the already-built unfolded blank's size envelope;
it does not map original CADSplit features or imply assembly placement.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any

from integration_cli.prepare_evidence import PrepareEvidenceError, _pure_json

_CUSTOM_ID = re.compile(r"^custom:[1-9][0-9]*$")
_PHYSICAL_ID = re.compile(r"^whd-[0-9a-f]{24}$")


def custom_fold_spec_from_trusted_prepared_part(part: Mapping[str, Any]):
    from ae_engine.contracts import CustomFoldPartSpec, FoldProfileSegment
    from ae_engine.custom_fold_manufacturing import _validate

    if (part.get("kind") != "custom_fold"
            or part.get("cabinet_family") not in ("金庫型", "受電箱")
            or part.get("dimension_semantics") != "part_formed_outer"
            or not isinstance(part.get("source_part_ref"), str)
            or _CUSTOM_ID.fullmatch(part["source_part_ref"]) is None):
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "registered standalone custom physical part required"
        )
    if any(field in part for field in (
        "frame_edges", "frame_width_mm", "gap_w_mm", "gap_h_mm",
        "fold_left_mm", "fold_right_mm", "fold_top_mm", "fold_bottom_mm",
        "indicator_groups", "shrink_top_mm", "shrink_bottom_mm",
        "shrink_left_mm", "shrink_right_mm", "bend_mm",
    )):
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "unsupported custom Fold or assembly overrides"
        )
    dims = part.get("dimensions_mm")
    if not isinstance(dims, Mapping) or set(dims) != {"thickness"}:
        raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "exact custom Fold thickness required")
    thickness = dims["thickness"]
    transverse = part.get("transverse_length_mm")
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
           for v in (thickness, transverse)):
        raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "positive custom Fold material inputs required")
    axis = part.get("fold_axis")
    profiles = part.get("fold_profile")
    if axis not in ("X", "Y") or not isinstance(profiles, list) or not 2 <= len(profiles) <= 64:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "bounded independent single-axis Fold required")
    segments = []
    for row in profiles:
        if not isinstance(row, Mapping):
            raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "invalid Fold profile row")
        if not {"length_mm", "angle_deg"} <= set(row) or set(row) - {
            "length_mm", "angle_deg", "core", "phase6_key", "formed_length_mm"
        }:
            raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "complete Fold material row required")
        length, angle = row["length_mm"], row["angle_deg"]
        if (type(length) not in (int, float) or not math.isfinite(length) or length <= 0
                or angle is not None and (
                    type(angle) not in (int, float) or not math.isfinite(angle)
                )):
            raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "invalid Fold material length or angle")
        formed = row.get("formed_length_mm")
        if formed is not None and (
                type(formed) not in (int, float) or not math.isfinite(formed)
                or formed <= 0):
            raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "invalid Fold formed length")
        if any(value is not None and (not isinstance(value, str) or not value.strip() or len(value) > 128)
               for value in (row.get("core"), row.get("phase6_key"))):
            raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "invalid Fold semantic key")
        segments.append(FoldProfileSegment(
            length=float(length), angle=float(angle) if angle is not None else None,
            core=row.get("core"), phase6_key=row.get("phase6_key"),
            formed_length=float(formed) if formed is not None else None,
        ))
    spec = CustomFoldPartSpec(
        physical_id=part["source_part_ref"], fold_axis=axis,
        fold_profile=tuple(segments), transverse_length=float(transverse),
        thickness=float(thickness),
    )
    try:
        _validate(spec)
    except (TypeError, ValueError, OverflowError, ArithmeticError) as exc:
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "AE rejected custom Fold profile or bend topology"
        ) from exc
    return spec


def _custom_size_only_record(width: float, height: float, physical_part_id: str) -> dict[str, Any]:
    return {
        "frame_id": f"custom_fold:{physical_part_id}:flat:size-only-v1",
        "coordinate_contract_revision": "1",
        "units": "mm",
        "origin_definition": (
            "WHD custom Fold standalone unfolded Final Material envelope size only; "
            "no certified CADSplit source Feature or assembly-world mapping"
        ),
        "origin_xyz_mm": [0.0, 0.0, 0.0],
        "axis_x": [1.0, 0.0, 0.0],
        "axis_y": [0.0, 1.0, 0.0],
        "normal": [0.0, 0.0, 1.0],
        "face_role": "outer",
        "viewed_from": "along_normal",
        "finished_face_dimensions_mm": {"width": width, "height": height},
        "allowed_feature_types": [],
    }


def resolve_custom_fold_size_only_frame(spec: Any, context: Any, *, physical_part_id: str):
    from ae_engine.contracts import CustomFoldPartSpec
    from ae_engine.manufacturing_api import build_part_render_data

    if (not isinstance(spec, CustomFoldPartSpec)
            or not isinstance(physical_part_id, str)
            or _PHYSICAL_ID.fullmatch(physical_part_id) is None):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "custom Fold physical identity required")
    try:
        render = build_part_render_data(spec, context)
        material = render.material
        if material is None or material.is_empty or not material.is_valid:
            raise ValueError("custom Fold has no valid material")
        min_x, min_y, max_x, max_y = map(float, material.bounds)
        width, height = max_x - min_x, max_y - min_y
        if any(not math.isfinite(n) or n <= 0 for n in (width, height, float(material.area))):
            raise ValueError("invalid unfolded custom Fold dimensions")
    except (TypeError, ValueError, ArithmeticError, OverflowError) as exc:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "custom Fold Final Material unverified") from exc
    return _custom_size_only_record(width, height, physical_part_id)


def require_canonical_custom_fold_size_only_frame(frame: Any, *, physical_part_id: str) -> None:
    if (not isinstance(physical_part_id, str) or _PHYSICAL_ID.fullmatch(physical_part_id) is None
            or not isinstance(frame, Mapping)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "untrusted custom Fold frame")
    dims = frame.get("finished_face_dimensions_mm")
    if not isinstance(dims, Mapping) or set(dims) != {"width", "height"}:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "unverified custom Fold envelope")
    width, height = dims["width"], dims["height"]
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
           for v in (width, height)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "invalid custom Fold Frame envelope")
    if _pure_json(frame) != _custom_size_only_record(float(width), float(height), physical_part_id):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "custom Fold Frame was forged")
