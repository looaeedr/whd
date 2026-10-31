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



def reverse_box_body_fold_traversal(rows):
    """Reverse a fold chain while moving bend ownership to the same boundary."""
    source = deepcopy(list(tuple(rows or ())))
    result = []
    total = len(source)
    for index, source_row in enumerate(reversed(source)):
        row = {k: v for k, v in source_row.items() if k != "angle"}
        owner_index = total - 2 - index
        if owner_index >= 0 and "angle" in source[owner_index]:
            row["angle"] = float(source[owner_index]["angle"])
        result.append(row)
    if result:
        result[-1].pop("angle", None)
    return result


def box_body_piece_editor_profiles(
    render_data, snapshot=None
) -> dict[str, dict[str, list[dict[str, object]]]]:
    """Project manufacturing pieces into operator-facing physical-child profiles.

    Material lengths remain authoritative.  The adapter only changes traversal
    and signed operator presentation: Receiving right-side editing is front→rear
    while manufacturing keeps its local rear→front chain; Receiving zl1 may carry
    a negative operator direction without ever making material length negative.
    """
    source_snapshot = dict(snapshot or {})
    result = {}
    for piece in tuple(getattr(render_data, "pieces", ()) or ()):
        role = str(getattr(piece, "role", "") or "").strip()
        if not role:
            continue
        key = f"box_body:{role}"
        rows = [
            {
                "len": float(row.length),
                **({"angle": float(row.angle)} if row.angle is not None else {}),
                **({"core": row.core} if getattr(row, "core", None) else {}),
                "phase6_key": str(getattr(row, "phase6_key", "") or ""),
            }
            for row in tuple(getattr(piece, "fold_profile", ()) or ())
        ]
        if role == "right_side":
            rows = reverse_box_body_fold_traversal(rows)
        # Legacy mirrored Receiving panels are supported for readback only.
        # New Receiving geometry uses the original pre-DXF source order
        # zl1/zl2/FW/D/rear, without this inverse or any re-mirroring.
        # Keep operator dimensions unchanged on both code paths.
        if role == "left_side" and tuple(row.get("phase6_key") for row in rows) == (
            "zl1", "d_left", "fw_left", "zl2", "side_rear_bend_left",
        ):
            a, new_d, fw, new_b, rear = [float(row["len"]) for row in rows]
            b = new_b - a + rear
            original_d = a + new_d + fw + new_b + rear - a - b - fw - rear
            if b <= 0 or original_d <= 0:
                raise ValueError("RECEIVING_LEFT_SIDE_OPERATOR_INVERSE_INVALID")
            by_key = {row["phase6_key"]: dict(row) for row in rows}
            rows = [
                dict(by_key["zl1"], len=a),
                dict(by_key["zl2"], len=b),
                dict(by_key["fw_left"], len=fw),
                dict(by_key["d_left"], len=original_d),
                dict(by_key["side_rear_bend_left"], len=rear),
            ]
        if role == "left_side" and float(source_snapshot.get("zl1", 0.0) or 0.0) < 0.0:
            for row in rows:
                if str(row.get("phase6_key") or "") == "zl1":
                    row["phase6_ui_sign"] = -1.0
                    break
        result[key] = {
            "X": rows,
            "Y": [{
                "len": float(piece.material_dimensions[1]),
                "phase6_key": "box_body_piece_height",
            }],
        }
    return result


