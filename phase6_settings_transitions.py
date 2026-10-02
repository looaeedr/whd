# -*- coding: utf-8 -*-
"""Pure Phase 4 Settings transition kernel.

This module owns Settings semantic calculations only. It has no Tk, GUI,
bridge, workspace, callback, scheduler, or renderer ownership.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.assembly_joint import (
    set_part_edge_relation,
    sync_snapshot_intent_joints,
)
from ae_engine.sheetmetal_geometry import (
    CornerDirection,
    CornerTypeId,
    CornerTypeSelection,
    CrossCornerMode,
)
from phase6_box_body_structure import (
    BoxBodyStructureType,
    reconcile_box_body_structure_for_total_w_change,
    activate_structure_with_defaults,
    set_join_seam_bend,
    set_side_back_geometry,
    set_structure_locked,
    set_three_piece_width,
    set_two_piece_width,
    update_structure_config,
)
from phase6_endcap_semantics import (
    apply_box_assembly_type_to_raw_state,
    assembly_intent_value,
    commit_endcap_bottom_wrap,
    commit_endcap_fw,
    legacy_corner_projection_for_intent,
    normalize_endcap_bottom_wrap_state,
    resolve_endcap_bottom_wrap,
    selection_from_raw,
    selection_to_raw,
    set_endcap_fw_follow,
)
from phase6_settings_center import normalize_ui_text_size
from phase6_fold_profiles import _num, _ui_len


CORNER_KEYS = ("top_left", "top_right", "bottom_left", "bottom_right")
CORNER_PAIR_KEYS = {
    "top": ("top_left", "top_right"),
    "bottom": ("bottom_left", "bottom_right"),
}


@dataclass(frozen=True)
class SettingsCommitTransition:
    settings_values: dict[str, object]
    input_snapshot: dict[str, object]
    box_whd: dict[str, object]
    committed: dict[str, object]


@dataclass(frozen=True)
class BottomWrapTransition:
    state: dict[str, object]
    resolved: dict[str, object]


@dataclass(frozen=True)
class CornerStateTransition:
    corner_state: dict[str, object]
    corner_pair_same: dict[str, object]
    value: object = None


@dataclass(frozen=True)
class AssemblyIntentTransition:
    input_snapshot: dict[str, object]
    corner_state: dict[str, object]
    corner_pair_same: dict[str, object]
    assembly_type: object


@dataclass(frozen=True)
class ExternalSyncPlan:
    accepted: bool
    revision: int
    transaction_id: str
    settings: dict[str, object]
    reason: str


@dataclass(frozen=True)
class ExternalModelPlan:
    changed: bool
    target_model: str


@dataclass(frozen=True)
class FamilyModelTransition:
    new_model: str
    old_model: str
    editable: bool
    defaults: dict[str, object]
    family_values: dict[str, object]
    assembly_type: object
    structure_state: dict[str, object] | None
    remember_non_receiving_structure: dict[str, object] | None


@dataclass(frozen=True)
class FamilyModelPlan:
    input_snapshot: dict[str, object]
    corner_state: dict[str, object]
    corner_pair_same: dict[str, object]
    endcap_bottom_wrap_state: dict[str, object]
    assembly_type: object
    desired_structure: dict[str, object] | None
    transition: FamilyModelTransition


def normalize_assembly_type(value: object) -> object:
    stable = assembly_intent_value(value)
    return stable if stable == "WRAP_OVERLAY" else CornerTypeId(stable)


def normalize_updates(
    settings_values: Mapping[str, object],
    updates: Mapping[str, object] | None,
    *,
    external_apply_guard: bool = False,
) -> dict[str, object]:
    clean: dict[str, object] = {}
    for key, raw in dict(updates or {}).items():
        if key not in settings_values:
            continue
        if key == "ui_text_size":
            value: object = normalize_ui_text_size(raw)
        elif isinstance(settings_values.get(key), bool):
            value = bool(raw)
        else:
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
        if external_apply_guard and settings_values.get(key) == value:
            continue
        clean[key] = value
    return clean


def commit_settings(
    settings_values: Mapping[str, object],
    input_snapshot: Mapping[str, object],
    box_whd: Mapping[str, object],
    values: Mapping[str, object] | None,
) -> SettingsCommitTransition:
    next_settings = deepcopy(dict(settings_values))
    next_snapshot = deepcopy(dict(input_snapshot))
    next_box = deepcopy(dict(box_whd))
    committed = deepcopy(dict(values or {}))
    if not committed:
        return SettingsCommitTransition(
            next_settings, next_snapshot, next_box, committed
        )

    next_settings.update(committed)
    next_snapshot.update(committed)
    if "ui_text_size" in committed:
        normalized = normalize_ui_text_size(committed["ui_text_size"])
        next_settings["ui_text_size"] = normalized
        next_snapshot["ui_text_size"] = normalized
        committed["ui_text_size"] = normalized
    for key in ("w", "h", "d"):
        if key in committed:
            next_box[key] = _ui_len(committed[key])
    return SettingsCommitTransition(
        next_settings, next_snapshot, next_box, committed
    )


def toggle_box_structure_lock(state: Mapping[str, object]) -> dict:
    return set_structure_locked(
        state, not bool(dict(state).get("locked", True))
    )


def activate_box_structure(
    state: Mapping[str, object],
    type_id: object,
    total_w: float,
) -> dict:
    return activate_structure_with_defaults(state, type_id, total_w)


def apply_box_structure_numeric(
    state: Mapping[str, object],
    type_id: object,
    field: str,
    value: float,
    *,
    total_w: float,
    outside_family: bool = False,
) -> dict:
    kind = BoxBodyStructureType(type_id)
    field = str(field)
    value = float(value)
    if (
        kind is BoxBodyStructureType.TWO_PIECE_W_SPLIT
        and field in {"left", "right"}
    ):
        return set_two_piece_width(state, total_w, field, value)
    if (
        kind is BoxBodyStructureType.THREE_PIECE_W_SPLIT
        and field in {"left", "middle", "right"}
    ):
        return set_three_piece_width(state, total_w, field, value)
    if field == "seam_bend":
        return set_join_seam_bend(state, kind, value)
    if (
        kind is BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT
        and field == "side_rear_bend"
    ):
        return set_side_back_geometry(
            state,
            side_rear_bend=value,
            side_rear_bend_dimension_space=(
                "OUTSIDE" if outside_family else None
            ),
        )
    if (
        kind is BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT
        and field == "back_width_comp_t"
    ):
        return set_side_back_geometry(state, back_width_comp_t=value)
    if field in {
        "endcap_extra_relief",
        "endcap_single_side_meat_t",
        "baseplate_relief_length",
        "baseplate_single_side_meat_t",
    } and value < 0:
        raise ValueError("截角／避讓參數不得小於 0")
    return update_structure_config(state, kind, {field: value})


def reconcile_width_structure(
    state: Mapping[str, object],
    new_w: float,
) -> dict:
    return reconcile_box_body_structure_for_total_w_change(
        state, float(new_w)
    )


def endcap_fw_follow(
    input_snapshot: Mapping[str, object],
    settings_values: Mapping[str, object],
    endcap_fw_state: Mapping[str, object],
    part_key: str,
    follow_box: bool,
) -> dict:
    snapshot = deepcopy(dict(input_snapshot))
    snapshot.update(deepcopy(dict(settings_values)))
    state = deepcopy(dict(endcap_fw_state or {}))
    set_endcap_fw_follow(
        state,
        str(part_key),
        bool(follow_box),
        box_fw=_num(snapshot.get("fw", 25), 25),
    )
    return state


def endcap_fw_override(
    input_snapshot: Mapping[str, object],
    settings_values: Mapping[str, object],
    endcap_fw_state: Mapping[str, object],
    part_key: str,
    value: object,
) -> dict:
    snapshot = deepcopy(dict(input_snapshot))
    snapshot.update(deepcopy(dict(settings_values)))
    state = deepcopy(dict(endcap_fw_state or {}))
    commit_endcap_fw(
        state,
        str(part_key),
        _num(value),
        box_fw=_num(snapshot.get("fw", 25), 25),
    )
    return state


def bottom_wrap(
    input_snapshot: Mapping[str, object],
    endcap_bottom_wrap_state: Mapping[str, object] | None,
    part_key: str,
    *,
    reserve_u: float,
    reserve_v: float,
) -> BottomWrapTransition:
    snapshot = deepcopy(dict(input_snapshot))
    state = deepcopy(dict(endcap_bottom_wrap_state or {}))
    if not state:
        state.update(normalize_endcap_bottom_wrap_state(snapshot))
    commit_endcap_bottom_wrap(
        state,
        str(part_key),
        reserve_u=float(reserve_u),
        reserve_v=float(reserve_v),
    )
    snapshot["endcap_bottom_wrap"] = deepcopy(state)
    resolved = resolve_endcap_bottom_wrap(
        snapshot,
        str(part_key),
        state=state,
    )
    return BottomWrapTransition(
        state=deepcopy(state),
        resolved=deepcopy(resolved),
    )


def endcap_edge_relation(
    input_snapshot: Mapping[str, object],
    part_key: str,
    edge: str,
    relation: object,
) -> dict:
    return set_part_edge_relation(
        deepcopy(dict(input_snapshot)),
        str(part_key),
        str(edge).upper(),
        relation,
    )


def ensure_corner_part(
    corner_state: Mapping[str, object] | None,
    corner_pair_same: Mapping[str, object] | None,
    part_key: str,
) -> CornerStateTransition:
    all_state = deepcopy(dict(corner_state or {}))
    all_pairs = deepcopy(dict(corner_pair_same or {}))
    part = str(part_key)
    state = all_state.setdefault(part, {})
    for corner_key in CORNER_KEYS:
        state[corner_key] = selection_to_raw(
            selection_from_raw(state.get(corner_key))
        )
    pairs = all_pairs.setdefault(part, {})
    pairs.setdefault("top", True)
    pairs.setdefault("bottom", True)
    return CornerStateTransition(all_state, all_pairs, deepcopy(state))


def corner_selection(
    part_state: Mapping[str, object],
    pairs: Mapping[str, object],
    target_key: str,
) -> CornerTypeSelection:
    del pairs
    current_key = (
        CORNER_PAIR_KEYS[target_key][0]
        if target_key in CORNER_PAIR_KEYS
        else str(target_key)
    )
    return selection_from_raw(part_state[current_key])


def corner_targets(
    pairs: Mapping[str, object],
    target_key: str,
) -> tuple[str, ...]:
    del pairs
    key = str(target_key)
    if key in CORNER_PAIR_KEYS:
        return CORNER_PAIR_KEYS[key]
    return (key,)


def commit_corner_pair(
    corner_state: Mapping[str, object] | None,
    corner_pair_same: Mapping[str, object] | None,
    part_key: str,
    pair_key: str,
    enabled: bool,
) -> CornerStateTransition:
    normalized = ensure_corner_part(
        corner_state, corner_pair_same, part_key
    )
    all_state = normalized.corner_state
    all_pairs = normalized.corner_pair_same
    state = all_state[str(part_key)]
    pairs = all_pairs[str(part_key)]
    pair = str(pair_key)
    if pair not in CORNER_PAIR_KEYS:
        raise ValueError(f"unknown corner pair: {pair}")
    pairs[pair] = bool(enabled)
    if enabled:
        left_key, right_key = CORNER_PAIR_KEYS[pair]
        state[right_key] = deepcopy(state[left_key])
    return CornerStateTransition(
        all_state, all_pairs, (deepcopy(state), deepcopy(pairs))
    )


def commit_corner_type(
    corner_state: Mapping[str, object] | None,
    corner_pair_same: Mapping[str, object] | None,
    part_key: str,
    target_key: str,
    type_id: object,
) -> CornerStateTransition:
    normalized = ensure_corner_part(
        corner_state, corner_pair_same, part_key
    )
    all_state = normalized.corner_state
    all_pairs = normalized.corner_pair_same
    state = all_state[str(part_key)]
    pairs = all_pairs[str(part_key)]
    current = corner_selection(state, pairs, target_key)
    wanted = CornerTypeId(type_id)
    selection = (
        current if current.type_id is wanted else CornerTypeSelection(wanted)
    )
    raw = selection_to_raw(selection)
    for corner_key in corner_targets(pairs, target_key):
        state[corner_key] = deepcopy(raw)
    return CornerStateTransition(all_state, all_pairs, deepcopy(raw))


def commit_corner_mode(
    corner_state: Mapping[str, object] | None,
    corner_pair_same: Mapping[str, object] | None,
    part_key: str,
    target_key: str,
    mode: object,
) -> CornerStateTransition:
    normalized = ensure_corner_part(
        corner_state, corner_pair_same, part_key
    )
    all_state = normalized.corner_state
    all_pairs = normalized.corner_pair_same
    state = all_state[str(part_key)]
    pairs = all_pairs[str(part_key)]
    current = corner_selection(state, pairs, target_key)
    if current.type_id is not CornerTypeId.CROSS:
        raw = selection_to_raw(current)
        return CornerStateTransition(all_state, all_pairs, deepcopy(raw))
    selection = CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode(mode),
    )
    raw = selection_to_raw(selection)
    for corner_key in corner_targets(pairs, target_key):
        state[corner_key] = deepcopy(raw)
    return CornerStateTransition(all_state, all_pairs, deepcopy(raw))


def commit_corner_parameters(
    corner_state: Mapping[str, object] | None,
    corner_pair_same: Mapping[str, object] | None,
    part_key: str,
    target_key: str,
    *,
    amount_t: float | None = None,
    cross_mode: object = None,
    direction: object = None,
    secondary_retain_t: float | None = None,
    secondary_depth_t: float | None = None,
) -> CornerStateTransition:
    normalized = ensure_corner_part(
        corner_state, corner_pair_same, part_key
    )
    all_state = normalized.corner_state
    all_pairs = normalized.corner_pair_same
    state = all_state[str(part_key)]
    pairs = all_pairs[str(part_key)]
    current = corner_selection(state, pairs, target_key)
    amount = current.amount_t if amount_t is None else float(amount_t)

    if current.type_id is CornerTypeId.CROSS:
        mode = (
            current.cross_mode
            if cross_mode is None
            else CrossCornerMode(cross_mode)
        )
        if mode is CrossCornerMode.STANDARD:
            selection = CornerTypeSelection(
                CornerTypeId.CROSS,
                cross_mode=mode,
            )
        else:
            selected_direction = (
                current.direction
                if direction is None
                else CornerDirection(direction)
            )
            selection = CornerTypeSelection(
                CornerTypeId.CROSS,
                cross_mode=mode,
                direction=selected_direction,
                amount_t=amount,
            )
    elif current.type_id is CornerTypeId.OVERLAY:
        selection = CornerTypeSelection(
            CornerTypeId.OVERLAY,
            amount_t=amount,
        )
    elif current.type_id is CornerTypeId.INSERT:
        selection = CornerTypeSelection(
            CornerTypeId.INSERT,
            amount_t=amount,
        )
    else:
        selection = CornerTypeSelection(
            CornerTypeId.INSERT_OVERLAY,
            amount_t=amount,
            secondary_retain_t=(
                current.secondary_retain_t
                if secondary_retain_t is None
                else float(secondary_retain_t)
            ),
            secondary_depth_t=(
                current.secondary_depth_t
                if secondary_depth_t is None
                else float(secondary_depth_t)
            ),
        )

    raw = selection_to_raw(selection)
    for corner_key in corner_targets(pairs, target_key):
        state[corner_key] = deepcopy(raw)
    return CornerStateTransition(all_state, all_pairs, deepcopy(raw))


def assembly_intent(
    input_snapshot: Mapping[str, object],
    corner_state: Mapping[str, object] | None,
    corner_pair_same: Mapping[str, object] | None,
    type_id: object,
    *,
    available_parts: tuple[object, ...] | list[object] = (),
    project_legacy_corner: bool = False,
    reset_bottom_defaults: bool = False,
) -> AssemblyIntentTransition:
    canonical = normalize_assembly_type(type_id)
    stable = assembly_intent_value(type_id)
    snapshot = deepcopy(dict(input_snapshot))
    corners = deepcopy(dict(corner_state or {}))
    pairs = deepcopy(dict(corner_pair_same or {}))
    parts = tuple(str(key) for key in tuple(available_parts or ()) if str(key))
    had_existing_parts = "existing_parts" in snapshot
    authoritative_existing_parts = deepcopy(snapshot.get("existing_parts"))
    if parts:
        # available_parts is an execution context for joint projection only.
        # The predecessor controller never promoted this temporary live
        # workspace list into authoritative project topology.
        snapshot["existing_parts"] = list(parts)
    snapshot = sync_snapshot_intent_joints(snapshot, canonical)
    if had_existing_parts:
        snapshot["existing_parts"] = authoritative_existing_parts
    else:
        snapshot.pop("existing_parts", None)
    if project_legacy_corner:
        apply_box_assembly_type_to_raw_state(
            corners,
            pairs,
            legacy_corner_projection_for_intent(stable),
            reset_bottom_defaults=bool(reset_bottom_defaults),
        )
    return AssemblyIntentTransition(
        input_snapshot=snapshot,
        corner_state=corners,
        corner_pair_same=pairs,
        assembly_type=canonical,
    )


def replace_corner_state(
    corner_state: Mapping[str, object] | None,
    corner_pair_same: Mapping[str, object] | None,
) -> CornerStateTransition:
    return CornerStateTransition(
        deepcopy(dict(corner_state or {})),
        deepcopy(dict(corner_pair_same or {})),
        None,
    )


def plan_external_sync(
    envelope: Mapping[str, object] | None,
    *,
    last_external_revision: int,
) -> ExternalSyncPlan:
    raw = dict(envelope or {})
    current_revision = int(last_external_revision or 0)
    if str(raw.get("origin") or "") != "main_gui":
        return ExternalSyncPlan(
            False, current_revision, "", {}, "WRONG_ORIGIN"
        )
    try:
        revision = int(raw.get("revision", 0) or 0)
    except (TypeError, ValueError):
        return ExternalSyncPlan(
            False, current_revision, "", {}, "INVALID_REVISION"
        )
    if revision <= current_revision:
        return ExternalSyncPlan(
            False,
            revision,
            str(raw.get("transaction_id") or ""),
            {},
            "STALE_REVISION",
        )
    transaction_id = str(raw.get("transaction_id") or "")
    delta = dict(raw.get("delta") or {})
    settings = dict(delta.get("settings") or {})
    return ExternalSyncPlan(
        True, revision, transaction_id, settings, "OK"
    )


def normalize_symmetry(value: object) -> bool:
    return bool(value)


def settings_defaults_payload(
    context: str,
    settings_values: Mapping[str, object],
    corner_state: Mapping[str, object],
    corner_pair_same: Mapping[str, object],
) -> tuple[str, dict[str, object], dict[str, object], dict[str, object]]:
    return (
        str(context),
        dict(settings_values),
        deepcopy(dict(corner_state)),
        deepcopy(dict(corner_pair_same)),
    )


def plan_external_model_change(
    model: object,
    current_model: object,
) -> ExternalModelPlan:
    target = str(model or "").strip()
    current = str(current_model or "").strip()
    return ExternalModelPlan(bool(target and target != current), target)


def apply_corner_preset(
    corner_state: Mapping[str, object] | None,
    corner_pair_same: Mapping[str, object] | None,
    fixed_corner_state: Mapping[str, object] | None,
) -> CornerStateTransition:
    next_state = deepcopy(dict(corner_state or {}))
    next_pairs = deepcopy(dict(corner_pair_same or {}))
    for part_key, corners in dict(fixed_corner_state or {}).items():
        state = next_state.setdefault(str(part_key), {})
        for corner_key, raw in dict(corners or {}).items():
            if isinstance(raw, Mapping):
                state[str(corner_key)] = selection_to_raw(
                    selection_from_raw(raw)
                )
            else:
                state[str(corner_key)] = selection_to_raw(raw)
        pairs = next_pairs.setdefault(str(part_key), {})
        pairs["top"] = True
        pairs["bottom"] = True
    return CornerStateTransition(next_state, next_pairs, None)


def family_model_transition(
    new_model: object,
    old_model: object,
    *,
    new_editable: bool,
    old_editable: bool,
    input_snapshot: Mapping[str, object],
    settings_values: Mapping[str, object],
    corner_state: Mapping[str, object] | None,
    corner_pair_same: Mapping[str, object] | None,
    endcap_bottom_wrap_state: Mapping[str, object] | None,
    assembly_type: object,
    fixed_corner_state: Mapping[str, object] | None = None,
    available_parts: tuple[object, ...] | list[object] = (),
    current_structure: Mapping[str, object] | None = None,
    previous_non_receiving_structure: Mapping[str, object] | None = None,
) -> FamilyModelPlan:
    target_model = str(new_model or "").strip()
    previous_model = str(old_model or "").strip()
    snapshot = deepcopy(dict(input_snapshot))
    corners = deepcopy(dict(corner_state or {}))
    pairs = deepcopy(dict(corner_pair_same or {}))
    wrap_state = deepcopy(dict(endcap_bottom_wrap_state or {}))
    canonical_assembly = normalize_assembly_type(assembly_type)
    old_snapshot_model = str(
        snapshot.get("model") or previous_model or ""
    ).strip()

    if (
        (not new_editable and target_model and target_model != previous_model)
        or (new_editable and previous_model and not old_editable)
    ):
        preset = apply_corner_preset(corners, pairs, fixed_corner_state)
        corners = preset.corner_state
        pairs = preset.corner_pair_same

    snapshot["model"] = target_model
    defaults: dict[str, object] = {}
    family_values: dict[str, object] = {}

    if (
        not new_editable
        and target_model
        and target_model != old_snapshot_model
    ):
        runtime_presets = dict(snapshot.get("_runtime_family_presets") or {})
        preset_runtime = deepcopy(
            dict(runtime_presets.get(target_model) or {})
        )
        preset_base = dict(preset_runtime.get("settings") or {})
        if not preset_base:
            preset_base = dict(snapshot.get("factory_defaults") or {})
        if not preset_base:
            preset_base = {
                key: value
                for key, value in snapshot.items()
                if key in settings_values
            }

        defaults = dict(
            cabinet_family_policy.apply_fresh_family_defaults(
                preset_base, target_model
            )
        )
        snapshot.update(defaults)

        runtime_field_map = {
            "multi_door_enabled": "multi_door_enabled",
            "door_layout_columns": "door_layout_columns",
            "door_layout_scope": "door_layout_scope",
            "door_handle_edges": "door_handle_edges",
            "receiving_inner_doors": "inner_doors",
            "door_nameplate_center_datum_top": (
                "door_nameplate_center_datum_top"
            ),
        }
        for source_key, target_key in runtime_field_map.items():
            if source_key in preset_runtime:
                snapshot[target_key] = deepcopy(preset_runtime[source_key])

        family_values = {
            key: value
            for key, value in defaults.items()
            if key in settings_values
        }

        intent_result = assembly_intent(
            snapshot,
            corners,
            pairs,
            cabinet_family_policy.fresh_assembly_intent(target_model),
            available_parts=available_parts,
            project_legacy_corner=False,
        )
        snapshot = intent_result.input_snapshot
        corners = intent_result.corner_state
        pairs = intent_result.corner_pair_same
        canonical_assembly = intent_result.assembly_type

        wrap_state = normalize_endcap_bottom_wrap_state(
            {"model": target_model}
        )
        snapshot["endcap_bottom_wrap"] = deepcopy(wrap_state)

    remember_structure = None
    desired_structure = None
    current = (
        None if current_structure is None
        else deepcopy(dict(current_structure))
    )

    if target_model == "受電箱" and current is not None:
        if old_snapshot_model != "受電箱":
            remember_structure = deepcopy(current)
        desired_structure = cabinet_family_policy.resolve_box_body_structure_state(
            target_model, current
        )
    elif old_snapshot_model == "受電箱":
        runtime_presets = dict(snapshot.get("_runtime_family_presets") or {})
        preset_runtime = deepcopy(
            dict(runtime_presets.get(target_model) or {})
        )
        previous = preset_runtime.get("box_body_structure")
        if previous is None:
            previous = previous_non_receiving_structure
        if previous:
            desired_structure = deepcopy(dict(previous))

    transition = FamilyModelTransition(
        new_model=target_model,
        old_model=previous_model,
        editable=bool(new_editable),
        defaults=deepcopy(defaults),
        family_values=deepcopy(family_values),
        assembly_type=canonical_assembly,
        structure_state=(
            None if desired_structure is None
            else deepcopy(desired_structure)
        ),
        remember_non_receiving_structure=(
            None if remember_structure is None
            else deepcopy(remember_structure)
        ),
    )
    return FamilyModelPlan(
        input_snapshot=snapshot,
        corner_state=corners,
        corner_pair_same=pairs,
        endcap_bottom_wrap_state=deepcopy(wrap_state),
        assembly_type=canonical_assembly,
        desired_structure=(
            None if desired_structure is None
            else deepcopy(desired_structure)
        ),
        transition=transition,
    )


__all__ = [
    "AssemblyIntentTransition",
    "BottomWrapTransition",
    "CornerStateTransition",
    "ExternalModelPlan",
    "ExternalSyncPlan",
    "FamilyModelPlan",
    "FamilyModelTransition",
    "SettingsCommitTransition",
    "activate_box_structure",
    "apply_box_structure_numeric",
    "assembly_intent",
    "bottom_wrap",
    "commit_corner_mode",
    "commit_corner_pair",
    "commit_corner_parameters",
    "commit_corner_type",
    "commit_settings",
    "corner_selection",
    "corner_targets",
    "endcap_edge_relation",
    "endcap_fw_follow",
    "endcap_fw_override",
    "ensure_corner_part",
    "family_model_transition",
    "apply_corner_preset",
    "normalize_assembly_type",
    "normalize_symmetry",
    "normalize_updates",
    "plan_external_model_change",
    "plan_external_sync",
    "reconcile_width_structure",
    "replace_corner_state",
    "settings_defaults_payload",
    "toggle_box_structure_lock",
]
