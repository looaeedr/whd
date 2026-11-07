"""Engine-owned Head/Tail physical Feature -> legacy 2D hole cache projection.

The main GUI consumes these legacy dictionaries for its older 2D renderer.
This read-only compatibility projection does not authorize manufacturing holes:
typed Features and the original finished-face placement remain the authority.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from math import isfinite

from .operator_settings_transactions import normalize_operator_source_dimension
from .sheetmetal_features import (
    CircleFeature, RectFeature, ProfileFeature, feature_to_legacy_hole,
)


def project_operator_endcap_legacy_hole_rows(
    source_features: Mapping[str, object], *, width: object, depth: object,
) -> dict[str, list[dict]]:
    """Stage both existing Head/Tail hole views before the GUI commits either.

    Only explicitly supplied Head/Tail keys are returned; missing keys keep
    their current GUI cache. The caller can deliberately pass an empty list
    when a project reload must clear a previously saved role.

    The existing Engine feature-to-finished-face converter is reused for
    every physical hole; invalid sources reject the *entire* candidate.
    """
    if not isinstance(source_features, Mapping):
        raise ValueError("endcap feature sources must be a mapping")
    finished_w = normalize_operator_source_dimension(width, field="w")
    finished_d = normalize_operator_source_dimension(depth, field="d")

    projected: dict[str, list[dict]] = {}
    for role in ("head", "tail"):
        if role not in source_features:
            continue
        source_rows = source_features[role]
        if source_rows is None:
            source_rows = ()
        if isinstance(source_rows, (str, bytes, Mapping)):
            raise ValueError(f"invalid {role} Feature rows")
        try:
            rows = tuple(source_rows)
        except TypeError as exc:
            raise ValueError(f"invalid {role} Feature rows") from exc

        converted = []
        for feature in rows:
            if not isinstance(feature, (CircleFeature, RectFeature, ProfileFeature)):
                raise ValueError(f"invalid {role} physical Feature")
            hole = feature_to_legacy_hole(feature, finished_w, finished_d)
            if not (isfinite(float(hole["x"])) and isfinite(float(hole["y"]))):
                raise ValueError(f"invalid {role} finished-face hole coordinate")
            converted.append(deepcopy(hole))
        projected[role] = converted
    return projected
