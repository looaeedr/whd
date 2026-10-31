# -*- coding: utf-8 -*-
"""#2383 one Receiving FULL rear panel as actual signed physical manufacturing.

The WHD family's existing 8-segment D/W/D input contract, fixed three-piece
side/back structure and dedicated 後面板.dxf are the ONLY manufacturing
geometry owners. This module does not invent Fold, source hole mapping,
HALF/open-back modes, NFB holes, assembly/world placement or multiple parts.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import Any

from integration_cli.prepare_evidence import PrepareEvidenceError, _pure_json
from integration_cli.worker_receiving_side_panel import (
    receiving_side_panel_expected_baselines,
)

_PHYSICAL_ID = re.compile(r"^whd-[0-9a-f]{24}$")
_SOURCE_FIELDS = frozenset({
    "kind", "cabinet_family", "source_part_ref", "dimension_semantics",
    "dimensions_mm", "frame_width_mm", "back_panel_mode",
    "box_zl1_mm", "box_zl2_mm", "box_zr2_mm",
})
_FOLD_SOURCE = (
    ("zl1", "box_zl1_mm"), ("zl2", "box_zl2_mm"),
    ("zr2", "box_zr2_mm"),
)
_TOPOLOGY = ("zl1", "zl2", "fw_left", "d_left", "w", "d_right", "fw_right", "zr2")


def receiving_back_panel_spec_from_trusted_part(part: Mapping[str, Any]):
    from ae_engine.cabinet_types import receiving
    from ae_engine.contracts import BoxBodyPartSpec
    from ae_engine.sheetmetal_geometry import box_body_height_from_corner_policies
    from phase6_fold_profiles import build_box_body_profile, profile_to_fold_segments

    if (not isinstance(part, Mapping)
            or set(part) != _SOURCE_FIELDS
            or part["kind"] != "back_panel"
            or part["cabinet_family"] != "受電箱"
            or part["source_part_ref"] != "box_body:back"
            or part["dimension_semantics"] != "cabinet_outer"
            or part["back_panel_mode"] != "FULL"):
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED",
            "only the source-owned Receiving FULL physical rear sheet is certified",
        )
    dims = part["dimensions_mm"]
    if not isinstance(dims, Mapping) or set(dims) != {
        "width", "height", "depth", "thickness",
    }:
        raise PrepareEvidenceError(
            "WHD_PREPARE_INPUT_INVALID", "FULL rear sheet needs operator W/H/D/T",
        )
    entries = [dims[k] for k in ("width", "height", "depth", "thickness")]
    entries.append(part["frame_width_mm"])
    entries.extend(part[wire] for _, wire in _FOLD_SOURCE)
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in entries):
        raise PrepareEvidenceError(
            "WHD_PREPARE_INPUT_INVALID", "non-finite or boolean rear-panel source dimension",
        )
    w, h, d, t, fw = map(float, entries[:5])
    if (min(w, h, d, t, fw) <= 0 or w <= 4*t or h <= 2*t
            or d <= 4*t or fw <= 2*t or fw >= min(w, d)):
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "Receiving rear physical dimensions impossible",
        )
    snapshot = {"model": "受電箱", "w": w, "h": h, "d": d, "t": t, "fw": fw}
    for name, field in _FOLD_SOURCE:
        snapshot[name] = float(part[field])
    try:
        fold = build_box_body_profile(snapshot)
        if (tuple(row.get("phase6_key") for row in fold) != _TOPOLOGY
                or any(not math.isfinite(float(row["len"]))
                       or float(row["len"]) <= 0 for row in fold)):
            raise ValueError("Receiving actual 8-segment folded body source lost")
        state = receiving.resolve_box_body_structure_state(None)
        from phase6_box_body_structure import (
            BoxBodyStructureType, back_panel_mode, BackPanelMode,
        )
        if back_panel_mode(state) is not BackPanelMode.FULL:
            raise ValueError("Receiving rear family no longer owns FULL mode")
        cfg = state["configs"][BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]
        back_width = w - float(cfg["back_width_comp_t"]) * t
        back_height = box_body_height_from_corner_policies(
            h, t, head_corner_policy=None, tail_corner_policy=None,
        )
        contract = receiving.resolve_back_panel_contract(
            snapshot, structure_state=state,
            panel_width=back_width, full_panel_height=back_height,
        )
        if (contract["mode"] != "FULL"
                or contract.get("opening") is not None
                or len(contract.get("fixed_slot_datums") or ()) != 4):
            raise ValueError("Receiving FULL rear panel slot contract changed")
        return BoxBodyPartSpec(
            width=w, height=h, depth=d, thickness=t,
            frame_width=fw, model_name="受電箱",
            fold_profile=profile_to_fold_segments(fold),
            structure_state=state, back_panel_contract=contract,
        )
    except (KeyError, TypeError, ValueError, OverflowError, ArithmeticError) as exc:
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "canonical Receiving FULL rear panel refused",
        ) from exc


def receiving_back_panel_render(spec: Any, context: Any):
    from ae_engine.manufacturing_api import build_box_body_structure_render_data
    if (spec.model_name != "受電箱"
            or not isinstance(spec.back_panel_contract, Mapping)
            or spec.back_panel_contract.get("mode") != "FULL"):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "not a certified FULL Receiving rear")
    try:
        pieces = build_box_body_structure_render_data(spec, context).pieces
        if len(pieces) != 3 or {piece.role for piece in pieces} != {
            "left_side", "right_side", "back",
        }:
            raise ValueError("Receiving physical three-piece assembly topology drift")
        rear = next(piece.render_data for piece in pieces if piece.role == "back")
        meta = rear.metadata
        material = rear.material
        if (material is None or material.is_empty or not material.is_valid
                or float(material.area) <= 0
                or rear.fold_guides
                or meta.get("back_panel_mode") != "FULL"
                or meta.get("baseline_source_status") != "VERIFIED"
                or meta.get("baseline_feature_count") != 4
                or meta.get("baseline_fit_error")):
            raise ValueError("Receiving FULL rear stock or exact 4 source slots invalid")
        minx, miny, maxx, maxy = map(float, material.bounds)
        if not (0 < maxx-minx and 0 < maxy-miny):
            raise ValueError("Rear material blank invalid")
        return rear
    except (KeyError, TypeError, ValueError, StopIteration, OverflowError, ArithmeticError) as exc:
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "Receiving FULL rear FinalScene or fixed source slots unavailable",
        ) from exc


def _frame_record(width: float, height: float, physical: str) -> dict[str, Any]:
    return {
        "frame_id": f"back_panel:{physical}:flat:size-only-v1",
        "coordinate_contract_revision": "1",
        "units": "mm",
        "origin_definition": (
            "WHD Receiving dedicated FULL rear panel exact fixed four source "
            "keyslots, unfolded size only; no source feature mapping, joint, "
            "half/back-opening mode or assembly/world coordinates"
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


def receiving_back_panel_frame(spec: Any, context: Any, *, physical_part_id: str):
    if not isinstance(physical_part_id, str) or _PHYSICAL_ID.fullmatch(physical_part_id) is None:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "unverified rear physical part ID")
    render = receiving_back_panel_render(spec, context)
    x0,y0,x1,y1 = map(float, render.material.bounds)
    return _frame_record(x1-x0,y1-y0,physical_part_id)


def require_receiving_back_panel_frame(frame: Any, *, physical_part_id: str):
    if (not isinstance(physical_part_id, str)
            or _PHYSICAL_ID.fullmatch(physical_part_id) is None
            or not isinstance(frame, Mapping)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "unknown rear physical Frame")
    dims = frame.get("finished_face_dimensions_mm")
    if not isinstance(dims, Mapping) or set(dims) != {"width", "height"}:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "rear physical material dimensions missing")
    w,h = dims["width"],dims["height"]
    if any(type(v) not in (float,int) or not math.isfinite(v) or v <= 0
           for v in (w,h)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "rear physical dimensions invalid")
    if _pure_json(frame) != _frame_record(float(w),float(h),physical_part_id):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "forged Receiving rear Frame")
