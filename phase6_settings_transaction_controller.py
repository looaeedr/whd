# -*- coding: utf-8 -*-
"""Phase 3 application-level settings transaction state owner.

This module owns Designer-side staged settings state and debounce transaction
decisions.  It deliberately owns no Tk widget, timer implementation, renderer,
project I/O, manufacturing solver, or bridge import.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, MutableMapping

from phase6_settings_center import normalize_ui_text_size
from phase6_fold_profiles import _ui_len


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
    ) -> None:
        self._settings_values = settings_values
        self._input_snapshot = input_snapshot
        self._box_whd = box_whd
        self._pending = pending_settings if pending_settings is not None else {}
        self._debounce_job: object | None = debounce_job

    def bind_state(
        self,
        *,
        settings_values: MutableMapping[str, object],
        input_snapshot: MutableMapping[str, object],
        box_whd: MutableMapping[str, object],
        pending_settings: MutableMapping[str, object] | None = None,
        debounce_job: object | None = None,
    ) -> None:
        """Rebind compatibility mirrors after legacy snapshot replacement."""
        self._settings_values = settings_values
        self._input_snapshot = input_snapshot
        self._box_whd = box_whd
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
