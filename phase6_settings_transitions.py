# -*- coding: utf-8 -*-
"""Pure Phase 4 Settings transition kernel.

This module owns Settings semantic calculations only. It has no Tk, GUI,
bridge, workspace, callback, scheduler, or renderer ownership.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping

from ae_engine import manufacturing_api
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


CORNER_KEYS = manufacturing_api.MANUAL_CORNER_KEYS
CORNER_PAIR_KEYS = manufacturing_api.MANUAL_CORNER_PAIR_KEYS


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


CornerStateTransition = manufacturing_api.CornerStateTransition


AssemblyIntentTransition = manufacturing_api.AssemblyIntentTransition


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


FamilyModelTransition = manufacturing_api.FamilyModelTransition
FamilyModelPlan = manufacturing_api.FamilyModelPlan


def normalize_assembly_type(value: object) -> object:
    return manufacturing_api.normalize_assembly_type(value)


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
    # Keep the original type until the sole physical size gate. float(True)
    # would otherwise turn a corrupt 1-mm boolean into an apparently valid W.
    return reconcile_box_body_structure_for_total_w_change(
        state, new_w
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
    return manufacturing_api.ensure_corner_part(
        corner_state, corner_pair_same, part_key
    )


def corner_selection(
    part_state: Mapping[str, object],
    pairs: Mapping[str, object],
    target_key: str,
) -> CornerTypeSelection:
    return manufacturing_api.corner_selection(
        part_state, pairs, target_key
    )


def corner_targets(
    pairs: Mapping[str, object],
    target_key: str,
) -> tuple[str, ...]:
    return manufacturing_api.corner_targets(
        pairs, target_key
    )


def commit_corner_pair(
    corner_state: Mapping[str, object] | None,
    corner_pair_same: Mapping[str, object] | None,
    part_key: str,
    pair_key: str,
    enabled: bool,
) -> CornerStateTransition:
    return manufacturing_api.commit_corner_pair(
        corner_state, corner_pair_same, part_key, pair_key, enabled
    )


def commit_corner_type(
    corner_state: Mapping[str, object] | None,
    corner_pair_same: Mapping[str, object] | None,
    part_key: str,
    target_key: str,
    type_id: object,
) -> CornerStateTransition:
    return manufacturing_api.commit_corner_type(
        corner_state, corner_pair_same, part_key, target_key, type_id
    )


def commit_corner_mode(
    corner_state: Mapping[str, object] | None,
    corner_pair_same: Mapping[str, object] | None,
    part_key: str,
    target_key: str,
    mode: object,
) -> CornerStateTransition:
    return manufacturing_api.commit_corner_mode(
        corner_state, corner_pair_same, part_key, target_key, mode
    )


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
    return manufacturing_api.commit_corner_parameters(
        corner_state, corner_pair_same, part_key, target_key, amount_t=amount_t, cross_mode=cross_mode, direction=direction, secondary_retain_t=secondary_retain_t, secondary_depth_t=secondary_depth_t
    )


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
    return manufacturing_api.commit_assembly_intent_state(
        input_snapshot, corner_state, corner_pair_same, type_id,
        available_parts=available_parts,
        project_legacy_corner=project_legacy_corner,
        reset_bottom_defaults=reset_bottom_defaults,
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
    return manufacturing_api.apply_corner_preset(
        corner_state, corner_pair_same, fixed_corner_state
    )


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
    return manufacturing_api.plan_cabinet_family_model_transition(
        new_model, old_model,
        new_editable=new_editable, old_editable=old_editable,
        input_snapshot=input_snapshot, settings_values=settings_values,
        corner_state=corner_state, corner_pair_same=corner_pair_same,
        endcap_bottom_wrap_state=endcap_bottom_wrap_state,
        assembly_type=assembly_type, fixed_corner_state=fixed_corner_state,
        available_parts=available_parts, current_structure=current_structure,
        previous_non_receiving_structure=previous_non_receiving_structure,
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
