# -*- coding: utf-8 -*-
"""A single source-owned Receiving C Divider physical part."""
from __future__ import annotations
import math
import re
from pathlib import Path
from collections.abc import Mapping
from integration_cli.prepare_evidence import PrepareEvidenceError, _pure_json

_SCOPE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")
_BOUNDARY = re.compile(r"^C([0-9]+):R([0-9]+)[|]R([0-9]+)$")
_PHYSICAL = re.compile(r"^whd-[0-9a-f]{24}$")
_FIELDS = frozenset({
    "kind", "cabinet_family", "source_part_ref", "dimension_semantics",
    "dimensions_mm", "divider_layout_scope", "divider_boundary_key",
    "divider_source_span_mm", "divider_frame_width_mm", "divider_handle_side",
})


def physical_c_divider_from_source(part: Mapping[str, object]):
    from ae_engine.door_dividers import _part, divider_stable_id

    if (not isinstance(part, Mapping) or set(part) != _FIELDS
            or part.get("kind") != "divider" or part.get("cabinet_family") != "受電箱"
            or part.get("dimension_semantics") != "part_formed_outer"):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Receiving C physical part contract missing")
    scope, boundary = part.get("divider_layout_scope"), part.get("divider_boundary_key")
    if (not isinstance(scope, str) or _SCOPE.fullmatch(scope) is None
            or not isinstance(boundary, str)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Saved Door boundary required")
    match = _BOUNDARY.fullmatch(boundary)
    if match is None:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Only horizontal adjacent Door boundary supported")
    col, upper, lower = map(int, match.groups())
    if lower != upper + 1:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Nonadjacent Door cells")
    stable = divider_stable_id(scope, "HORIZONTAL", boundary)
    if part.get("source_part_ref") != stable:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "C physical source identity mismatch")
    dims = part.get("dimensions_mm")
    if not isinstance(dims, Mapping) or set(dims) != {"depth", "thickness"}:
        raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "C requires owner depth and physical thickness")
    span, fw = part.get("divider_source_span_mm"), part.get("divider_frame_width_mm")
    values = [dims["depth"], dims["thickness"], span, fw]
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in values):
        raise PrepareEvidenceError("WHD_PREPARE_INPUT_INVALID", "Invalid C material dimensions")
    handle = part.get("divider_handle_side")
    if type(handle) is not bool:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Unconfirmed C handle fold direction")
    try:
        model = _part(
            layout_scope=scope, axis="HORIZONTAL", boundary_key=boundary,
            span=float(span), depth=float(dims["depth"]),
            thickness=float(dims["thickness"]), frame_width=float(fw),
            handle_side=handle, adjacent_cells=(f"{col}:{upper}", f"{col}:{lower}"),
            model_name="受電箱",
        )
        if (model.stable_id != stable or len(model.fold_profile) != 4
                or abs(model.blank_width - 158.0) > 0.04 or model.span <= 110
                or model.frame_width_segment_index != 1 or model.core_segment_index != 2):
            raise ValueError("C original source width/fold mismatch")
        return model
    except (TypeError, ValueError, OverflowError, ArithmeticError) as exc:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Canonical Receiving C Fold rejected") from exc


def source_c_path(root: Path) -> Path:
    return Path(root) / "基準檔" / "受電箱" / "框.dxf"


def _frame(physical: str, width: float, height: float):
    return {
        "frame_id": f"divider:C:{physical}:flat:size-only-v1",
        "coordinate_contract_revision": "1", "units": "mm",
        "origin_definition": (
            "WHD Receiving independently attested C CUTTING six holes and one relief, "
            "canonical Divider material Fold; no assembled contact or source Feature transform"
        ),
        "origin_xyz_mm": [0.0, 0.0, 0.0],
        "axis_x": [1.0, 0.0, 0.0], "axis_y": [0.0, 1.0, 0.0],
        "normal": [0.0, 0.0, 1.0],
        "face_role": "outer", "viewed_from": "along_normal",
        "finished_face_dimensions_mm": {"width": width, "height": height},
        "allowed_feature_types": [],
    }


def source_c_frame(part, root: Path, *, physical_part_id: str):
    from ae_engine.door_dividers import BoxBodyDividerPart
    from ae_engine.receiving_divider_c_manufacturing import build_receiving_divider_c_render_data

    if (not isinstance(part, BoxBodyDividerPart)
            or not isinstance(physical_part_id, str)
            or _PHYSICAL.fullmatch(physical_part_id) is None):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Invalid C source Frame identity")
    try:
        render = build_receiving_divider_c_render_data(part, resource_root=root)
        if (render.metadata.get("receiving_frame_source_tag") != "C"
                or render.metadata.get("receiving_frame_source_holes") != 6
                or render.metadata.get("receiving_frame_source_relief_contours") != 1):
            raise ValueError("Unverified C source aperture inventory")
        x0, y0, x1, y1 = map(float, render.material.bounds)
        width, height = x1 - x0, y1 - y0
        if any(not math.isfinite(v) or v <= 0 for v in (width, height, float(render.material.area))):
            raise ValueError("Invalid C material extent")
        return _frame(physical_part_id, width, height)
    except (OSError, TypeError, ValueError, OverflowError, ArithmeticError) as exc:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "C Final Material unavailable") from exc


def require_source_c_frame(frame, *, physical_part_id: str):
    if (not isinstance(frame, Mapping) or not isinstance(physical_part_id, str)
            or _PHYSICAL.fullmatch(physical_part_id) is None):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Invalid signed C Frame")
    dims = frame.get("finished_face_dimensions_mm")
    if not isinstance(dims, Mapping) or set(dims) != {"width", "height"}:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Missing C final envelope")
    width, height = dims["width"], dims["height"]
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in (width, height)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Invalid C Frame bounds")
    if _pure_json(frame) != _frame(physical_part_id, float(width), float(height)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "C Frame changed after signing")
