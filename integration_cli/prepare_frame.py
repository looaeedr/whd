# -*- coding: utf-8 -*-
"""Door-only finished-face *local* transport frame, owned by WHD (#2378).

The authoritative 2D origin and direction come from FeatureAnchor,
feature_finished_point and the finished-reference guide.  This local XY
embedding is NOT a world/assembly pose, an EndCap mapping or a DXF coordinate.
"""
from __future__ import annotations

import math
import re
from typing import Any

from integration_cli.prepare_evidence import PrepareEvidenceError, resolve_authoritative_door_inputs

_FRAME_ID_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def resolve_door_finished_local_frame(
    spec: Any, context: Any, *, physical_part_id: str
) -> dict[str, Any]:
    """Issue an explicit local datum, never silently infer a CADSplit source transform.

    Frame origin=(0,0,0) is the *local finished-face lower-left*; X to right,
    Y up. Z is the right-handed local normal (NOT an assembly-world vector).
    The actual finished-face→DXF relationship is still owned by the existing
    WHD build_finished_reference_guide, not this protocol adapter.
    """
    if not isinstance(physical_part_id, str) or not _FRAME_ID_PART.fullmatch(physical_part_id):
        raise PrepareEvidenceError("WHD_PHYSICAL_ID_INVALID", "verified physical part ID required")
    authoritative = resolve_authoritative_door_inputs(spec, context)
    width = float(authoritative["finished_face_dimensions_mm"]["width"])
    height = float(authoritative["finished_face_dimensions_mm"]["height"])

    from ae_engine.sheetmetal_features import (
        CircleFeature, FeatureAnchor, Vec2, feature_finished_point,
    )
    # Guard the actual owning anchor semantics instead of defining a second
    # coordinate converter in Worker.
    bottom_left = feature_finished_point(
        CircleFeature(diameter=1, anchor=FeatureAnchor.BOTTOM_LEFT, offset=Vec2(0, 0)),
        width, height,
    )
    top_right = feature_finished_point(
        CircleFeature(diameter=1, anchor=FeatureAnchor.TOP_RIGHT, offset=Vec2(0, 0)),
        width, height,
    )
    absolute = feature_finished_point(
        CircleFeature(diameter=1, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE, offset=Vec2(0, 0)),
        width, height,
    )
    if any(not math.isfinite(float(x)) for x in (width, height, bottom_left.x, bottom_left.y, top_right.x, top_right.y, absolute.x, absolute.y)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "nonfinite authoritative Door frame")
    if (bottom_left.x, bottom_left.y) != (0.0, 0.0) or (absolute.x, absolute.y) != (0.0, 0.0) or (top_right.x, top_right.y) != (width, height):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "WHD Door finished-face anchor contract changed")
    if width <= 0 or height <= 0:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "empty Door finished-face")

    return _door_frame_record(width, height, physical_part_id)


def _door_frame_record(width: float, height: float, physical_part_id: str) -> dict[str, Any]:
    """Single WHD owner for the supported Door-local wire basis."""
    return {
        "frame_id": f"door:{physical_part_id}:front:local-v1",
        "coordinate_contract_revision": "1",
        "units": "mm",
        "origin_definition": (
            "WHD Door local finished-face bottom-left (absolute anchor); "
            "NOT cabinet-world/assembly coordinates"
        ),
        "origin_xyz_mm": [0.0, 0.0, 0.0],
        "axis_x": [1.0, 0.0, 0.0],
        "axis_y": [0.0, 1.0, 0.0],
        "normal": [0.0, 0.0, 1.0],
        "face_role": "front",
        "viewed_from": "along_normal",
        "finished_face_dimensions_mm": {"width": width, "height": height},
        "allowed_feature_types": ["circle", "rect", "profile"],
    }


def require_canonical_door_local_frame(frame: Any, *, physical_part_id: str) -> None:
    """Fail closed before signing a caller-supplied frame, not just on token recheck.

    Only the exact Door-local basis that WHD issues in this revision can be
    sealed. This checks transport provenance, never a fabrication formula.
    """
    from collections.abc import Mapping
    from integration_cli.prepare_evidence import _pure_json

    if (not isinstance(physical_part_id, str) or
            not _FRAME_ID_PART.fullmatch(physical_part_id) or
            not isinstance(frame, Mapping)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "missing verified Door-local frame")
    dimensions = frame.get("finished_face_dimensions_mm")
    if not isinstance(dimensions, Mapping) or set(dimensions) != {"width", "height"}:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "missing finished-face bounds")
    width, height = dimensions["width"], dimensions["height"]
    if (type(width) not in (int, float) or type(height) not in (int, float) or
            not math.isfinite(float(width)) or not math.isfinite(float(height)) or
            width <= 0 or height <= 0):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "invalid finished-face bounds")
    for key in ("origin_xyz_mm", "axis_x", "axis_y", "normal"):
        vector = frame.get(key)
        if (not isinstance(vector, list) or len(vector) != 3 or
                any(type(v) not in (int, float) or not math.isfinite(float(v)) for v in vector)):
            raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "invalid Door-local basis vector")
    expected = _door_frame_record(float(width), float(height), physical_part_id)
    if _pure_json(frame) != expected:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Frame is not WHD-issued Door-local basis")

