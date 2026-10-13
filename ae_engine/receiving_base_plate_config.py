"""Receiving-family physical Base Plate configuration adapter.

Only the EXISTING BasePlatePartSpec is manufactured. These values select an
explicit physical plate variant; source DXF layout is not a placement datum.
Unconfigured legacy projects remain previewable, not production-authorized.
"""
from __future__ import annotations

from collections.abc import Mapping
from math import isfinite

from .sheetmetal_part_adapters import (
    RECEIVING_BASE_PATTERNS, build_receiving_base_plate_result,
)

RECEIVING_FAMILIES = frozenset(("受電箱", "RECEIVING"))
_REQUIRED = (
    "pattern", "height", "shrink_top", "shrink_bottom",
    "shrink_left", "shrink_right", "bend",
)


def receiving_base_plate_values(snapshot):
    """Return existing BasePlatePartSpec input values; never guess a variant.

    The explicit mapping is attached to the Receiving cabinet snapshot, not
    manufactured as a new/derived part. Height is the nominal physical plate
    dimension, NOT the height of the 1100-mm upper door or the full cabinet.
    """
    data = dict(snapshot or {})
    if str(data.get("model") or "").strip() not in RECEIVING_FAMILIES:
        return None
    config = data.get("receiving_base_plate")
    if config is None:
        return None
    if not isinstance(config, Mapping):
        raise ValueError("RECEIVING_BASE_PLATE_CONFIG_INVALID")
    missing = tuple(key for key in _REQUIRED if key not in config)
    if missing:
        raise ValueError("RECEIVING_BASE_PLATE_CONFIG_INCOMPLETE: " + ",".join(missing))
    pattern = str(config["pattern"] or "").strip()
    if pattern not in RECEIVING_BASE_PATTERNS:
        raise ValueError("RECEIVING_BASE_PLATE_PATTERN_INVALID")
    values = {}
    for key in _REQUIRED[1:]:
        try:
            value = float(config[key])
        except (ValueError, TypeError) as exc:
            raise ValueError("RECEIVING_BASE_PLATE_CONFIG_INVALID: " + key) from exc
        if not isfinite(value):
            raise ValueError("RECEIVING_BASE_PLATE_CONFIG_INVALID: " + key)
        values[key] = value
    if values["height"] <= 0 or values["bend"] <= 0:
        raise ValueError("RECEIVING_BASE_PLATE_CONFIG_INVALID: dimensions")
    values["receiving_bend_pattern"] = pattern
    return {
        "h": values["height"],
        "base_plate_shrink_top": values["shrink_top"],
        "base_plate_shrink_bottom": values["shrink_bottom"],
        "base_plate_shrink_left": values["shrink_left"],
        "base_plate_shrink_right": values["shrink_right"],
        "base_plate_bend": values["bend"],
        "receiving_bend_pattern": pattern,
    }


def receiving_base_plate_blank_dimensions(snapshot):
    """Physical unfolded envelope from ONE canonical structural formula."""
    override = receiving_base_plate_values(snapshot)
    if override is None:
        return None
    data = dict(snapshot or {})
    result = build_receiving_base_plate_result(
        w=float(data["w"]), h=override["h"], t=float(data["t"]),
        shrink_top=override["base_plate_shrink_top"],
        shrink_bottom=override["base_plate_shrink_bottom"],
        shrink_left=override["base_plate_shrink_left"],
        shrink_right=override["base_plate_shrink_right"],
        bend=override["base_plate_bend"],
        pattern=override["receiving_bend_pattern"],
    )
    return float(result.width), float(result.height)
