# -*- coding: utf-8 -*-
"""Physical part parent identity: Engine source-backed navigation projection.

This is a display/selection hierarchy for real part identities, not a
manufacturing authorization. Never invent a missing physical parent blank.
"""
from __future__ import annotations

import re

from .physical_part_identity import is_box_body_physical_piece_key

_TIER_BASE = re.compile(r"base_plate:nfb_layer:[01]$")
_TIER_EAR = re.compile(r"base_plate:fixing_plate:nfb_layer:([01]):(left|right)$")


def project_physical_part_navigation_rows(available_parts):
    """Return immutable (part_key, physical_parent_key | None, depth) rows.

    Existing source order, conditional root nesting and exact tier/side
    identities remain unchanged. UI decides labels, focus and rendering.
    """
    keys = tuple(
        str(key) for key in tuple(available_parts or ()) if str(key or "")
    )
    body_children = tuple(key for key in keys if is_box_body_physical_piece_key(key))
    body_set = set(body_children)
    body_present = "box_body" in keys
    fixing_children = tuple(
        key for key in keys if key.startswith("base_plate:fixing_plate:")
    )
    fixing_set = set(fixing_children)
    base_present = "base_plate" in keys
    tier_owners = {key for key in keys if _TIER_BASE.fullmatch(key)}

    def parent_for_ear(key):
        match = _TIER_EAR.fullmatch(key)
        if match:
            tier_parent = f"base_plate:nfb_layer:{match.group(1)}"
            if tier_parent in tier_owners:
                return tier_parent
        return "base_plate" if base_present else None

    rows = []
    for key in keys:
        if (body_present and key in body_set) or (
            key in fixing_set and parent_for_ear(key) is not None
        ):
            continue
        rows.append((key, None, 0))
        if body_present and key == "box_body":
            rows.extend((child, "box_body", 1) for child in body_children)
        if base_present and key == "base_plate":
            rows.extend(
                (child, "base_plate", 1)
                for child in fixing_children
                if parent_for_ear(child) == "base_plate"
            )
        if key in tier_owners:
            rows.extend(
                (child, key, 1)
                for child in fixing_children if parent_for_ear(child) == key
            )
    return tuple(rows)
