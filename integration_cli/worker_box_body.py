# -*- coding: utf-8 -*-
"""#2383: Vault *integral* canonical BoxBody manufacturable part-only Worker route.

WHD Phase6 owns D-W-D outside→material Fold conversion, AE owns final sheet,
baseline holes, corner/relief and saved DXF. This boundary takes only explicit
cabinet dimensions/factory strip scalar settings; no arbitrary Fold/Joint,
source features, multipart structure or inferred physical assembly.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any

from integration_cli.prepare_evidence import PrepareEvidenceError, _pure_json

_PHYSICAL_ID = re.compile(r"^whd-[0-9a-f]{24}$")

_FACTORY_BOX_SCALARS = (
    ("zl1", "box_zl1_mm"), ("zl2", "box_zl2_mm"),
    ("zr1", "box_zr1_mm"), ("zr2", "box_zr2_mm"), ("z_comp", "box_z_comp_mm"),
)


def vault_box_body_spec_from_trusted_prepared_part(part: Mapping[str, Any]):
    from ae_engine.contracts import BoxBodyPartSpec
    from phase6_fold_profiles import build_box_body_profile, profile_to_fold_segments

    if (part.get("kind") != "box_body"
            or part.get("cabinet_family") != "金庫型"
            or part.get("dimension_semantics") != "cabinet_outer"):
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "only Vault cabinet-outer integral BoxBody certified"
        )
    if any(key in part for key in (
        "frame_edges", "gap_w_mm", "gap_h_mm", "fold_left_mm",
        "fold_right_mm", "fold_top_mm", "fold_bottom_mm",
        "indicator_groups", "shrink_top_mm", "shrink_bottom_mm",
        "shrink_left_mm", "shrink_right_mm", "bend_mm",
        "fold_profile", "fold_axis", "transverse_length_mm",
    )):
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "multipart, manual Fold or Door overrides not certified"
        )
    dims = part.get("dimensions_mm")
    fw = part.get("frame_width_mm")
    if (not isinstance(dims, Mapping)
            or set(dims) != {"width", "height", "depth", "thickness"}):
        raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "explicit BoxBody W/H/D/T required")
    numbers = [dims[x] for x in ("width", "height", "depth", "thickness")] + [fw]
    for _, wire in _FACTORY_BOX_SCALARS:
        if wire not in part:
            raise PrepareEvidenceError(
                "WHD_PREPARE_INPUT_INVALID", "explicit signed Vault BoxBody factory Fold scalar missing"
            )
        numbers.append(part[wire])
    if any(type(v) not in (float, int) or not math.isfinite(v) for v in numbers):
        raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "nonfinite/bool BoxBody manufacturing input")
    w, h, d, t, frame_width = map(float, numbers[:5])
    if (min(w, h, d, t, frame_width) <= 0
            or w <= 4 * t or d <= 4 * t or h <= 2 * t
            or frame_width >= min(w, d)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Vault BoxBody W/H/D/FW impossible")
    settings = {
        "model": "金庫型", "w": w, "h": h, "d": d,
        "t": t, "fw": frame_width,
    }
    for name, wire in _FACTORY_BOX_SCALARS:
        settings[name] = float(part[wire])
    try:
        rows = build_box_body_profile(settings)
        if not rows or len(rows) != 9:
            raise ValueError("Vault canonical 9-segment D-W-D profile missing")
        if tuple(str(row.get("phase6_key")) for row in rows) != (
            "zl1", "zl2", "fw_left", "d_left", "w", "d_right",
            "fw_right", "zr2", "zr1",
        ):
            raise ValueError("unrecognized Vault factory Fold source topology")
        if any(not math.isfinite(float(row.get("len", 0)))
               or float(row.get("len", 0)) <= 0 for row in rows):
            raise ValueError("invalid Vault canonical Fold material segment")
        folded = profile_to_fold_segments(rows)
    except (TypeError, ValueError, OverflowError, ArithmeticError) as exc:
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "WHD Vault BoxBody Fold conversion refused"
        ) from exc
    return BoxBodyPartSpec(
        width=w, height=h, depth=d, thickness=t, frame_width=frame_width,
        model_name="金庫型", zl1=settings["zl1"], zl2=settings["zl2"],
        zr1=settings["zr1"], zr2=settings["zr2"], z_comp=settings["z_comp"],
        fold_profile=folded,
    )


def _box_size_only_record(width: float, height: float, physical_part_id: str) -> dict[str, Any]:
    return {
        "frame_id": f"box_body:{physical_part_id}:flat:size-only-v1",
        "coordinate_contract_revision": "1",
        "units": "mm",
        "origin_definition": (
            "WHD Vault integral BoxBody standalone unfolded Final Material envelope size only; "
            "no certified CADSplit source Feature, manual Fold or assembly-world mapping"
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


def resolve_vault_box_body_size_only_frame(spec: Any, context: Any, *, physical_part_id: str):
    from ae_engine.contracts import BoxBodyPartSpec
    from ae_engine.manufacturing_api import build_part_render_data

    if (not isinstance(spec, BoxBodyPartSpec)
            or spec.model_name != "金庫型"
            or bool(spec.structure_state) or bool(spec.back_panel_contract)
            or bool(spec.physical_piece_features) or bool(spec.face_features)
            or bool(spec.features)
            or not isinstance(physical_part_id, str)
            or _PHYSICAL_ID.fullmatch(physical_part_id) is None):
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "unverified Vault integral physical BoxBody"
        )
    try:
        render = build_part_render_data(spec, context)
        material = render.material
        if material is None or material.is_empty or not material.is_valid:
            raise ValueError("BoxBody has no verified Final Material")
        min_x, min_y, max_x, max_y = map(float, material.bounds)
        width, height = max_x - min_x, max_y - min_y
        if (any(not math.isfinite(v) or v <= 0 for v in (
                width, height, float(material.area)))
                or not render.fold_guides):
            raise ValueError("invalid Vault BoxBody CUTTING/BEND")
    except (TypeError, ValueError, OverflowError, ArithmeticError) as exc:
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "Vault BoxBody canonical FinalScene cannot be verified"
        ) from exc
    return _box_size_only_record(width, height, physical_part_id)


def require_canonical_vault_box_body_size_only_frame(frame: Any, *, physical_part_id: str):
    if (not isinstance(physical_part_id, str)
            or _PHYSICAL_ID.fullmatch(physical_part_id) is None
            or not isinstance(frame, Mapping)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "untrusted Vault BoxBody frame")
    dims = frame.get("finished_face_dimensions_mm")
    if not isinstance(dims, Mapping) or set(dims) != {"width", "height"}:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Vault BoxBody bounds missing")
    width, height = dims["width"], dims["height"]
    if any(type(v) not in (float, int) or not math.isfinite(v) or v <= 0
           for v in (width, height)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "invalid Vault BoxBody Frame")
    if _pure_json(frame) != _box_size_only_record(float(width), float(height), physical_part_id):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "forged Vault BoxBody Frame")
