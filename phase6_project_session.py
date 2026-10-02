# -*- coding: utf-8 -*-
"""Phase6 專案交易狀態的單一所有權模組。"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Mapping


class ProjectSession:
    """管理 loaded baseline、committed、draft 與 project path 的交易生命週期。"""

    def __init__(self) -> None:
        self._project_path: str | None = None
        self._loaded_baseline: dict | None = None
        self._committed: dict | None = None
        self._draft: dict | None = None

    @staticmethod
    def _clone(snapshot: Mapping[str, object] | None) -> dict | None:
        if snapshot is None:
            return None
        return deepcopy(dict(snapshot))

    @property
    def project_path(self) -> str | None:
        return self._project_path

    @property
    def has_draft(self) -> bool:
        return self._draft is not None

    def set_project_path(self, path: str | Path | None) -> str | None:
        self._project_path = None if path is None else str(Path(path))
        return self._project_path

    def load_project(self, path: str | Path, snapshot: Mapping[str, object]) -> dict:
        loaded = self._clone(snapshot)
        self._project_path = str(Path(path))
        self._loaded_baseline = self._clone(loaded)
        self._committed = self._clone(loaded)
        self._draft = None
        return self._clone(self._committed)

    def capture_committed(self, snapshot: Mapping[str, object]) -> dict:
        if self._draft is not None:
            raise RuntimeError("ProjectSession 有 active draft，不能直接改寫 committed")
        self._committed = self._clone(snapshot)
        return self._clone(self._committed)

    def begin_draft(self) -> dict:
        if self._committed is None:
            raise RuntimeError("ProjectSession 尚無 committed snapshot，不能開始 draft")
        self._draft = self._clone(self._committed)
        return self._clone(self._draft)

    def replace_draft(self, snapshot: Mapping[str, object]) -> dict:
        if self._draft is None:
            raise RuntimeError("ProjectSession 尚無 active draft，不能取代 draft")
        self._draft = self._clone(snapshot)
        return self._clone(self._draft)

    def commit_draft(self, snapshot: Mapping[str, object] | None = None) -> dict:
        if self._draft is None:
            raise RuntimeError("ProjectSession 尚無 active draft，不能提交")
        if snapshot is not None:
            self._draft = self._clone(snapshot)
        self._committed = self._clone(self._draft)
        self._draft = None
        return self._clone(self._committed)

    def cancel_draft(self) -> dict | None:
        self._draft = None
        return self._clone(self._committed)

    def snapshot_for_save(self) -> dict:
        if self._committed is None:
            raise RuntimeError("ProjectSession 尚無 committed snapshot，不能儲存")
        return self._clone(self._committed)

    def committed_snapshot(self) -> dict | None:
        return self._clone(self._committed)

    def loaded_baseline_snapshot(self) -> dict | None:
        return self._clone(self._loaded_baseline)

    def draft_snapshot(self) -> dict | None:
        return self._clone(self._draft)
