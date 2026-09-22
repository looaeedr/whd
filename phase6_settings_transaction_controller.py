# -*- coding: utf-8 -*-
"""Phase 3 application-level settings transaction state owner.

This module owns Designer-side staged settings state and debounce transaction
decisions.  It deliberately owns no Tk widget, timer implementation, renderer,
project I/O, manufacturing solver, or bridge import.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Mapping, MutableMapping

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
    commit_box_fw as _commit_box_fw_semantics,
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
import phase6_settings_transitions as settings_transitions
from phase6_settings_service import (
    Phase6SettingsTransactionService,
    SettingsFlushPlan,
    SettingsStagePlan,
)


def _sync_mapping_in_place(
    target: MutableMapping[str, object],
    source: Mapping[str, object],
) -> MutableMapping[str, object]:
    """Apply a pure transition result without invalidating live nested refs."""
    incoming = deepcopy(dict(source or {}))
    for key in tuple(target):
        if key not in incoming:
            del target[key]
    for key, value in incoming.items():
        current = target.get(key)
        if isinstance(current, MutableMapping) and isinstance(value, Mapping):
            _sync_mapping_in_place(current, value)
        else:
            target[key] = value
    return target


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


class Phase6SettingsTransactionController:
    """Own staged setting state and transaction ordering without Tk effects."""

    DEBOUNCE_MS = 150

    def __init__(
        self,
        *,
        settings_values: MutableMapping[str, object],
        input_snapshot: MutableMapping[str, object],
        box_whd: MutableMapping[str, object],
        pending_settings: MutableMapping[str, object] | None = None,
        debounce_job: object | None = None,
        workspace=None,
        endcap_fw_state: MutableMapping[str, object] | None = None,
        endcap_bottom_wrap_state: MutableMapping[str, object] | None = None,
        corner_state: MutableMapping[str, object] | None = None,
        corner_pair_same: MutableMapping[str, object] | None = None,
        assembly_type=None,
        last_external_revision: int = 0,
        last_external_transaction_id: str = "",
        active_transaction_id: str = "",
        orchestration: Phase6SettingsTransactionService | None = None,
    ) -> None:
        self._settings_values = settings_values
        self._input_snapshot = input_snapshot
        self._box_whd = box_whd
        self._workspace = workspace
        self._orchestration = orchestration or Phase6SettingsTransactionService(
            settings_values=self._settings_values,
            input_snapshot=self._input_snapshot,
            box_whd=self._box_whd,
            pending_settings=pending_settings,
            debounce_job=debounce_job,
            last_external_revision=last_external_revision,
            last_external_transaction_id=last_external_transaction_id,
            active_transaction_id=active_transaction_id,
        )
        self._endcap_fw_state = endcap_fw_state if endcap_fw_state is not None else {}
        self._endcap_bottom_wrap_state = (
            endcap_bottom_wrap_state if endcap_bottom_wrap_state is not None else {}
        )
        self._corner_state = corner_state if corner_state is not None else {}
        self._corner_pair_same = (
            corner_pair_same if corner_pair_same is not None else {}
        )
        raw_assembly = (
            assembly_type
            if assembly_type is not None
            else self._input_snapshot.get("assembly_type", CornerTypeId.INSERT_OVERLAY)
        )
        self._assembly_type = settings_transitions.normalize_assembly_type(
            raw_assembly
        )
    @property
    def pending(self) -> dict[str, object]:
        return self._orchestration.pending
    @property
    def debounce_job(self):
        return self._orchestration.debounce_job
    def install_debounce_job(self, job) -> None:
        self._orchestration.install_debounce_job(job)
    def clear_debounce_job(self) -> None:
        self._orchestration.clear_debounce_job()
    def stage_setting_update(
        self,
        key: str,
        value: object,
        *,
        destroying: bool = False,
    ) -> SettingsStagePlan:
        return self._orchestration.stage_setting_update(
            key,
            value,
            destroying=destroying,
        )
    def drain_pending(self) -> SettingsFlushPlan:
        return self._orchestration.drain_pending()
    def normalize_updates(
        self,
        updates: Mapping[str, object] | None,
        *,
        external_apply_guard: bool = False,
    ) -> dict[str, object]:
        return settings_transitions.normalize_updates(
            self._settings_values,
            updates,
            external_apply_guard=external_apply_guard,
        )
    def restore_setting(self, key: str, value: object) -> None:
        key = str(key)
        self._settings_values[key] = value
        self._input_snapshot[key] = value
        self._orchestration.discard_pending(key)

    def commit_settings(
        self, values: Mapping[str, object] | None
    ) -> dict[str, object]:
        result = settings_transitions.commit_settings(
            self._settings_values,
            self._input_snapshot,
            self._box_whd,
            values,
        )
        self._settings_values.clear()
        self._settings_values.update(result.settings_values)
        self._input_snapshot.clear()
        self._input_snapshot.update(result.input_snapshot)
        self._box_whd.clear()
        self._box_whd.update(result.box_whd)
        return dict(result.committed)
    def mark_workspace_dirty(self) -> None:
        marker = getattr(self._workspace, "mark_dirty", None)
        if callable(marker):
            marker()

    def commit_box_structure_state(self, state) -> dict:
        setter = getattr(self._workspace, "set_box_body_structure_state", None)
        if not callable(setter):
            raise RuntimeError("workspace box-body structure owner is not connected")
        committed = setter(state)
        self._input_snapshot["box_body_structure"] = deepcopy(committed)
        self.mark_workspace_dirty()
        return committed

    def toggle_box_structure_lock(self, state) -> dict:
        return self.commit_box_structure_state(
            settings_transitions.toggle_box_structure_lock(state)
        )
    def activate_box_structure(self, state, type_id, total_w: float) -> dict:
        return self.commit_box_structure_state(
            settings_transitions.activate_box_structure(
                state, type_id, total_w
            )
        )
    def apply_box_structure_numeric(
        self,
        state,
        type_id,
        field: str,
        value: float,
        *,
        total_w: float,
        outside_family: bool = False,
    ) -> dict:
        next_state = settings_transitions.apply_box_structure_numeric(
            state,
            type_id,
            field,
            value,
            total_w=total_w,
            outside_family=outside_family,
        )
        return self.commit_box_structure_state(next_state)
    def commit_endcap_fw_follow(
        self, part_key: str, follow_box: bool
    ) -> dict:
        state = settings_transitions.endcap_fw_follow(
            self._input_snapshot,
            self._settings_values,
            self._endcap_fw_state,
            part_key,
            follow_box,
        )
        self._endcap_fw_state.clear()
        self._endcap_fw_state.update(deepcopy(state))
        self._input_snapshot["endcap_fw"] = deepcopy(state)
        self.mark_workspace_dirty()
        return deepcopy(state)
    def commit_endcap_fw_override(
        self, part_key: str, value: object
    ) -> dict:
        state = settings_transitions.endcap_fw_override(
            self._input_snapshot,
            self._settings_values,
            self._endcap_fw_state,
            part_key,
            value,
        )
        self._endcap_fw_state.clear()
        self._endcap_fw_state.update(deepcopy(state))
        self._input_snapshot["endcap_fw"] = deepcopy(state)
        self.mark_workspace_dirty()
        return deepcopy(state)
    def commit_editor_fw_takeover(self, value: object) -> dict[str, object]:
        """Route explicit editor box-FW takeover through EndCap semantic authority."""
        _commit_box_fw_semantics(self._endcap_fw_state, float(value))
        self._input_snapshot["endcap_fw"] = deepcopy(self._endcap_fw_state)
        return deepcopy(self._endcap_fw_state)

    def commit_bottom_wrap(
        self,
        part_key: str,
        *,
        reserve_u: float,
        reserve_v: float,
    ) -> dict:
        result = settings_transitions.bottom_wrap(
            self._input_snapshot,
            self._endcap_bottom_wrap_state,
            part_key,
            reserve_u=reserve_u,
            reserve_v=reserve_v,
        )
        self._endcap_bottom_wrap_state.clear()
        self._endcap_bottom_wrap_state.update(deepcopy(result.state))
        self._input_snapshot["endcap_bottom_wrap"] = deepcopy(result.state)
        self.mark_workspace_dirty()
        return deepcopy(result.resolved)
    def commit_endcap_edge_relation(
        self, part_key: str, edge: str, relation
    ) -> dict:
        snapshot = settings_transitions.endcap_edge_relation(
            self._input_snapshot,
            part_key,
            edge,
            relation,
        )
        self._input_snapshot.update({
            "assembly_joint_schema_version": snapshot[
                "assembly_joint_schema_version"
            ],
            "assembly_joints": deepcopy(snapshot["assembly_joints"]),
            "assembly_type": snapshot.get(
                "assembly_type", self._input_snapshot.get("assembly_type")
            ),
        })
        self.mark_workspace_dirty()
        return snapshot

    CORNER_KEYS = settings_transitions.CORNER_KEYS
    CORNER_PAIR_KEYS = settings_transitions.CORNER_PAIR_KEYS

    @property
    def assembly_type(self):
        return self._assembly_type

    @property
    def active_transaction_id(self) -> str:
        return self._orchestration.active_transaction_id
    @property
    def last_external_revision(self) -> int:
        return self._orchestration.last_external_revision
    @property
    def last_external_transaction_id(self) -> str:
        return self._orchestration.last_external_transaction_id
    def ensure_corner_part(
        self, part_key: str
    ) -> tuple[dict, dict]:
        result = settings_transitions.ensure_corner_part(
            self._corner_state,
            self._corner_pair_same,
            part_key,
        )
        _sync_mapping_in_place(self._corner_state, result.corner_state)
        _sync_mapping_in_place(
            self._corner_pair_same, result.corner_pair_same
        )
        part = str(part_key)
        return self._corner_state[part], self._corner_pair_same[part]
    def corner_selection(
        self, part_key: str, target_key: str
    ) -> CornerTypeSelection:
        state, pairs = self.ensure_corner_part(part_key)
        return settings_transitions.corner_selection(
            state, pairs, target_key
        )
    def _corner_targets(
        self, pairs: Mapping[str, object], target_key: str
    ) -> tuple[str, ...]:
        return settings_transitions.corner_targets(pairs, target_key)
    def commit_corner_pair(
        self, part_key: str, pair_key: str, enabled: bool
    ) -> tuple[dict, dict]:
        result = settings_transitions.commit_corner_pair(
            self._corner_state,
            self._corner_pair_same,
            part_key,
            pair_key,
            enabled,
        )
        _sync_mapping_in_place(self._corner_state, result.corner_state)
        _sync_mapping_in_place(
            self._corner_pair_same, result.corner_pair_same
        )
        part = str(part_key)
        return self._corner_state[part], self._corner_pair_same[part]
    def commit_corner_type(
        self, part_key: str, target_key: str, type_id
    ) -> dict:
        result = settings_transitions.commit_corner_type(
            self._corner_state,
            self._corner_pair_same,
            part_key,
            target_key,
            type_id,
        )
        _sync_mapping_in_place(self._corner_state, result.corner_state)
        _sync_mapping_in_place(
            self._corner_pair_same, result.corner_pair_same
        )
        return deepcopy(result.value)
    def commit_corner_mode(
        self, part_key: str, target_key: str, mode
    ) -> dict:
        result = settings_transitions.commit_corner_mode(
            self._corner_state,
            self._corner_pair_same,
            part_key,
            target_key,
            mode,
        )
        _sync_mapping_in_place(self._corner_state, result.corner_state)
        _sync_mapping_in_place(
            self._corner_pair_same, result.corner_pair_same
        )
        return deepcopy(result.value)
    def commit_corner_parameters(
        self,
        part_key: str,
        target_key: str,
        *,
        amount_t: float | None = None,
        cross_mode=None,
        direction=None,
        secondary_retain_t: float | None = None,
        secondary_depth_t: float | None = None,
    ) -> dict:
        result = settings_transitions.commit_corner_parameters(
            self._corner_state,
            self._corner_pair_same,
            part_key,
            target_key,
            amount_t=amount_t,
            cross_mode=cross_mode,
            direction=direction,
            secondary_retain_t=secondary_retain_t,
            secondary_depth_t=secondary_depth_t,
        )
        _sync_mapping_in_place(self._corner_state, result.corner_state)
        _sync_mapping_in_place(
            self._corner_pair_same, result.corner_pair_same
        )
        return deepcopy(result.value)
    def commit_assembly_intent(
        self,
        type_id,
        *,
        available_parts=(),
        project_legacy_corner: bool = False,
        reset_bottom_defaults: bool = False,
        mark_dirty: bool = True,
    ):
        result = settings_transitions.assembly_intent(
            self._input_snapshot,
            self._corner_state,
            self._corner_pair_same,
            type_id,
            available_parts=available_parts,
            project_legacy_corner=project_legacy_corner,
            reset_bottom_defaults=reset_bottom_defaults,
        )
        snapshot = result.input_snapshot
        self._input_snapshot.update({
            "assembly_joint_schema_version": snapshot[
                "assembly_joint_schema_version"
            ],
            "assembly_joints": deepcopy(snapshot["assembly_joints"]),
            "assembly_type": snapshot["assembly_type"],
        })
        _sync_mapping_in_place(self._corner_state, result.corner_state)
        _sync_mapping_in_place(
            self._corner_pair_same, result.corner_pair_same
        )
        self._assembly_type = result.assembly_type
        if mark_dirty:
            self.mark_workspace_dirty()
        return self._assembly_type
    def replace_corner_state(
        self,
        corner_state: Mapping[str, object] | None,
        corner_pair_same: Mapping[str, object] | None,
    ) -> tuple[dict, dict]:
        result = settings_transitions.replace_corner_state(
            corner_state, corner_pair_same
        )
        _sync_mapping_in_place(self._corner_state, result.corner_state)
        _sync_mapping_in_place(
            self._corner_pair_same, result.corner_pair_same
        )
        return (
            deepcopy(self._corner_state),
            deepcopy(self._corner_pair_same),
        )
    def plan_external_sync(
        self, envelope: Mapping[str, object] | None
    ) -> ExternalSyncPlan:
        plan = self._orchestration.plan_external_sync(envelope)
        return ExternalSyncPlan(
            plan.accepted,
            plan.revision,
            plan.transaction_id,
            dict(plan.settings),
            plan.reason,
        )
    def push_active_transaction(
        self, transaction_id: str | None
    ) -> str:
        return self._orchestration.push_active_transaction(transaction_id)
    def restore_active_transaction(
        self, previous: str | None
    ) -> None:
        self._orchestration.restore_active_transaction(previous)
    def commit_symmetry(self, state, value: bool) -> bool:
        committed = settings_transitions.normalize_symmetry(value)
        setattr(state, "symmetric", committed)
        self.mark_workspace_dirty()
        return committed
    def settings_defaults_payload(self, context: str):
        return settings_transitions.settings_defaults_payload(
            context,
            self._settings_values,
            self._corner_state,
            self._corner_pair_same,
        )
    def commit_reconciled_width_structure(self, new_w: float) -> dict:
        getter = getattr(self._workspace, "box_body_structure_state", None)
        if not callable(getter):
            raise RuntimeError(
                "workspace box-body structure owner is not connected"
            )
        next_state = settings_transitions.reconcile_width_structure(
            getter(), new_w
        )
        return self.commit_box_structure_state(next_state)
    def _apply_corner_preset(
        self, fixed_corner_state: Mapping[str, object] | None
    ) -> None:
        result = settings_transitions.apply_corner_preset(
            self._corner_state,
            self._corner_pair_same,
            fixed_corner_state,
        )
        _sync_mapping_in_place(self._corner_state, result.corner_state)
        _sync_mapping_in_place(
            self._corner_pair_same, result.corner_pair_same
        )
    def commit_family_model_transition(
        self,
        new_model,
        old_model,
        *,
        new_editable: bool,
        old_editable: bool,
        fixed_corner_state: Mapping[str, object] | None = None,
        available_parts=(),
        previous_non_receiving_structure=None,
    ) -> FamilyModelTransition:
        getter = getattr(self._workspace, "box_body_structure_state", None)
        current_structure = getter() if callable(getter) else None
        plan = settings_transitions.family_model_transition(
            new_model,
            old_model,
            new_editable=new_editable,
            old_editable=old_editable,
            input_snapshot=self._input_snapshot,
            settings_values=self._settings_values,
            corner_state=self._corner_state,
            corner_pair_same=self._corner_pair_same,
            endcap_bottom_wrap_state=self._endcap_bottom_wrap_state,
            assembly_type=self._assembly_type,
            fixed_corner_state=fixed_corner_state,
            available_parts=available_parts,
            current_structure=current_structure,
            previous_non_receiving_structure=(
                previous_non_receiving_structure
            ),
        )
        self._input_snapshot.clear()
        self._input_snapshot.update(deepcopy(plan.input_snapshot))
        self._corner_state.clear()
        self._corner_state.update(deepcopy(plan.corner_state))
        self._corner_pair_same.clear()
        self._corner_pair_same.update(deepcopy(plan.corner_pair_same))
        self._endcap_bottom_wrap_state.clear()
        self._endcap_bottom_wrap_state.update(
            deepcopy(plan.endcap_bottom_wrap_state)
        )
        self._assembly_type = plan.assembly_type

        committed_structure = None
        if plan.desired_structure is not None:
            committed_structure = self.commit_box_structure_state(
                plan.desired_structure
            )

        self.mark_workspace_dirty()
        result = plan.transition
        return FamilyModelTransition(
            new_model=result.new_model,
            old_model=result.old_model,
            editable=result.editable,
            defaults=deepcopy(result.defaults),
            family_values=deepcopy(result.family_values),
            assembly_type=self._assembly_type,
            structure_state=(
                None
                if committed_structure is None
                else deepcopy(committed_structure)
            ),
            remember_non_receiving_structure=deepcopy(
                result.remember_non_receiving_structure
            ),
        )
    def plan_external_model_change(self, model) -> ExternalModelPlan:
        plan = settings_transitions.plan_external_model_change(
            model,
            self._input_snapshot.get("model"),
        )
        return ExternalModelPlan(plan.changed, plan.target_model)