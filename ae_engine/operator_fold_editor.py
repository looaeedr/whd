# -*- coding: utf-8 -*-
"""Headless Engine owner for operator Fold-editor save conversion.

UI supplies typed rows; canonical material spans, angles and live BEND
adjacency belong to Engine. No Tk/Phase6/renderer dependencies.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from .box_body_fold_profile import apply_outside_dimension_compensation
from .box_body_editor_readback import box_body_ui_segment_length_to_material


def _operator_angle_to_engine(value: object) -> int | float:
    """Preserve the existing operator ↔ material bend sign convention."""
    angle = float(value)
    if angle in (90.0, -90.0):
        angle = -angle
    return int(angle) if angle.is_integer() else angle


def operator_fold_editor_save_segments(
    old_segments: Sequence[Mapping[str, object]],
    edited_rows: Sequence[Mapping[str, object]],
    thickness: float,
) -> list[dict[str, object]]:
    """Resolve edited outside dimensions against the *new* physical topology.

    No saved ``ui_len_add`` is trusted: the BEND count is recomputed from
    edited angles before material conversion. Signed operator lengths express
    direction only; material spans stay nonnegative. Historical core/key
    identities are preserved without creating missing physical parts.
    """
    previous = tuple(old_segments)
    edited = tuple(edited_rows)
    topology = []
    for row in edited:
        seg: dict[str, object] = {"len": 0}
        if "angle" in row:
            seg["angle"] = _operator_angle_to_engine(row["angle"])
        topology.append(seg)
    apply_outside_dimension_compensation(topology, thickness)

    resolved: list[dict[str, object]] = []
    for index, row in enumerate(edited):
        old = previous[index] if index < len(previous) else {}
        ui_length = int(row["len"])
        conversion = dict(old)
        conversion["ui_len_add"] = topology[index].get("ui_len_add", 0)
        material_length = box_body_ui_segment_length_to_material(
            conversion, abs(ui_length)
        )
        segment: dict[str, object] = {"len": material_length}
        if "phase6_ui_sign" in old or ui_length < 0:
            segment["phase6_ui_sign"] = -1.0 if ui_length < 0 else 1.0
        if "angle" in topology[index]:
            segment["angle"] = topology[index]["angle"]
        for key in ("core", "phase6_key"):
            if key in old:
                segment[key] = old[key]
        resolved.append(segment)
    apply_outside_dimension_compensation(resolved, thickness)
    return resolved
