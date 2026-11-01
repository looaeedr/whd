# -*- coding: utf-8 -*-
"""Headless Engine owner of Fold Editor source commits and symmetry targets.

The operator enters outside lengths and angles. Material Fold rows and physical
pairing follow the existing BoxBody canonical adjacent-BEND/T policy; Tk owns
only widget values, labels and event dispatch.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Mapping, Sequence

from .box_body_fold_profile import apply_outside_dimension_compensation
from .box_body_editor_readback import box_body_ui_segment_length_to_material, can_remove_box_body_fold_segment


def commit_operator_fold_editor_rows(
    old_segments: Sequence[Mapping[str, object]],
    operator_rows: Sequence[Mapping[str, object]],
    thickness: float,
) -> list[dict]:
    """Return fresh material Fold rows for one confirmed operator editor edit.

    Angle controls use the established GUI +/-90 convention; topology is
    converted first, so simultaneous angle and outside-length edits use the
    NEW adjacent real BEND count. No caller input is mutated.
    """
    source = tuple(old_segments)
    edits = tuple(operator_rows)
    topology: list[dict] = []
    for row in edits:
        seg = {"len": 0}
        if "angle" in row:
            ui_angle = row["angle"]
            engine_angle = -ui_angle if ui_angle in (90, -90) else ui_angle
            seg["angle"] = engine_angle
        topology.append(seg)
    apply_outside_dimension_compensation(topology, thickness)

    new_segments: list[dict] = []
    for index, row in enumerate(edits):
        old = source[index] if index < len(source) else {}
        ui_length = row["len"]
        conversion = dict(old)
        conversion["ui_len_add"] = topology[index].get("ui_len_add", 0)
        length = box_body_ui_segment_length_to_material(
            conversion, abs(ui_length),
        )
        segment = {"len": length}
        if "phase6_ui_sign" in old or ui_length < 0:
            segment["phase6_ui_sign"] = -1.0 if ui_length < 0 else 1.0
        if "angle" in topology[index]:
            segment["angle"] = topology[index]["angle"]
        for key in ("core", "phase6_key"):
            if key in old:
                segment[key] = old[key]
        new_segments.append(segment)

    apply_outside_dimension_compensation(new_segments, thickness)
    return new_segments


@dataclass(frozen=True)
class OperatorFoldMirrorPlan:
    """Pair index or explicit structural veto of legacy positional mirroring."""

    target_index: int | None
    block_legacy_fallback: bool


_BOX_BODY_MIRROR_PAIRS = {
    "zl1": "zr1", "zr1": "zl1",
    "zl2": "zr2", "zr2": "zl2",
    "fw_left": "fw_right", "fw_right": "fw_left",
    "d_left": "d_right", "d_right": "d_left",
    "w": "w",
}


def plan_operator_fold_mirror_target(
    segments: Sequence[Mapping[str, object]],
    source_index: int,
    field: str,
    *,
    is_box_body: bool,
) -> OperatorFoldMirrorPlan:
    """Select an actual keyed structural counterpart, never an arbitrary FW.

    Non-BoxBody or genuinely unkeyed rows retain the existing original
    BendingUI positional-mirror behavior. Keyed BoxBody rows can only mirror
    known source-matched pair identities; absent matches do not fall back.
    """
    if not is_box_body:
        return OperatorFoldMirrorPlan(None, False)

    rows = tuple(segments)
    source_key = str(rows[source_index].get("phase6_key") or "")
    target_index = None
    if source_key in _BOX_BODY_MIRROR_PAIRS:
        if field == "len":
            mirror_key = _BOX_BODY_MIRROR_PAIRS[source_key]
            target_index = next(
                (i for i, row in enumerate(rows)
                 if str(row.get("phase6_key") or "") == mirror_key),
                None,
            )
        elif field == "angle" and source_index + 1 < len(rows):
            next_key = str(rows[source_index + 1].get("phase6_key") or "")
            if next_key in _BOX_BODY_MIRROR_PAIRS:
                mirror_left = _BOX_BODY_MIRROR_PAIRS[next_key]
                mirror_right = _BOX_BODY_MIRROR_PAIRS[source_key]
                target_index = next(
                    (
                        i for i in range(len(rows) - 1)
                        if str(rows[i].get("phase6_key") or "") == mirror_left
                        and str(rows[i + 1].get("phase6_key") or "") == mirror_right
                    ),
                    None,
                )
        return OperatorFoldMirrorPlan(target_index, True)

    # Only genuinely unkeyed source/target rows may use old positional mirror.
    legacy_index = (
        len(rows) - 1 - source_index
        if field == "len" else len(rows) - 2 - source_index
    )
    if 0 <= legacy_index < len(rows):
        other_key = str(rows[legacy_index].get("phase6_key") or "")
        if other_key:
            return OperatorFoldMirrorPlan(None, True)
    return OperatorFoldMirrorPlan(None, False)

def operator_fold_editor_add_segment(
    segments: Sequence[Mapping[str, object]], position: int, thickness: float,
) -> list[dict]:
    """Extend the material Fold chain using existing editor entry semantics."""
    updated = deepcopy(list(segments))
    if position == 0:
        updated.insert(0, {"angle": 90, "len": 50, "ui_len_add": thickness})
    else:
        if updated:
            updated[-1]["angle"] = -90
        updated.append({"len": 50})
    apply_outside_dimension_compensation(updated, thickness)
    return updated


def operator_fold_editor_remove_segment(
    segments: Sequence[Mapping[str, object]],
    index: int,
    thickness: float,
    *,
    symmetric_box_body: bool = False,
) -> list[dict] | None:
    """Remove optional Fold rows, honoring real keyed symmetric counterparts.

    Return None for invalid/protected edits. Never alter caller-owned profiles.
    All adjacent-BEND T compensation uses the existing canonical Engine rule.
    """
    source = tuple(segments)
    if not isinstance(index, int) or not 0 <= index < len(source):
        return None
    if not can_remove_box_body_fold_segment(source[index]):
        return None
    targets = [index]
    if symmetric_box_body:
        source_key = str(source[index].get("phase6_key") or "")
        partner = None
        if source_key in _BOX_BODY_MIRROR_PAIRS:
            other_key = _BOX_BODY_MIRROR_PAIRS[source_key]
            partner = next(
                (i for i, row in enumerate(source)
                 if str(row.get("phase6_key") or "") == other_key),
                None,
            )
        elif not source_key:
            candidate = len(source) - 1 - index
            if (
                0 <= candidate < len(source)
                and not str(source[candidate].get("phase6_key") or "")
            ):
                partner = candidate
        # A keyed row with no matching semantic mate is never mirrored by index.
        if partner is not None and partner != index:
            if not can_remove_box_body_fold_segment(source[partner]):
                return None
            targets.append(partner)
    updated = deepcopy(list(source))
    for target in sorted(set(targets), reverse=True):
        updated.pop(target)
    if updated:
        updated[-1].pop("angle", None)
    apply_outside_dimension_compensation(updated, thickness)
    return updated