def _indicator_box_size_only_record(width: float, height: float, physical_part_id: str) -> dict[str, Any]:
    """WHD-owned width/height, no authority to map a caller Feature to DXF."""
    return {
        "frame_id": f"indicator_box:{physical_part_id}:outer:local-v1",
        "coordinate_contract_revision": "1",
        "units": "mm",
        "origin_definition": (
            "WHD shared indicator box formed outside-face size-only datum; "
            "no certified source-to-DXF Feature mapping"
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


def resolve_indicator_box_size_only_frame(
    spec: Any, context: Any, *, physical_part_id: str,
) -> dict[str, Any]:
    """W-03 can attest WHD shared box size; W-04 placement is still closed."""
    from ae_engine.contracts import IndicatorBoxPartSpec
    from ae_engine.manufacturing_api import indicator_box_finished_face_size

    if (not isinstance(spec, IndicatorBoxPartSpec)
            or not isinstance(physical_part_id, str)
            or not _FRAME_ID_PART.fullmatch(physical_part_id)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "verified box identity required")
    width, height = indicator_box_finished_face_size(
        spec.layer_groups, thickness=spec.thickness, context=context,
    )
    if any(not math.isfinite(v) or v <= 0 for v in (width, height)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "invalid shared box outside face")
    return _indicator_box_size_only_record(float(width), float(height), physical_part_id)


def require_canonical_indicator_box_size_only_frame(
    frame: Any, *, physical_part_id: str,
) -> None:
    """Only the exact feature-disabled frame can enter a signed receipt."""
    from collections.abc import Mapping
    from integration_cli.prepare_evidence import _pure_json

    if (not isinstance(physical_part_id, str)
            or not _FRAME_ID_PART.fullmatch(physical_part_id)
            or not isinstance(frame, Mapping)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "untrusted indicator-box frame")
    dims = frame.get("finished_face_dimensions_mm")
    if not isinstance(dims, Mapping) or set(dims) != {"width", "height"}:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "missing box outside dimensions")
    w, h = dims["width"], dims["height"]
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in (w, h)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "invalid box outside dimensions")
    if _pure_json(frame) != _indicator_box_size_only_record(float(w), float(h), physical_part_id):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "box Frame cannot authorize external Features")

def _endcap_size_only_record(
    width: float, height: float, physical_part_id: str, kind: str,
) -> dict[str, Any]:
    """Serialize only WHD's existing local EndCap finished-face guide size.

    This is NOT a world assembly transform, a cut-feature placement contract,
    or certification of head/tail fold orientation.
    """
    if kind not in ("end_cap_head", "end_cap_tail"):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "invalid EndCap role")
    return {
        "frame_id": f"{kind}:{physical_part_id}:outer:size-only-v1",
        "coordinate_contract_revision": "1",
        "units": "mm",
        "origin_definition": (
            "WHD Vault EndCap finished-face guide size only; "
            "no certified local-to-assembly or source-to-DXF mapping"
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


def resolve_endcap_size_only_frame(
    spec: Any, *, physical_part_id: str,
) -> dict[str, Any]:
    """Use the official AE EndCap guide without duplicating its dimensional math."""
    from ae_engine.contracts import EndCapPartSpec
    from ae_engine.sheetmetal_feature_surface import resolve_endcap_finished_face_guide

    if (not isinstance(spec, EndCapPartSpec)
            or spec.model_name != "金庫型"
            or not isinstance(physical_part_id, str)
            or not _FRAME_ID_PART.fullmatch(physical_part_id)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "Vault EndCap authority missing")
    try:
        guide = resolve_endcap_finished_face_guide(
            spec.width, spec.depth, spec.thickness,
        )
        width = float(guide.max_point.x - guide.min_point.x)
        height = float(guide.max_point.y - guide.min_point.y)
    except (TypeError, ValueError, OverflowError, ArithmeticError) as exc:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "EndCap finished guide unavailable") from exc
    if any(not math.isfinite(v) or v <= 0 for v in (width, height)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "EndCap finished face has no area")
    kind = "end_cap_tail" if spec.is_tail else "end_cap_head"
    return _endcap_size_only_record(width, height, physical_part_id, kind)


def require_canonical_endcap_size_only_frame(
    frame: Any, *, physical_part_id: str, kind: str,
) -> None:
    """Reject caller-rewritten size-only data and any enabled Features."""
    from collections.abc import Mapping
    from integration_cli.prepare_evidence import _pure_json

    if (not isinstance(physical_part_id, str)
            or not _FRAME_ID_PART.fullmatch(physical_part_id)
            or kind not in ("end_cap_head", "end_cap_tail")
            or not isinstance(frame, Mapping)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "untrusted EndCap frame")
    dims = frame.get("finished_face_dimensions_mm")
    if not isinstance(dims, Mapping) or set(dims) != {"width", "height"}:
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "missing EndCap finished-face dimensions")
    w, h = dims["width"], dims["height"]
    if any(type(v) not in (int, float) or not math.isfinite(v) or v <= 0 for v in (w, h)):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "invalid EndCap finished-face bounds")
    if _pure_json(frame) != _endcap_size_only_record(float(w), float(h), physical_part_id, kind):
        raise PrepareEvidenceError("WHD_FRAME_UNVERIFIED", "EndCap frame cannot authorize external Features")
