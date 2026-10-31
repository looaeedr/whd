# -*- coding: utf-8 -*-
"""#2383 Receiving actual independent rear sheet (FULL/BACK_OPENING only).

The canonical Receiving three-piece family, operator-confirmed factory Fold
scalars, three dedicated certified reference DXFs and AE resolved BackPanel
contract own the real CUTTING and fixed key-slots. Unlike side pieces the
rear sheet is flat: lack of a BEND guide is correct, not missing geometry.
HALF needs source-attested two-section Door topology and remains blocked.
"""
from __future__ import annotations

from dataclasses import replace
import math
import re
from collections.abc import Mapping
from typing import Any

from integration_cli.prepare_evidence import PrepareEvidenceError, _pure_json
from integration_cli.worker_receiving_side_panel import (
    receiving_side_panel_spec_from_trusted_part,
    receiving_side_panel_expected_baselines,
)

_PHYSICAL = re.compile(r"^whd-[0-9a-f]{24}$")
_FACTORY_FIELDS = frozenset({
    "kind", "cabinet_family", "source_part_ref", "dimension_semantics",
    "dimensions_mm", "frame_width_mm",
    "box_zl1_mm", "box_zl2_mm", "box_zr2_mm", "back_panel_mode",
})
_MODES = frozenset({"FULL", "BACK_OPENING"})


def receiving_back_panel_spec_from_trusted_part(part: Mapping[str, Any]):
    """Read exactly one source-bound Receiving rear physical sheet.

    We reuse the already-certified side-panel factory D-W-D conversion,
    with the exact same three baselines, but select a separately signed
    rear panel mode/contract; external source holes are not projected.
    """
    from ae_engine.cabinet_types import receiving
    from ae_engine.box_body_structure import box_body_height_from_corner_policies
    from phase6_box_body_structure import set_side_back_back_panel_mode

    if (not isinstance(part, Mapping)
            or set(part) != _FACTORY_FIELDS
            or part.get("kind") != "back_panel"
            or part.get("cabinet_family") != "受電箱"
            or part.get("source_part_ref") != "box_body:back"
            or part.get("dimension_semantics") != "cabinet_outer"
            or part.get("back_panel_mode") not in _MODES):
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED",
            "only confirmed FULL/BACK_OPENING Receiving physical rear panel supported",
        )
    copied = {k: v for k, v in part.items() if k != "back_panel_mode"}
    copied["kind"] = "side_panel"
    copied["source_part_ref"] = "box_body:left_side"
    # This calls exactly the signed 8-segment Receiving D-W-D parser and
    # rejects unknown family fields before any mode-specific geometry.
    base, role = receiving_side_panel_spec_from_trusted_part(copied)
    if role != "left_side" or base.model_name != "受電箱":
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Receiving factory source topology changed")
    mode = part["back_panel_mode"]
    try:
        state = set_side_back_back_panel_mode(base.structure_state, mode)
        dimensions = part["dimensions_mm"]
        snapshot = {
            "model": "受電箱",
            "w": float(dimensions["width"]),
            "h": float(dimensions["height"]),
            "d": float(dimensions["depth"]),
            "t": float(dimensions["thickness"]),
            "fw": float(part["frame_width_mm"]),
            "zl1": float(part["box_zl1_mm"]),
            "zl2": float(part["box_zl2_mm"]),
            "zr2": float(part["box_zr2_mm"]),
        }
        from phase6_box_body_structure import back_panel_mode
        if back_panel_mode(state).value != mode:
            raise ValueError("Receiving rear-panel mode was not persisted")
        from phase6_box_body_structure import BoxBodyStructureType
        config = state["configs"][BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value]
        panel_width = base.width - float(config["back_width_comp_t"]) * base.thickness
        full_height = box_body_height_from_corner_policies(
            base.height, base.thickness,
            head_corner_policy=None, tail_corner_policy=None,
        )
        contract = receiving.resolve_back_panel_contract(
            snapshot, structure_state=state,
            panel_width=panel_width, full_panel_height=full_height,
        )
        if (contract.get("mode") != mode
                or len(tuple(contract.get("fixed_slot_profiles") or ())) != 4
                or (contract.get("opening") is not None) != (mode == "BACK_OPENING")):
            raise ValueError("certified rear CUTTING mode contract missing")
    except (TypeError, ValueError, KeyError, ArithmeticError, OverflowError) as exc:
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "Receiving rear-panel factory mode source could not be verified",
        ) from exc
    return replace(base, structure_state=state, back_panel_contract=contract)


