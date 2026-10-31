# -*- coding: utf-8 -*-
"""Engine authority for BoxBody Fold edit/readback and formed-FW witnesses.

Preserves existing canonical Family and 1T-per-adjacent-real-BEND policy.
Formed FW is only assembly/collision evidence, never CUTTING oracle.
"""
from __future__ import annotations
from collections.abc import Mapping, Sequence
from copy import deepcopy

from .cabinet_types import policy as cabinet_family_policy
from .box_body_fold_profile import (
    _num, _ui_len, _common_dimension_len,
    apply_outside_dimension_compensation,
)
from .endcap_xy_readback import fold_material_segment_outside_length


def _signed_like(original, magnitude):
    return -abs(magnitude) if _num(original) < 0 else abs(magnitude)


def formed_box_body_fw_widths(profile: Sequence[Mapping[str, object]], thickness) -> tuple[float | None, float | None]:
    """Return formed left/right Box Body FW outside widths from the actual fold topology.

    ``len`` is the flat/material FW.  Assembly insertion clearance must use the
    formed outside occupation, so adjacent real bends contribute their actual
    thickness compensation.  Recompute that compensation from the current
    profile instead of trusting stale saved ``ui_len_add`` metadata.
    """
    rows = apply_outside_dimension_compensation(deepcopy(list(profile)), thickness)
    by_key = {str(seg.get("phase6_key") or ""): seg for seg in rows}
    def one(key):
        seg = by_key.get(key)
        if seg is None:
            return None
        return abs(_num(seg.get("len"))) + abs(_num(seg.get("ui_len_add")))
    return one("fw_left"), one("fw_right")


def box_body_ui_segment_length_to_material(seg: Mapping[str, object], ui_value):
    """Convert an operator outside dimension back to the Renderer span."""
    return _ui_len(max(0.0, _num(ui_value) - _num(seg.get("ui_len_add"))))

def read_box_body_outside_dimensions(profile: Sequence[Mapping[str, object]], original: Mapping[str, object]) -> dict:
    """Convert known Phase6 positions back while allowing extra outer folds."""
    by_key = {str(seg.get("phase6_key")): seg for seg in profile if seg.get("phase6_key")}
    d_segments = [seg for seg in profile if seg.get("core") == "D"]
    w_segments = [seg for seg in profile if seg.get("core") == "W"]
    if len(d_segments) != 2 or len(w_segments) != 1:
        raise ValueError("中央三段必須固定為 D-W-D")

    core_length = lambda seg: _common_dimension_len(original, _num(seg.get("len")) + _num(seg.get("ui_len_add")))
    d_left = core_length(d_segments[0])
    d_right = core_length(d_segments[1])
    if d_left != d_right:
        raise ValueError("D-W-D 的兩個 D 必須相同")
    w_value = core_length(w_segments[0])

    material_profile = cabinet_family_policy.box_body_profile_uses_outside_dimensions(original)
    fw_left_seg = by_key.get("fw_left")
    fw_right_seg = by_key.get("fw_right")
    if fw_left_seg is not None and fw_right_seg is not None:
        fw_left = fold_material_segment_outside_length(fw_left_seg) if material_profile else _ui_len(fw_left_seg.get("len"))
        fw_right = fold_material_segment_outside_length(fw_right_seg) if material_profile else _ui_len(fw_right_seg.get("len"))
        if fw_left != fw_right:
            raise ValueError("左右 FW 必須相同")
        fw_value = fw_left
    elif fw_left_seg is not None:
        fw_value = fold_material_segment_outside_length(fw_left_seg) if material_profile else _ui_len(fw_left_seg.get("len"))
    elif fw_right_seg is not None:
        fw_value = fold_material_segment_outside_length(fw_right_seg) if material_profile else _ui_len(fw_right_seg.get("len"))
    else:
        fw_value = _ui_len(original.get("fw"))

    def known_len(key, fallback):
        seg = by_key.get(key)
        if seg is None:
            return _ui_len(fallback)
        return fold_material_segment_outside_length(seg) if material_profile else _ui_len(seg.get("len"))

    return {
        "zl1": _signed_like(original.get("zl1"), known_len("zl1", original.get("zl1"))),
        "zl2": known_len("zl2", original.get("zl2")),
        "fw": fw_value,
        "d": d_left,
        "w": w_value,
        "zr2": known_len("zr2", original.get("zr2")),
        "zr1": _signed_like(original.get("zr1"), known_len("zr1", original.get("zr1"))),
    }

def can_remove_box_body_fold_segment(segment: Mapping[str, object]) -> bool:
    """Keep D/W core and the two global FW fields structurally present."""
    if segment.get("core"):
        return False
    return str(segment.get("phase6_key") or "") not in {"fw_left", "fw_right"}

