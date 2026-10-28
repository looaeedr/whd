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
