# -*- coding: utf-8 -*-
"""Phase 4 Settings orchestration/effect planning service.

This module owns staged/pending settings transaction ordering, debounce-token
ownership, external revision ordering, and active transaction scope.  It owns
no Tk widgets/timers, GUI owner, bridge object, renderer, project I/O, or
manufacturing behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from ae_engine import manufacturing_api
from phase6_settings_center import SETTING_SPECS
import phase6_settings_transitions as settings_transitions

_STAGE_SPECS = {spec.key: spec for spec in SETTING_SPECS}


@dataclass(frozen=True)
class SettingsStagePlan:
    changed: bool
    cancel_job: object | None
    schedule_after_ms: int | None
    key: str = ""
    value: object = None


@dataclass(frozen=True)
class SettingsFlushPlan:
    cancel_job: object | None
    pending: dict[str, object]


@dataclass(frozen=True)
class SettingsTransactionScope:
    previous_transaction_id: str
    active_transaction_id: str


class Phase6SettingsTransactionService:
    """Own non-UI Settings orchestration state and emit explicit plans."""

    DEBOUNCE_MS = 150

    def __init__(
        self,
        *,
        settings_values: dict[str, object] | None = None,
        input_snapshot: dict[str, object] | None = None,
        box_whd: dict[str, object] | None = None,
        pending_settings: dict[str, object] | None = None,
        debounce_job: object | None = None,
        last_external_revision: int = 0,
        last_external_transaction_id: str = "",
        active_transaction_id: str = "",
    ) -> None:
        self._settings_values = (
            settings_values if settings_values is not None else {}
        )
        self._input_snapshot = (
            input_snapshot if input_snapshot is not None else {}
        )
        self._box_whd = box_whd if box_whd is not None else {}
        self._pending = (
            pending_settings if pending_settings is not None else {}
        )
        self._debounce_job = debounce_job
        self._last_external_revision = int(last_external_revision or 0)
        self._last_external_transaction_id = str(
            last_external_transaction_id or ""
        )
        self._active_transaction_id = str(active_transaction_id or "")

    @property
    def pending(self) -> dict[str, object]:
        return dict(self._pending)

    @property
    def debounce_job(self):
        return self._debounce_job

    @property
    def last_external_revision(self) -> int:
        return self._last_external_revision

    @property
    def last_external_transaction_id(self) -> str:
        return self._last_external_transaction_id

    @property
    def active_transaction_id(self) -> str:
        return self._active_transaction_id

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
        spec = _STAGE_SPECS.get(key)
        if spec is None:
            raise ValueError(f"未定義的 Settings 欄位：{key}")

        # Direct service/controller callers must obey the same public Engine
        # source contract as Tk before touching any saved/pending draft.
        if key in manufacturing_api.PHYSICAL_SNAPSHOT_SOURCE_KEYS:
            staged_value = manufacturing_api.normalize_operator_source_dimension(
                value, field=key,
            )
        else:
            # The legacy adapter owns only UI text size; all other authored
            # boolean/numeric settings go through the original public Engine.
            normalized = settings_transitions.normalize_updates(
                {key: spec.default}, {key: value},
            )
            if key not in normalized:
                raise ValueError(f"{key} 設定來源無效，拒絕暫存")
            staged_value = normalized[key]

        if self._settings_values.get(key) == staged_value:
            return SettingsStagePlan(False, None, None)
        self._settings_values[key] = staged_value
        self._input_snapshot[key] = staged_value
        self._pending[key] = staged_value
        return SettingsStagePlan(
            True,
            self._debounce_job,
            self.DEBOUNCE_MS,
            key,
            staged_value,
        )

    def drain_pending(self) -> SettingsFlushPlan:
        job = self._debounce_job
        self._debounce_job = None
        pending = dict(self._pending)
        self._pending.clear()
        return SettingsFlushPlan(cancel_job=job, pending=pending)

    def clear_pending(self) -> None:
        self._pending.clear()

    def discard_pending(self, key: str) -> None:
        self._pending.pop(str(key), None)

    def plan_external_sync(
        self, envelope: Mapping[str, object] | None
    ) -> settings_transitions.ExternalSyncPlan:
        plan = settings_transitions.plan_external_sync(
            envelope,
            last_external_revision=self._last_external_revision,
        )
        if plan.accepted:
            self._last_external_revision = plan.revision
            self._last_external_transaction_id = plan.transaction_id
        return plan

    def push_active_transaction(
        self, transaction_id: str | None
    ) -> str:
        previous = self._active_transaction_id
        self._active_transaction_id = str(
            transaction_id or previous or ""
        )
        return previous

    def restore_active_transaction(self, previous: str | None) -> None:
        self._active_transaction_id = str(previous or "")

    def begin_transaction(
        self, transaction_id: str | None
    ) -> SettingsTransactionScope:
        previous = self.push_active_transaction(transaction_id)
        return SettingsTransactionScope(
            previous_transaction_id=previous,
            active_transaction_id=self._active_transaction_id,
        )

    def finish_transaction(
        self, scope: SettingsTransactionScope
    ) -> None:
        self.restore_active_transaction(scope.previous_transaction_id)


__all__ = [
    "Phase6SettingsTransactionService",
    "SettingsFlushPlan",
    "SettingsStagePlan",
    "SettingsTransactionScope",
]
