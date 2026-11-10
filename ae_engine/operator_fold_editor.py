# -*- coding: utf-8 -*-
"""Headless Engine owner of Fold Editor source commits and symmetry targets.

The operator enters outside lengths and angles. Material Fold rows and physical
pairing follow the existing BoxBody canonical adjacent-BEND/T policy; Tk owns
only widget values, labels and event dispatch.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import Mapping, Sequence

from .box_body_fold_profile import apply_outside_dimension_compensation, _num
from .box_body_editor_readback import box_body_ui_segment_length_to_material, can_remove_box_body_fold_segment
from .endcap_xy_readback import fold_material_segment_outside_length


def _finite_operator_fold_number(raw, *, field):
    """Preserve real numeric Fold input; never reinterpret invalid as zero."""
    if isinstance(raw, bool):
        raise ValueError(f"FOLD_EDITOR_SOURCE_INVALID:{field}")
    try:
        number = float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"FOLD_EDITOR_SOURCE_INVALID:{field}") from exc
    if not isfinite(number):
        raise ValueError(f"FOLD_EDITOR_SOURCE_INVALID:{field}")
    return raw if type(raw) in (int, float) else number


def _positive_fold_thickness(raw):
    """One physical T source gate shared by all Fold edit transactions."""
    physical_t = _finite_operator_fold_number(raw, field="thickness")
    if physical_t <= 0:
        raise ValueError("FOLD_EDITOR_SOURCE_INVALID:thickness")
    return physical_t


def require_operator_fold_editor_profile_target(
    profiles: Mapping[str, object], requested: object,
) -> str:
    """Qualify the exact physical Fold axis before any operator edit.

    A stale notebook label may fall back to X for *display*, but an edit must
    never write X when the operator selected a missing Y/custom axis.  Only a
    real, exactly named profile can receive a source transaction.
    """
    if (
        not isinstance(profiles, Mapping)
        or type(requested) is not str
        or not requested
        or requested not in profiles
        or not isinstance(profiles[requested], (list, tuple))
    ):
        raise ValueError("FOLD_EDITOR_PROFILE_TARGET_INVALID")
    return requested


def normalize_operator_fold_editor_control(raw, *, field):
    """Public Engine parser for the legacy whole-mm Fold editor controls.

    Use the same round-to-integer convention as the old UI on valid inputs,
    but never turn a malformed length or angle into a fabricated zero.
    """
    if field not in ("len", "angle"):
        raise ValueError("FOLD_EDITOR_CONTROL_FIELD_INVALID")
    return int(round(_finite_operator_fold_number(raw, field=field)))


def project_operator_fold_editor_angle(raw):
    """Project the legacy Fold Editor +/-90 orientation using Engine authority.

    This is deliberately involutive: the same operation translates saved
    Engine angles to GUI display and GUI input back to Engine. Malformed,
    boolean or non-finite values must not become fabricated zero-degree bends.
    """
    angle = float(_finite_operator_fold_number(raw, field="angle"))
    projected = -angle if angle in (90.0, -90.0) else angle
    return int(projected) if projected.is_integer() else projected


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
    physical_t = _positive_fold_thickness(thickness)
    topology: list[dict] = []
    for row in edits:
        seg = {"len": 0}
        if "angle" in row:
            engine_angle = project_operator_fold_editor_angle(row["angle"])
            seg["angle"] = engine_angle
        topology.append(seg)
    apply_outside_dimension_compensation(topology, physical_t)

    new_segments: list[dict] = []
    for index, row in enumerate(edits):
        old = source[index] if index < len(source) else {}
        ui_length = _finite_operator_fold_number(row["len"], field="len")
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

    apply_outside_dimension_compensation(new_segments, physical_t)
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
    resolve_legacy_position: bool = False,
) -> OperatorFoldMirrorPlan:
    """Select the semantic or legacy mirror position inside the Engine.

    Old clients may still request an explicit structural veto and handle
    unkeyed fallback themselves. New GUI callers opt into a fully resolved
    legacy positional plan so they never call the old BendingUI manufacturing
    save. The original valid mirror indices remain unchanged.
    """
    # A boolean, negative Python index, stale row or unknown control field
    # must never select a different physical Fold segment for mirroring.
    rows = tuple(segments)
    if (
        type(source_index) is not int
        or not 0 <= source_index < len(rows)
        or type(field) is not str
        or field not in ("len", "angle")
        or any(not isinstance(row, Mapping) for row in rows)
    ):
        raise ValueError("FOLD_EDITOR_MIRROR_TARGET_INVALID")

    def legacy_target():
        index = (
            len(rows) - 1 - source_index
            if field == "len" else len(rows) - 2 - source_index
        )
        return index if 0 <= index < len(rows) and index != source_index else None

    if not is_box_body:
        if resolve_legacy_position:
            return OperatorFoldMirrorPlan(legacy_target(), True)
        return OperatorFoldMirrorPlan(None, False)

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

    # A keyed potential target must never be replaced by positional guessing.
    # With resolve_legacy_position, the Engine supplies the SAME index that
    # the old BendingUI used when both rows are eligible for legacy mirroring.
    legacy_index = legacy_target()
    if legacy_index is not None:
        other_key = str(rows[legacy_index].get("phase6_key") or "")
        if other_key:
            return OperatorFoldMirrorPlan(None, True)
    if resolve_legacy_position:
        return OperatorFoldMirrorPlan(legacy_index, True)
    return OperatorFoldMirrorPlan(None, False)

def operator_fold_editor_add_segment(
    segments: Sequence[Mapping[str, object]], position: int, thickness: float,
) -> list[dict]:
    """Extend the material Fold chain using existing editor entry semantics.

    The public caller supplies only a front/back action and actual sheet T.
    Never persist a bool/nonfinite T in a physical Fold, or let the legacy
    compensation calculation silently replace malformed T with 0.
    """
    if type(position) is not int:
        raise ValueError("FOLD_EDITOR_SOURCE_INVALID:position")
    physical_t = _positive_fold_thickness(thickness)
    updated = deepcopy(list(segments))
    if position == 0:
        updated.insert(0, {"angle": 90, "len": 50, "ui_len_add": physical_t})
    else:
        if updated:
            updated[-1]["angle"] = -90
        updated.append({"len": 50})
    apply_outside_dimension_compensation(updated, physical_t)
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
    if type(index) is not int or not 0 <= index < len(source):
        return None
    if not can_remove_box_body_fold_segment(source[index]):
        return None
    physical_t = _positive_fold_thickness(thickness)
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
    apply_outside_dimension_compensation(updated, physical_t)
    return updated


def project_operator_fold_editor_display_rows(
    material_segments: Sequence[Mapping[str, object]],
    thickness: float,
) -> tuple[Mapping[str, object], ...]:
    """Detached, read-only outside-length rows for the legacy Fold UI.

    The caller's material/profile rows must NEVER be rewritten just to render.
    Actual adjacent BENDs, not stale serialized ui_len_add, supply the same
    0/1/2-T display compensation as existing readback and manufacturing. The
    signed operator dimension is display orientation, never negative material.
    Only the view copies use the opposite UI angle convention for +/-90.
    """
    physical_t = _positive_fold_thickness(thickness)
    source_rows = []
    for material in material_segments:
        row = deepcopy(dict(material))
        # Display may discard stale ui_len_add and reconstruct actual BEND
        # compensation, but it must never invent a material length of 0
        # from an invalid source. A legacy None angle remains a flat segment.
        _finite_operator_fold_number(row.get("len"), field="len")
        if row.get("angle") is not None:
            _finite_operator_fold_number(row["angle"], field="angle")
        source_rows.append(row)
    views = apply_outside_dimension_compensation(source_rows, physical_t)
    projected = []
    for row in views:
        view = dict(row)
        length = fold_material_segment_outside_length(row)
        if _num(row.get("phase6_ui_sign", 1.0), 1.0) < 0:
            length = -length
        view["len"] = length
        if "angle" in row:
            angle = _num(row["angle"])
            if angle in (90.0, -90.0):
                angle = -angle
            view["angle"] = int(angle) if angle.is_integer() else angle
        projected.append(MappingProxyType(view))
    return tuple(projected)