def receiving_back_panel_render(spec, context):
    from ae_engine.manufacturing_api import build_box_body_structure_render_data
    from ae_engine.sheetmetal_drawing import PolylinePrimitive

    if spec.model_name != "受電箱" or (
        not isinstance(spec.back_panel_contract, Mapping)
        or spec.back_panel_contract.get("mode") not in _MODES
    ):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "unregistered Receiving back-panel spec")
    try:
        pieces = build_box_body_structure_render_data(spec, context).pieces
        if len(pieces) != 3 or {p.role for p in pieces} != {
            "left_side", "right_side", "back",
        }:
            raise ValueError("Receiving family physical 3-piece structure changed")
        render = next(row.render_data for row in pieces if row.role == "back")
        metadata = render.metadata
        material = render.material
        mode = spec.back_panel_contract["mode"]
        closed = tuple(
            p for p in render.scene.primitives
            if isinstance(p, PolylinePrimitive) and p.layer == "CUTTING" and p.closed
        )
        # Flat rear sheet: exactly one real stock boundary, four certified
        # R8/4.5 key-slots, and optionally the exact source 650x200 opening.
        if (material is None or material.is_empty or not material.is_valid
                or not math.isfinite(float(material.area)) or material.area <= 0
                or render.fold_guides
                or len(closed) != (5 if mode == "FULL" else 6)
                or metadata.get("baseline_source_status") != "VERIFIED"
                or metadata.get("baseline_source_role") != "back"
                or metadata.get("baseline_feature_count") != (4 if mode == "FULL" else 5)
                or metadata.get("baseline_fit_error")
                or metadata.get("back_panel_mode") != mode):
            raise ValueError("Receiving real rear CUTTING/key-slot geometry unverified")
        left, bottom, right, top = map(float, material.bounds)
        if any(not math.isfinite(v) or v <= 0 for v in (
            right-left, top-bottom,
        )):
            raise ValueError("Receiving rear panel material envelope invalid")
        return render
    except (TypeError, ValueError, ArithmeticError, OverflowError, StopIteration) as exc:
        raise PrepareEvidenceError(
            "WHD_FRAME_UNVERIFIED", "Receiving dedicated rear DXF FinalScene unavailable",
        ) from exc


def _frame_record(mode: str, width: float, height: float, physical: str) -> dict[str, Any]:
    return {
        "frame_id": f"back_panel:{mode}:{physical}:flat:size-only-v1",
        "coordinate_contract_revision": "1",
        "units": "mm",
        "origin_definition": (
            "WHD Receiving back physical sheet " + mode
            + " certified source DXF key-slots and optional 650x200 opening; "
            + "flat size-only Final Material, no source Feature/assembly mapping"
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


def receiving_back_panel_frame(spec, context, *, physical_part_id: str):
    if not isinstance(physical_part_id, str) or _PHYSICAL.fullmatch(physical_part_id) is None:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "invalid Receiving rear physical identity")
    rd = receiving_back_panel_render(spec, context)
    lowx, lowy, highx, highy = map(float, rd.material.bounds)
    return _frame_record(
        spec.back_panel_contract["mode"], highx-lowx, highy-lowy, physical_part_id,
    )


def require_receiving_back_panel_frame(frame, *, mode: str, physical_part_id: str):
    if (mode not in _MODES or not isinstance(frame, Mapping)
            or not isinstance(physical_part_id, str)
            or _PHYSICAL.fullmatch(physical_part_id) is None):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "invalid rear sheet Frame")
    dims = frame.get("finished_face_dimensions_mm")
    if not isinstance(dims, Mapping) or set(dims) != {"width", "height"}:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "rear sheet dimensions missing")
    width, height = dims["width"], dims["height"]
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0
           for v in (width, height)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "rear sheet dimensions invalid")
    if _pure_json(frame) != _frame_record(mode, float(width), float(height), physical_part_id):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Receiving rear sheet Frame forged")
