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


@dataclass(frozen=True)
class SettingsStagePlan:
    changed: bool
    cancel_job: object | None
    schedule_after_ms: int | None


@dataclass(frozen=True)
class SettingsFlushPlan:
    cancel_job: object | None
    pending: dict[str, object]


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
    ) -> None:
        self._settings_values = settings_values
        self._input_snapshot = input_snapshot
        self._box_whd = box_whd
        self._pending = pending_settings if pending_settings is not None else {}
        self._debounce_job: object | None = debounce_job
        self._workspace = workspace
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
        stable = assembly_intent_value(raw_assembly)
        self._assembly_type = (
            stable if stable == "WRAP_OVERLAY" else CornerTypeId(stable)
        )
        self._last_external_revision = int(last_external_revision or 0)
        self._last_external_transaction_id = str(last_external_transaction_id or "")
        self._active_transaction_id = str(active_transaction_id or "")

    def bind_state(
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
    ) -> None:
        """Rebind mutable compatibility mirrors after legacy snapshot replacement."""
        self._settings_values = settings_values
        self._input_snapshot = input_snapshot
        self._box_whd = box_whd
        self._workspace = workspace
        if endcap_fw_state is not None:
            self._endcap_fw_state = endcap_fw_state
        if endcap_bottom_wrap_state is not None:
            self._endcap_bottom_wrap_state = endcap_bottom_wrap_state
        if corner_state is not None:
            self._corner_state = corner_state
        if corner_pair_same is not None:
            self._corner_pair_same = corner_pair_same
        if pending_settings is not None and pending_settings is not self._pending:
            if self._pending and not pending_settings:
                pending_settings.update(self._pending)
            self._pending = pending_settings
        self._debounce_job = debounce_job

    @property
    def pending(self) -> dict[str, object]:
        return dict(self._pending)

    @property
    def debounce_job(self):
        return self._debounce_job

    def install_debounce_job(self, job) -> None:
        self._debounce_job = job

    def clear_debounce_job(self) -> None:
        self._debounce_job = None

    def stage_setting_update(
        self,
        key: str,
        value: object,
        *,
        destroying: bool = False,
    ) -> SettingsStagePlan:
        if destroying:
            return SettingsStagePlan(False, None, None)
        key = str(key)
        if self._settings_values.get(key) == value:
            return SettingsStagePlan(False, None, None)

        self._settings_values[key] = value
        self._input_snapshot[key] = value
        self._pending[key] = value
        return SettingsStagePlan(
            True,
            self._debounce_job,
            self.DEBOUNCE_MS,
        )

    def drain_pending(self) -> SettingsFlushPlan:
        job = self._debounce_job
        self._debounce_job = None
        pending = dict(self._pending)
        self._pending.clear()
        return SettingsFlushPlan(cancel_job=job, pending=pending)

    def normalize_updates(
        self,
        updates: Mapping[str, object] | None,
        *,
        external_apply_guard: bool = False,
    ) -> dict[str, object]:
        clean: dict[str, object] = {}
        for key, raw in dict(updates or {}).items():
            if key not in self._settings_values:
                continue
            if key == "ui_text_size":
                value: object = normalize_ui_text_size(raw)
            elif isinstance(self._settings_values.get(key), bool):
                value = bool(raw)
            else:
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    continue
            if external_apply_guard and self._settings_values.get(key) == value:
                continue
            clean[key] = value
        return clean

    def restore_setting(self, key: str, value: object) -> None:
        key = str(key)
        self._settings_values[key] = value
        self._input_snapshot[key] = value
        self._pending.pop(key, None)

    def commit_settings(self, values: Mapping[str, object] | None) -> dict[str, object]:
        committed = dict(values or {})
        if not committed:
            return {}
        self._settings_values.update(committed)
        self._input_snapshot.update(committed)
        if "ui_text_size" in committed:
            normalized = normalize_ui_text_size(committed["ui_text_size"])
            self._settings_values["ui_text_size"] = normalized
            self._input_snapshot["ui_text_size"] = normalized
            committed["ui_text_size"] = normalized
        for key in ("w", "h", "d"):
            if key in committed:
                self._box_whd[key] = _ui_len(committed[key])
        return committed


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
            set_structure_locked(state, not bool(dict(state).get("locked", True)))
        )

    def activate_box_structure(self, state, type_id, total_w: float) -> dict:
        return self.commit_box_structure_state(
            activate_structure_with_defaults(state, type_id, total_w)
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
        type_id = BoxBodyStructureType(type_id)
        field = str(field)
        value = float(value)
        if type_id is BoxBodyStructureType.TWO_PIECE_W_SPLIT and field in {"left", "right"}:
            next_state = set_two_piece_width(state, total_w, field, value)
        elif type_id is BoxBodyStructureType.THREE_PIECE_W_SPLIT and field in {"left", "middle", "right"}:
            next_state = set_three_piece_width(state, total_w, field, value)
        elif field == "seam_bend":
            next_state = set_join_seam_bend(state, type_id, value)
        elif type_id is BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT and field == "side_rear_bend":
            next_state = set_side_back_geometry(
                state,
                side_rear_bend=value,
                side_rear_bend_dimension_space=("OUTSIDE" if outside_family else None),
            )
        elif type_id is BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT and field == "back_width_comp_t":
            next_state = set_side_back_geometry(state, back_width_comp_t=value)
        else:
            if field in {
                "endcap_extra_relief",
                "endcap_single_side_meat_t",
                "baseplate_relief_length",
                "baseplate_single_side_meat_t",
            } and value < 0:
                raise ValueError("截角／避讓參數不得小於 0")
            next_state = update_structure_config(state, type_id, {field: value})
        return self.commit_box_structure_state(next_state)

    def commit_endcap_fw_follow(self, part_key: str, follow_box: bool) -> dict:
        snapshot = dict(self._input_snapshot)
        snapshot.update(dict(self._settings_values))
        set_endcap_fw_follow(
            self._endcap_fw_state,
            str(part_key),
            bool(follow_box),
            box_fw=_num(snapshot.get("fw", 25), 25),
        )
        self._input_snapshot["endcap_fw"] = deepcopy(self._endcap_fw_state)
        self.mark_workspace_dirty()
        return deepcopy(self._endcap_fw_state)

    def commit_endcap_fw_override(self, part_key: str, value: object) -> dict:
        snapshot = dict(self._input_snapshot)
        snapshot.update(dict(self._settings_values))
        commit_endcap_fw(
            self._endcap_fw_state,
            str(part_key),
            _num(value),
            box_fw=_num(snapshot.get("fw", 25), 25),
        )
        self._input_snapshot["endcap_fw"] = deepcopy(self._endcap_fw_state)
        self.mark_workspace_dirty()
        return deepcopy(self._endcap_fw_state)

    def commit_bottom_wrap(
        self,
        part_key: str,
        *,
        reserve_u: float,
        reserve_v: float,
    ) -> dict:
        if not isinstance(self._endcap_bottom_wrap_state, dict):
            self._endcap_bottom_wrap_state = {}
        if not self._endcap_bottom_wrap_state:
            self._endcap_bottom_wrap_state.update(
                normalize_endcap_bottom_wrap_state(self._input_snapshot)
            )
        commit_endcap_bottom_wrap(
            self._endcap_bottom_wrap_state,
            str(part_key),
            reserve_u=float(reserve_u),
            reserve_v=float(reserve_v),
        )
        self._input_snapshot["endcap_bottom_wrap"] = deepcopy(
            self._endcap_bottom_wrap_state
        )
        self.mark_workspace_dirty()
        return resolve_endcap_bottom_wrap(
            self._input_snapshot,
            str(part_key),
            state=self._endcap_bottom_wrap_state,
        )

    def commit_endcap_edge_relation(self, part_key: str, edge: str, relation) -> dict:
        snapshot = set_part_edge_relation(
            dict(self._input_snapshot),
            str(part_key),
            str(edge).upper(),
            relation,
        )
        self._input_snapshot.update({
            "assembly_joint_schema_version": snapshot["assembly_joint_schema_version"],
            "assembly_joints": deepcopy(snapshot["assembly_joints"]),
            "assembly_type": snapshot.get(
                "assembly_type", self._input_snapshot.get("assembly_type")
            ),
        })
        self.mark_workspace_dirty()
        return snapshot


    CORNER_KEYS = ("top_left", "top_right", "bottom_left", "bottom_right")
    CORNER_PAIR_KEYS = {
        "top": ("top_left", "top_right"),
        "bottom": ("bottom_left", "bottom_right"),
    }

    @property
    def assembly_type(self):
        return self._assembly_type

    @property
    def active_transaction_id(self) -> str:
        return self._active_transaction_id

    @property
    def last_external_revision(self) -> int:
        return self._last_external_revision

    @property
    def last_external_transaction_id(self) -> str:
        return self._last_external_transaction_id

    def ensure_corner_part(self, part_key: str) -> tuple[dict, dict]:
        part = str(part_key)
        state = self._corner_state.setdefault(part, {})
        for corner_key in self.CORNER_KEYS:
            state[corner_key] = selection_to_raw(
                selection_from_raw(state.get(corner_key))
            )
        pairs = self._corner_pair_same.setdefault(part, {})
        pairs.setdefault("top", True)
        pairs.setdefault("bottom", True)
        return state, pairs

    def corner_selection(self, part_key: str, target_key: str) -> CornerTypeSelection:
        state, pairs = self.ensure_corner_part(part_key)
        current_key = (
            self.CORNER_PAIR_KEYS[target_key][0]
            if target_key in self.CORNER_PAIR_KEYS
            else str(target_key)
        )
        return selection_from_raw(state[current_key])

    def _corner_targets(self, pairs: Mapping[str, object], target_key: str) -> tuple[str, ...]:
        key = str(target_key)
        if key in self.CORNER_PAIR_KEYS:
            return self.CORNER_PAIR_KEYS[key]
        return (key,)

    def commit_corner_pair(self, part_key: str, pair_key: str, enabled: bool) -> tuple[dict, dict]:
        state, pairs = self.ensure_corner_part(part_key)
        pair = str(pair_key)
        if pair not in self.CORNER_PAIR_KEYS:
            raise ValueError(f"unknown corner pair: {pair}")
        pairs[pair] = bool(enabled)
        if enabled:
            left_key, right_key = self.CORNER_PAIR_KEYS[pair]
            state[right_key] = deepcopy(state[left_key])
        return state, pairs

    def commit_corner_type(self, part_key: str, target_key: str, type_id) -> dict:
        state, pairs = self.ensure_corner_part(part_key)
        current = self.corner_selection(part_key, target_key)
        wanted = CornerTypeId(type_id)
        selection = (
            current
            if current.type_id is wanted
            else CornerTypeSelection(wanted)
        )
        raw = selection_to_raw(selection)
        for corner_key in self._corner_targets(pairs, target_key):
            state[corner_key] = deepcopy(raw)
        return deepcopy(raw)

    def commit_corner_mode(self, part_key: str, target_key: str, mode) -> dict:
        state, pairs = self.ensure_corner_part(part_key)
        current = self.corner_selection(part_key, target_key)
        if current.type_id is not CornerTypeId.CROSS:
            return selection_to_raw(current)
        selection = CornerTypeSelection(
            CornerTypeId.CROSS,
            cross_mode=CrossCornerMode(mode),
        )
        raw = selection_to_raw(selection)
        for corner_key in self._corner_targets(pairs, target_key):
            state[corner_key] = deepcopy(raw)
        return deepcopy(raw)

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
        state, pairs = self.ensure_corner_part(part_key)
        current = self.corner_selection(part_key, target_key)
        amount = current.amount_t if amount_t is None else float(amount_t)

        if current.type_id is CornerTypeId.CROSS:
            mode = current.cross_mode if cross_mode is None else CrossCornerMode(cross_mode)
            if mode is CrossCornerMode.STANDARD:
                selection = CornerTypeSelection(
                    CornerTypeId.CROSS,
                    cross_mode=mode,
                )
            else:
                selected_direction = (
                    current.direction if direction is None else CornerDirection(direction)
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
        for corner_key in self._corner_targets(pairs, target_key):
            state[corner_key] = deepcopy(raw)
        return deepcopy(raw)

    def commit_assembly_intent(
        self,
        type_id,
        *,
        available_parts=(),
        project_legacy_corner: bool = False,
        reset_bottom_defaults: bool = False,
        mark_dirty: bool = True,
    ):
        stable = assembly_intent_value(type_id)
        canonical = (
            stable if stable == "WRAP_OVERLAY" else CornerTypeId(stable)
        )
        snapshot = deepcopy(dict(self._input_snapshot))
        parts = tuple(str(key) for key in tuple(available_parts or ()) if str(key))
        if parts:
            snapshot["existing_parts"] = list(parts)
        snapshot = sync_snapshot_intent_joints(snapshot, canonical)
        self._input_snapshot.update({
            "assembly_joint_schema_version": snapshot["assembly_joint_schema_version"],
            "assembly_joints": deepcopy(snapshot["assembly_joints"]),
            "assembly_type": snapshot["assembly_type"],
        })
        self._assembly_type = canonical
        if project_legacy_corner:
            apply_box_assembly_type_to_raw_state(
                self._corner_state,
                self._corner_pair_same,
                legacy_corner_projection_for_intent(stable),
                reset_bottom_defaults=bool(reset_bottom_defaults),
            )
        if mark_dirty:
            self.mark_workspace_dirty()
        return canonical

    def replace_corner_state(
        self,
        corner_state: Mapping[str, object] | None,
        corner_pair_same: Mapping[str, object] | None,
    ) -> tuple[dict, dict]:
        self._corner_state.clear()
        self._corner_state.update(deepcopy(dict(corner_state or {})))
        self._corner_pair_same.clear()
        self._corner_pair_same.update(deepcopy(dict(corner_pair_same or {})))
        return deepcopy(self._corner_state), deepcopy(self._corner_pair_same)

    def plan_external_sync(self, envelope: Mapping[str, object] | None) -> ExternalSyncPlan:
        raw = dict(envelope or {})
        if str(raw.get("origin") or "") != "main_gui":
            return ExternalSyncPlan(False, self._last_external_revision, "", {}, "WRONG_ORIGIN")
        try:
            revision = int(raw.get("revision", 0) or 0)
        except (TypeError, ValueError):
            return ExternalSyncPlan(False, self._last_external_revision, "", {}, "INVALID_REVISION")
        if revision <= self._last_external_revision:
            return ExternalSyncPlan(
                False,
                revision,
                str(raw.get("transaction_id") or ""),
                {},
                "STALE_REVISION",
            )
        transaction_id = str(raw.get("transaction_id") or "")
        self._last_external_revision = revision
        self._last_external_transaction_id = transaction_id
        delta = dict(raw.get("delta") or {})
        settings = dict(delta.get("settings") or {})
        return ExternalSyncPlan(True, revision, transaction_id, settings, "OK")

    def push_active_transaction(self, transaction_id: str | None) -> str:
        previous = self._active_transaction_id
        self._active_transaction_id = str(transaction_id or previous or "")
        return previous

    def restore_active_transaction(self, previous: str | None) -> None:
        self._active_transaction_id = str(previous or "")

    def commit_symmetry(self, state, value: bool) -> bool:
        committed = bool(value)
        setattr(state, "symmetric", committed)
        self.mark_workspace_dirty()
        return committed

    def settings_defaults_payload(self, context: str):
        return (
            str(context),
            dict(self._settings_values),
            deepcopy(self._corner_state),
            deepcopy(self._corner_pair_same),
        )

    def plan_external_model_change(self, model) -> ExternalModelPlan:
        target = str(model or "").strip()
        current = str(self._input_snapshot.get("model") or "").strip()
        return ExternalModelPlan(bool(target and target != current), target)
