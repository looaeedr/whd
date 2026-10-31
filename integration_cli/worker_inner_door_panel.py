# -*- coding: utf-8 -*-
"""#2383 Receiving one independently owned inner-door *panel* manufacturing API.

Uses the existing physical InnerDoorPanelPart and AE canonical FinalScene.
No inner-door frame set, NFB cutout, source DXF feature transform, mounting
joint, assembly or production-ready claim for those separate roles.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any

from integration_cli.prepare_evidence import PrepareEvidenceError, _pure_json

_PHYSICAL_ID = re.compile(r"^whd-[0-9a-f]{24}$")
_INNER_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
_CELL_KEY = re.compile(r"^[0-9]+:[0-9]+$")
_FORBIDDEN = frozenset((
    "frame_edges", "frame_width_mm", "gap_w_mm", "gap_h_mm",
    "fold_left_mm", "fold_right_mm", "fold_top_mm", "fold_bottom_mm",
    "indicator_groups", "shrink_top_mm", "shrink_bottom_mm",
    "shrink_left_mm", "shrink_right_mm", "bend_mm", "fold_axis",
    "fold_profile", "transverse_length_mm", "box_zl1_mm", "box_zl2_mm",
    "box_zr1_mm", "box_zr2_mm", "box_z_comp_mm",
))


def receiving_inner_door_panel_from_trusted_part(part: Mapping[str, Any]):
    from ae_engine.inner_door_panels import derive_inner_door_panel

    if (not isinstance(part, Mapping)
            or part.get("kind") != "inner_door"
            or part.get("cabinet_family") != "受電箱"
            or part.get("dimension_semantics") != "part_formed_outer"
            or any(key in part for key in _FORBIDDEN)):
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "only source-owned Receiving standalone inner-door panel supported"
        )
    door_id = part.get("inner_door_id")
    cell_key = part.get("inner_door_cell_key")
    if (not isinstance(door_id, str) or _INNER_ID.fullmatch(door_id) is None
            or not isinstance(cell_key, str) or _CELL_KEY.fullmatch(cell_key) is None):
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "explicit saved inner-door ID and grid cell are required"
        )
    source_id = f"inner_door:{door_id}:panel"
    if part.get("source_part_ref") != source_id:
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "inner-door source ID differs from physical panel identity"
        )
    dims = part.get("dimensions_mm")
    if not isinstance(dims, Mapping) or set(dims) != {"width", "height", "thickness"}:
        raise PrepareEvidenceError(
            "WHD_PREPARE_INPUT_INVALID", "inner-door finished W/H and material T required"
        )
    if any(type(v) not in (float, int) or not math.isfinite(v) or v <= 0
           for v in dims.values()):
        raise PrepareEvidenceError(
            "WHD_PREPARE_INPUT_INVALID", "invalid inner-door finished physical dimensions"
        )
    try:
        return derive_inner_door_panel(
            door_id, cell_key=cell_key,
            width=dims["width"], height=dims["height"],
            thickness=dims["thickness"],
        )
    except (TypeError, ValueError, ArithmeticError, OverflowError) as exc:
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "AE rejected Receiving canonical inner-door panel geometry"
        ) from exc


def _frame_record(width: float, height: float, physical_id: str) -> dict[str, Any]:
    return {
        "frame_id": f"inner_door:{physical_id}:flat:size-only-v1",
        "coordinate_contract_revision": "1",
        "units": "mm",
        "origin_definition": (
            "WHD Receiving one physical inner-door PANEL unfolded Final Material; "
            "size-only, no certified source Feature or NFB cutout, frame set, "
            "assembly-world placement or adjacent panel transfer"
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


def resolve_receiving_inner_door_panel_frame(
    panel: Any, *, physical_part_id: str,
) -> dict[str, Any]:
    from ae_engine.inner_door_panels import InnerDoorPanelPart
    from ae_engine.manufacturing_api import build_inner_door_panel_render_data

    if (not isinstance(panel, InnerDoorPanelPart)
            or not isinstance(physical_part_id, str)
            or _PHYSICAL_ID.fullmatch(physical_part_id) is None):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "inner-door panel physical identity invalid")
    try:
        render = build_inner_door_panel_render_data(panel)
        material = render.material
        if material is None or material.is_empty or not material.is_valid or not render.fold_guides:
            raise ValueError("inner-door FinalScene CUTTING/BEND absent")
        low_x, low_y, high_x, high_y = map(float, material.bounds)
        width, height = high_x - low_x, high_y - low_y
        if any(not math.isfinite(v) or v <= 0
               for v in (width, height, float(material.area))):
            raise ValueError("inner-door FinalScene material bounds invalid")
    except (TypeError, ValueError, ArithmeticError, OverflowError) as exc:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "AE inner-door Final Material unavailable") from exc
    return _frame_record(width, height, physical_part_id)


def require_canonical_receiving_inner_door_panel_frame(frame: Any, *, physical_part_id: str):
    if (not isinstance(frame, Mapping)
            or not isinstance(physical_part_id, str)
            or _PHYSICAL_ID.fullmatch(physical_part_id) is None):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "untrusted inner-door panel Frame")
    dims = frame.get("finished_face_dimensions_mm")
    if not isinstance(dims, Mapping) or set(dims) != {"width", "height"}:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "invalid inner-door panel bounds")
    width, height = dims["width"], dims["height"]
    if any(type(v) not in (float, int) or not math.isfinite(v) or v <= 0
           for v in (width, height)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "invalid inner-door material dimensions")
    if _pure_json(frame) != _frame_record(float(width), float(height), physical_part_id):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "forged inner-door material Frame")
