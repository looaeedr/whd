"""Public Hole Editor feature-rotation operations over canonical Engine semantics.

The GUI owns button labels, selection and undo; the Engine alone qualifies
rotation source and returns a detached, validated physical Feature candidate.
"""
from __future__ import annotations

import re
from dataclasses import replace

from .sheetmetal_feature_core import (
    CircleFeature, ProfileFeature, RectFeature, _normalize_rotation,
)


def operator_hole_rotation_from_control(raw: object) -> int:
    """Accept a Hole Editor operator angle without lossy GUI int() casts.

    The original UI presents 90°/180°/270°/360° and stores a numeric
    rotation on a physical Feature. Use the existing Engine four-angle gate,
    including its 360°=0° convention. Strings are the GUI display adapter
    only; do not admit fractional, boolean, nonfinite or malformed strings.
    """
    if isinstance(raw, str):
        token = raw.strip()
        if token.endswith("°"):
            token = token[:-1].strip()
        if re.fullmatch(r"[+-]?[0-9]+", token) is None:
            raise ValueError("rotation must be 0/90/180/270/360 degrees")
        return _normalize_rotation(int(token))
    return _normalize_rotation(raw)


def operator_hole_feature_with_rotation(feature: object, raw_angle: object):
    """Pure candidate rotation for the same physical Hole Feature as DXF.

    Session selection, surface containment, Confirm All and Save→Reload
    remain their existing owners. No mutation on invalid source.
    """
    if not isinstance(feature, (CircleFeature, RectFeature, ProfileFeature)):
        raise ValueError("Hole Editor feature type is unsupported")
    angle = operator_hole_rotation_from_control(raw_angle)
    return replace(feature, rotation_deg=angle)
