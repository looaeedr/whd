# -*- coding: utf-8 -*-
"""Engine-owned classification of existing persisted physical part identities.

No new IDs are allocated and recognition does not confer DXF capability.
"""
from __future__ import annotations

import re


def is_box_body_physical_piece_key(value: object) -> bool:
    """Classify manufacturing-owned BoxBody child identities only."""
    key = str(value or "")
    return key.startswith("box_body:") and not key.startswith("box_body:divider:")


def is_derived_physical_part_key(value: object) -> bool:
    key = str(value or "")
    return (
        re.fullmatch(r"door_c\d+_r\d+", key) is not None
        or re.fullmatch(r"base_plate_c\d+_r\d+", key) is not None
        or key.startswith("base_plate:fixing_plate:")
        or key.startswith("base_plate:nfb_layer:")
        or key.startswith("nfb_pad:")
        or is_box_body_physical_piece_key(key)
        or key.startswith("box_body:divider:")
        or (key.startswith("inner_door:") and key.endswith("_frame"))
        or (key.startswith("inner_door:") and key.endswith(":panel"))
    )


def door_display_part_role(value: object) -> str:
    """Canonical persisted Door/panel identity for 3D presentation, not release.

    Display opacity and true CUTTING hole-rim visibility may depend on this
    immutable physical identity. A lookalike name must not be a Door sheet.
    """
    key = str(value or "")
    if key == "door" or re.fullmatch(r"door_c\d+_r\d+", key) is not None:
        return "outer"
    if key.startswith("inner_door:") and key.endswith(":panel"):
        return "inner"
    return "other"
