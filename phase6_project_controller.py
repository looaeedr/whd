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


    @staticmethod
    def build_designer_payload(
        *,
        schema: str,
        model: str,
        base_snapshot: Mapping[str, object],
        settings: Mapping[str, object],
        box_whd: Mapping[str, object],
        assembly_type,
        endcap_fw,
        corner_state,
        corner_pair_same,
        owner_workspace: Mapping[str, object],
        workspace: Mapping[str, object],
        box_body_profile,
        assembly_relief,
        final_geometry,
        saved_at: str | None = None,
    ) -> dict:
        snapshot = deepcopy(dict(base_snapshot or {}))
        snapshot.update(dict(settings or {}))
        snapshot.update(dict(box_whd or {}))
        owner = dict(owner_workspace or {})
        shared_workspace = deepcopy(dict(workspace or {}))
        snapshot.update({
            "model": str(model or ""),
            "assembly_type": deepcopy(assembly_type),
            "endcap_fw": deepcopy(endcap_fw),
            "settings": deepcopy(dict(settings or {})),
            "corner_state": deepcopy(corner_state or {}),
            "corner_pair_same": deepcopy(corner_pair_same or {}),
            "existing_parts": list(owner.get("existing_parts") or ()),
            "active_part": owner.get("active_part"),
            "workspace": shared_workspace,
            "box_body_profile": deepcopy(box_body_profile or []),
            "part_profiles": deepcopy(shared_workspace.get("part_profiles") or {}),
            "part_features": deepcopy(owner.get("part_features") or {}),
            "part_face_features": deepcopy(owner.get("part_face_features") or {}),
            "assembly_placements": deepcopy(owner.get("assembly_placements") or {}),
            "assembly_relief": deepcopy(assembly_relief or {}),
        })
        return {
            "schema": str(schema),
            "saved_at": saved_at or Phase6ProjectController._default_clock(),
            "model": str(model or ""),
            "snapshot": snapshot,
            "final_geometry": deepcopy(final_geometry or {}),
        }

    @staticmethod
    def validate_project_load(path, read_project):
        return read_project(path)

    @staticmethod
    def write_designer_project(path, payload, write_project) -> str:
        return str(write_project(path, payload))

    @staticmethod
    def build_diagnostic_payload(
        *,
        model: str,
        active_part,
        settings: Mapping[str, object],
        corner_state,
        corner_pair_same,
        workspace,
        active_part_payload,
        final_geometry_provider,
        context_factory,
        builder,
    ):
        context = context_factory(
            model=str(model or ""),
            active_part=active_part,
            settings=deepcopy(dict(settings or {})),
            corner_state=deepcopy(corner_state or {}),
            corner_pair_same=deepcopy(corner_pair_same or {}),
            workspace=deepcopy(workspace or {}),
            active_part_payload=deepcopy(active_part_payload or {}),
        )
        return builder(context, final_geometry_provider)

    @staticmethod
    def write_diagnostic(path, payload, writer) -> str:
        return str(writer(path, payload))

    @staticmethod
    def build_workspace_export(
        *,
        owner_workspace: Mapping[str, object],
        box_body_profile,
        structure_state,
    ) -> dict:
        owner = dict(owner_workspace or {})
        return {
            "box_body_profile": deepcopy(box_body_profile or []),
            "existing_parts": list(owner.get("existing_parts") or ()),
            "active_part": owner.get("active_part"),
            "part_profiles": deepcopy(owner.get("part_profiles") or {}),
            "box_body_structure": deepcopy(
                owner.get("box_body_structure") or structure_state or {}
            ),
        }

    @staticmethod
    def project_status_projection(*, family: str, mode: str, part_text: str) -> str:
        if mode == "assembly":
            return f"箱型：{family or '-'}  ｜  板件：-  ｜  視圖：組合體"
        if mode == "corner_data":
            return f"箱型：{family or '-'}  ｜  板件：{part_text or '-'}  ｜  視圖：截角資料"
        return f"箱型：{family or '-'}  ｜  板件：{part_text or '-'}  ｜  視圖：單件 3D"

    @staticmethod
    def route_settings_defaults(callback, payload) -> bool:
        if callback is None:
            return False
        callback(*payload)
        return True

    @staticmethod
    def commit_output_stock(value, stage_setting) -> bool:
        committed = bool(value)
        stage_setting("draw_stock", committed)
        return committed

    @staticmethod
    def route_selected_dxf_export(callback, flush_pending):
        flush_pending()
        if callback is None:
            return None
        return callback()
