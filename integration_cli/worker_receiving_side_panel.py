# -*- coding: utf-8 -*-
"""#2383 Receiving real side-sheet W-08 Worker source/Frame authority.

The existing Receiving family Fold/three-piece resolver and dedicated
left/right/back reference DXFs own material, fixed holes, BLIND_HOLE, MARKING
and stock geometry. This module selects exactly ONE independent side panel.
No part splitting, assembly, side-to-back joints or external source holes.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any

from integration_cli.prepare_evidence import PrepareEvidenceError, _pure_json

_WHD_ID = re.compile(r"^whd-[0-9a-f]{24}$")
_INPUTS = (
    ("zl1", "box_zl1_mm"), ("zl2", "box_zl2_mm"),
    ("zr1", "box_zr1_mm"), ("zr2", "box_zr2_mm"),
    ("z_comp", "box_z_comp_mm"),
)
_KINDS = {"box_body:left_side": "left_side", "box_body:right_side": "right_side"}
_PART_FIELDS = {
    "kind", "cabinet_family", "source_part_ref", "dimension_semantics",
    "dimensions_mm", "frame_width_mm",
    *(field for _, field in _INPUTS),
}
_BASELINES = ("左側板.dxf", "右側板.dxf", "後面板.dxf")


def receiving_side_panel_spec_from_trusted_part(part: Mapping[str, Any]):
    from ae_engine.cabinet_types import receiving
    from ae_engine.box_body_structure import box_body_height_from_corner_policies
    from ae_engine.contracts import BoxBodyPartSpec
    from phase6_fold_profiles import build_box_body_profile, profile_to_fold_segments

    if (not isinstance(part, Mapping)
            or part.get("kind") != "side_panel"
            or part.get("cabinet_family") != "受電箱"
            or part.get("dimension_semantics") != "cabinet_outer"
            or part.get("source_part_ref") not in _KINDS
            or set(part) != _PART_FIELDS):
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "only one source-owned Receiving left/right physical sheet is certified"
        )
    dimensions = part.get("dimensions_mm")
    if not isinstance(dimensions, Mapping) or set(dimensions) != {
        "width", "height", "depth", "thickness",
    }:
        raise PrepareEvidenceError(
            "WHD_PREPARE_INPUT_INVALID", "exact Receiving side/back factory W/H/D/T required"
        )
    values = [dimensions[n] for n in ("width", "height", "depth", "thickness")]
    values.append(part["frame_width_mm"])
    values.extend(part[field] for _, field in _INPUTS)
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise PrepareEvidenceError(
            "WHD_PREPARE_INPUT_INVALID", "Receiving source dimensions/fold scalars must be finite numeric"
        )
    w, h, d, t, fw = map(float, values[:5])
    if (min(w, h, d, t, fw) <= 0 or w <= 4 * t or h <= 2 * t
            or d <= 4 * t or fw <= 2 * t or fw >= min(w, d)):
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "impossible Receiving physical side dimensions/FW"
        )
    # These are independent already-confirmed operator outside dimensions:
    # do not allow family defaults to replace input or infer missing W/D/FW.
    snapshot = {
        "model": "受電箱", "w": w, "h": h, "d": d,
        "t": t, "fw": fw,
    }
    for name, wire in _INPUTS:
        snapshot[name] = float(part[wire])
    try:
        fold_rows = build_box_body_profile(snapshot)
        if len(fold_rows) != 9 or any(
                not math.isfinite(float(row["len"])) or float(row["len"]) <= 0
                for row in fold_rows):
            raise ValueError("unverified Receiving D-W-D source profile")
        fold = profile_to_fold_segments(fold_rows)
        state = receiving.resolve_box_body_structure_state(None)
        from phase6_box_body_structure import BoxBodyStructureType
        config = state["configs"][BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]
        back_comp = float(config["back_width_comp_t"])
        back_width = w - back_comp * t
        back_height = box_body_height_from_corner_policies(
            h, t, head_corner_policy=None, tail_corner_policy=None,
        )
        back_contract = receiving.resolve_back_panel_contract(
            snapshot, structure_state=state,
            panel_width=back_width, full_panel_height=back_height,
        )
    except (TypeError, ValueError, OverflowError, ArithmeticError, KeyError) as exc:
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "WHD canonical Receiving split Fold/back source refused"
        ) from exc
    spec = BoxBodyPartSpec(
        width=w, height=h, depth=d, thickness=t, frame_width=fw,
        model_name="受電箱", fold_profile=fold, structure_state=state,
        back_panel_contract=back_contract,
    )
    return spec, _KINDS[part["source_part_ref"]]


def receiving_side_panel_expected_baselines(resource_root) -> tuple:
    from pathlib import Path
    root = Path(resource_root)
    return tuple(root / "基準檔" / "受電箱" / name for name in _BASELINES)


def receiving_side_panel_render(spec, role: str, context):
    from ae_engine.manufacturing_api import build_box_body_structure_render_data
    if role not in _KINDS.values() or spec.model_name != "受電箱":
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "unregistered Receiving physical side sheet")
    try:
        pieces = build_box_body_structure_render_data(spec, context).pieces
        if len(pieces) != 3 or {p.role for p in pieces} != {
            "left_side", "right_side", "back",
        }:
            raise ValueError("Receiving split physical topology changed")
        chosen = next(p for p in pieces if p.role == role)
        render = chosen.render_data
        material = render.material
        meta = render.metadata
        if (material is None or material.is_empty or not material.is_valid
                or not render.fold_guides or float(material.area) <= 0
                or meta.get("baseline_source_status") != "VERIFIED"
                or meta.get("baseline_feature_count") != 9
                or meta.get("baseline_fit_error")):
            raise ValueError("Receiving dedicated side panel CUTTING/BEND or fixed-hole fit invalid")
        lowx, lowy, highx, highy = map(float, material.bounds)
        width, height = highx - lowx, highy - lowy
        if any(not math.isfinite(v) or v <= 0 for v in (width, height)):
            raise ValueError("invalid side material bounds")
        return render
    except (TypeError, ValueError, ArithmeticError, OverflowError, StopIteration) as exc:
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "WHD Receiving dedicated side FinalScene unavailable"
        ) from exc


def _frame_record(role: str, width: float, height: float, physical_id: str) -> dict[str, Any]:
    return {
        "frame_id": f"side_panel:{role}:{physical_id}:flat:size-only-v1",
        "coordinate_contract_revision": "1",
        "units": "mm",
        "origin_definition": (
            "WHD Receiving " + role + " dedicated reference DXF/Factory Fold "
            "unfolded Final Material only; no certified original CADSplit "
            "feature projection, side-to-back assembly or joint placement"
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


def receiving_side_panel_frame(spec, role: str, context, *, physical_part_id: str):
    if not isinstance(physical_part_id, str) or _WHD_ID.fullmatch(physical_part_id) is None:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "untrusted Receiving side physical ID")
    render = receiving_side_panel_render(spec, role, context)
    x0, y0, x1, y1 = map(float, render.material.bounds)
    return _frame_record(role, x1-x0, y1-y0, physical_part_id)


def require_receiving_side_panel_frame(frame, *, role: str, physical_part_id: str):
    if (role not in _KINDS.values() or not isinstance(frame, Mapping)
            or not isinstance(physical_part_id, str)
            or _WHD_ID.fullmatch(physical_part_id) is None):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "invalid Receiving side Frame")
    dims = frame.get("finished_face_dimensions_mm")
    if not isinstance(dims, Mapping) or set(dims) != {"width", "height"}:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "side Frame material bounds missing")
    width, height = dims["width"], dims["height"]
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
           for v in (width, height)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "side Frame material dimensions invalid")
    if _pure_json(frame) != _frame_record(role, float(width), float(height), physical_part_id):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "forged Receiving physical side Frame")
