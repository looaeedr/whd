# -*- coding: utf-8 -*-
"""Phase6 主 GUI 專案交易與持久化協調模組。"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Callable, Mapping

from phase6_project_session import ProjectSession


SnapshotProvider = Callable[[], Mapping[str, object]]


class Phase6ProjectController:
    """隱藏 ProjectSession ordering 與 .p6fold 持久化規則的深模組。"""

    def __init__(
        self,
        *,
        read_project,
        write_project,
        schema: str,
        clock=None,
    ) -> None:
        self._session = ProjectSession()
        self._read_project = read_project
        self._write_project = write_project
        self._schema = str(schema)
        self._clock = clock or self._default_clock

    @staticmethod
    def _default_clock() -> str:
        return datetime.now().astimezone().isoformat(timespec="seconds")

    @property
    def project_path(self) -> str | None:
        return self._session.project_path

    @property
    def has_draft(self) -> bool:
        return self._session.has_draft

    def committed_snapshot(self) -> dict | None:
        return self._session.committed_snapshot()

    def loaded_baseline_snapshot(self) -> dict | None:
        return self._session.loaded_baseline_snapshot()

    def draft_snapshot(self) -> dict | None:
        return self._session.draft_snapshot()

    def set_project_path(self, path) -> str | None:
        return self._session.set_project_path(path)

    def capture_committed(self, snapshot: Mapping[str, object]) -> dict:
        return self._session.capture_committed(snapshot)

    def begin_designer(self, snapshot_provider: SnapshotProvider) -> dict:
        if self._session.has_draft:
            raise RuntimeError("Phase6ProjectController 已有 active draft，不能重複開始 3D 交易")
        self._session.capture_committed(snapshot_provider())
        return self._session.begin_draft()

    def cancel_designer(self) -> dict | None:
        return self._session.cancel_draft()

    def confirm_designer(self, committed_snapshot: Mapping[str, object]) -> dict:
        if self._session.has_draft:
            return self._session.commit_draft(committed_snapshot)
        return self._session.capture_committed(committed_snapshot)

    @staticmethod
    def _with_active_part_hint(snapshot: Mapping[str, object], active_part_hint=None) -> dict:
        result = deepcopy(dict(snapshot))
        workspace = deepcopy(dict(result.get("workspace") or {}))
        existing = set(result.get("existing_parts") or workspace.get("existing_parts") or ())
        if active_part_hint in existing:
            result["active_part"] = active_part_hint
            workspace["active_part"] = active_part_hint
            result["workspace"] = workspace
        return result

    def build_payload(self, snapshot_provider: SnapshotProvider, *, active_part_hint=None) -> dict:
        if self._session.has_draft:
            snapshot = self._session.snapshot_for_save()
        else:
            snapshot = self._session.capture_committed(snapshot_provider())
        snapshot = self._with_active_part_hint(snapshot, active_part_hint)
        return {
            "schema": self._schema,
            "saved_at": self._clock(),
            "snapshot": snapshot,
            "final_geometry": {},
        }

    def save(self, path, snapshot_provider: SnapshotProvider, *, active_part_hint=None) -> str:
        payload = self.build_payload(snapshot_provider, active_part_hint=active_part_hint)
        target = self._write_project(path, payload)
        self._session.set_project_path(target)
        return str(target)

    def load(self, path) -> tuple[dict, dict]:
        payload = self._read_project(path)
        committed = self._session.load_project(path, payload["snapshot"])
        return payload, committed
