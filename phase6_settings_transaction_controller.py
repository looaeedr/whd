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

from ae_engine.assembly_joint import set_part_edge_relation
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
    commit_endcap_bottom_wrap,
    commit_endcap_fw,
    resolve_endcap_bottom_wrap,
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
    ) -> None:
        """Rebind compatibility mirrors after legacy snapshot replacement."""
        self._settings_values = settings_values
        self._input_snapshot = input_snapshot
        self._box_whd = box_whd
        self._workspace = workspace
        if endcap_fw_state is not None:
            self._endcap_fw_state = endcap_fw_state
        if endcap_bottom_wrap_state is not None:
            self._endcap_bottom_wrap_state = endcap_bottom_wrap_state
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
