# -*- coding: utf-8 -*-
"""#2379 W-04: fail-closed wire Feature preflight against WHD-issued Frame.

This checks the caller's *claims*, not the original CADSplit DXF entities.
It is NOT source verification, PartSpec mapping, manufacturing certification,
a public export handler, or authorization to commit any DXF. W-04 must still
reopen verified source geometry and map it through the canonical WHD owner.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from integration_cli.prepare_evidence import PrepareEvidenceError


def _reject(reason: str) -> None:
    raise PrepareEvidenceError("WHD_FEATURE_UNVERIFIED", reason)


def _finite(value: Any) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        _reject("Feature coordinate or transform must be a finite real number")
    return float(value)


def _xy(value: Any) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        _reject("Feature point must contain exactly two coordinates")
    return _finite(value[0]), _finite(value[1])


def _positive(value: Any) -> float:
    number = _finite(value)
    if number <= 0:
        _reject("Feature size must be positive")
    return number


def _inside(x: float, y: float, width: float, height: float) -> None:
    if not (0 <= x <= width and 0 <= y <= height):
        _reject("Feature lies outside the WHD-issued finished face")


def _validate_transform(transform: Mapping[str, Any], dimensions: Mapping[str, Any]) -> None:
    source_unit = transform.get("source_units")
    scale = _finite(transform.get("source_to_mm_scale"))
    if (source_unit, scale) not in (("mm", 1.0), ("inch", 25.4)):
        _reject("Source units and mm scale disagree")

    for name in ("source_dimensions_mm", "target_dimensions_mm"):
        values = transform.get(name)
        if not isinstance(values, Mapping):
            _reject("Missing source/target dimension evidence")
        measured = (_positive(values.get("width")), _positive(values.get("height")))
        if name == "target_dimensions_mm" and measured != (
            _positive(dimensions.get("width")), _positive(dimensions.get("height"))
        ):
            _reject("Target dimensions differ from the WHD-issued Frame")

    matrix = transform.get("matrix_2x2")
    if not isinstance(matrix, (list, tuple)) or len(matrix) != 2:
        _reject("Invalid source transform matrix")
    a, b = _xy(matrix[0])
    c, d = _xy(matrix[1])
    _xy(transform.get("translation_mm"))
    if type(transform.get("mirror_x")) is not bool or type(transform.get("mirror_y")) is not bool:
        _reject("Mirroring flags must be exact booleans")
    turn = transform.get("rotation_deg")
    if type(turn) is not int or turn not in (0, 90, 180, 270):
        _reject("Only declared quarter turns are supported")

    rotation = {
        0: ((1, 0), (0, 1)),
        90: ((0, -1), (1, 0)),
        180: ((-1, 0), (0, -1)),
        270: ((0, 1), (-1, 0)),
    }[turn]
    sx = -1 if transform["mirror_x"] else 1
    sy = -1 if transform["mirror_y"] else 1
    # Both orders are supported because the current wire contract specifies
    # the explicit matrix, not an order of mirror/rotate composition.
    before = ((rotation[0][0] * sx, rotation[0][1] * sy),
              (rotation[1][0] * sx, rotation[1][1] * sy))
    after = ((sx * rotation[0][0], sx * rotation[0][1]),
             (sy * rotation[1][0], sy * rotation[1][1]))
    actual = ((a, b), (c, d))
    if not any(
        all(math.isclose(actual[i][j], expected[i][j], abs_tol=1e-9, rel_tol=0)
            for i in range(2) for j in range(2))
        for expected in (before, after)
    ):
        _reject("Matrix, mirror flags, and quarter-turn evidence disagree")


def _validate_shape(feature: Mapping[str, Any], width: float, height: float) -> None:
    kind = feature.get("type")
    if kind == "circle":
        x, y = _xy(feature.get("center_mm"))
        radius = _positive(feature.get("radius_mm"))
        _inside(x - radius, y - radius, width, height)
        _inside(x + radius, y + radius, width, height)
    elif kind == "rect":
        x, y = _xy(feature.get("center_mm"))
        rw, rh = _positive(feature.get("width_mm")), _positive(feature.get("height_mm"))
        turn = feature.get("rotation_deg")
        if type(turn) is not int or turn not in (0, 90, 180, 270):
            _reject("Unverified rectangular feature rotation")
        half_x, half_y = (rh / 2, rw / 2) if turn in (90, 270) else (rw / 2, rh / 2)
        _inside(x - half_x, y - half_y, width, height)
        _inside(x + half_x, y + half_y, width, height)
    elif kind == "profile":
        points = feature.get("points_mm")
        if feature.get("closed") is not True or not isinstance(points, (list, tuple)):
            _reject("Profile must be a closed point sequence")
        coords = tuple(_xy(point) for point in points)
        if len(set(coords)) < 3:
            _reject("Profile has fewer than three distinct vertices")
        for x, y in coords:
            _inside(x, y, width, height)
        from shapely.geometry import Polygon
        polygon = Polygon(coords)
        if not polygon.is_valid or polygon.is_empty or polygon.area <= 0:
            _reject("Profile is self-intersecting or has no material area")
    else:
        _reject("Unsupported wire Feature type")


def validate_wire_features_against_prepared_frame(
    features: Sequence[Mapping[str, Any]],
    frame: Mapping[str, Any],
) -> None:
    """Check untrusted Feature envelope; never certify claimed source geometry.

    W-03 first checks the authenticated prepare receipt/Frame identity. This
    additional W-04 gate rejects malformed, contradictory, duplicated or
    out-of-face Feature claims before W-04 render/staging. A passing result
    does NOT attest original DXF entities, feature transforms applied once,
    or the Worker-owned job journal.
    """
    if not isinstance(features, (list, tuple)) or not isinstance(frame, Mapping):
        _reject("Missing Feature list or trusted target Frame")
    dims = frame.get("finished_face_dimensions_mm")
    if not isinstance(dims, Mapping):
        _reject("Missing trusted finished-face dimensions")
    width, height = _positive(dims.get("width")), _positive(dims.get("height"))
    allowed = frame.get("allowed_feature_types", ())
    seen: set[str] = set()
    for feature in features:
        if not isinstance(feature, Mapping):
            _reject("Malformed Feature entry")
        identity = feature.get("feature_id")
        if not isinstance(identity, str) or not identity or identity in seen:
            _reject("Duplicate or missing Feature identity")
        seen.add(identity)
        if feature.get("type") not in allowed:
            _reject("Feature shape not permitted by WHD-issued Frame")
        if (feature.get("coordinate_space") != "finished_face"
                or feature.get("units") != "mm"
                or feature.get("target_frame_id") != frame.get("frame_id")
                or feature.get("face_role") != frame.get("face_role")
                or feature.get("viewed_from") != frame.get("viewed_from")):
            _reject("Feature Frame/face orientation differs from WHD-issued Frame")
        if feature.get("process") not in ("THROUGH_CUT", "BLIND_HOLE", "MARKING"):
            _reject("Unverified fabrication process")
        transform = feature.get("source_transform")
        if not isinstance(transform, Mapping):
            _reject("Missing original source-transform evidence")
        _validate_transform(transform, dims)
        _validate_shape(feature, width, height)
