"""Phase6 統一開孔編輯器的純 Python 交易狀態機。

本模組只擁有編輯器草稿的交易語意：context、selection、active edit、Undo、
Confirm/Cancel。孔位幾何、Tk、Canvas 與 manufacturing 規則不屬於此模組。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, MutableSequence, Sequence


@dataclass(frozen=True)
class HoleEditorAction:
    """封閉的開孔編輯 action。呼叫端不直接操作 Session metadata。"""

    kind: str
    index: int | None = None
    feature: Any = None
    features: tuple[Any, ...] | None = None
    selected_index: int | None = None
    keep_selected: bool = True

    @classmethod
    def select(cls, index: int) -> "HoleEditorAction":
        return cls("select", index=int(index))

    @classmethod
    def insert(cls, feature: Any) -> "HoleEditorAction":
        return cls("insert", feature=feature)

    @classmethod
    def replace_selected(cls, feature: Any) -> "HoleEditorAction":
        return cls("replace_selected", feature=feature)

    @classmethod
    def commit_active(cls, *, keep_selected: bool = True) -> "HoleEditorAction":
        return cls("commit_active", keep_selected=bool(keep_selected))

    @classmethod
    def cancel_active(cls) -> "HoleEditorAction":
        return cls("cancel_active")

    @classmethod
    def replace_selected_committed(cls, feature: Any) -> "HoleEditorAction":
        return cls("replace_selected_committed", feature=feature)

    @classmethod
    def delete_selected(cls) -> "HoleEditorAction":
        return cls("delete_selected")

    @classmethod
    def undo(cls) -> "HoleEditorAction":
        return cls("undo")

    @classmethod
    def preview_all(
        cls,
        features: Sequence[Any],
        *,
        selected_index: int = -1,
    ) -> "HoleEditorAction":
        return cls(
            "preview_all",
            features=tuple(features),
            selected_index=int(selected_index),
        )


@dataclass(frozen=True)
class HoleEditorSessionSnapshot:
    context_key: str
    selected_index: int
    features: tuple[Any, ...]
    active_edit: bool
    undo_depth: int


@dataclass
class _ContextState:
    features: MutableSequence[Any]
    original: list[Any]


class _UndoHistory:
    def __init__(self, max_steps: int) -> None:
        self.max_steps = max(1, int(max_steps))
        self._snapshots: list[list[Any]] = []

    def push(self, features: Sequence[Any]) -> None:
        self._snapshots.append(list(features))
        if len(self._snapshots) > self.max_steps:
            del self._snapshots[:-self.max_steps]

    def pop(self) -> list[Any] | None:
        if not self._snapshots:
            return None
        return list(self._snapshots.pop())

    def __len__(self) -> int:
        return len(self._snapshots)


class Phase6HoleEditorSession:
    """統一開孔編輯器的交易 owner。

    `feature_list` 保持 caller 原本的 mutable list identity；Session 只集中管理
    如何修改它，以及修改前 snapshot / Undo / context ordering。
    """

    def __init__(
        self,
        context_key: str,
        feature_list: MutableSequence[Any],
        *,
        max_undo_steps: int = 50,
    ) -> None:
        key = str(context_key)
        self._max_undo_steps = max(1, int(max_undo_steps))
        self._contexts: dict[str, _ContextState] = {
            key: _ContextState(feature_list, list(feature_list))
        }
        self._active_context_key = key
        self._selected_index = -1
        self._active_before: list[Any] | None = None
        self._undo = _UndoHistory(self._max_undo_steps)

    @property
    def active_features(self) -> MutableSequence[Any]:
        return self._context.features

    @property
    def selected_index(self) -> int:
        return self._selected_index

    @property
    def has_active_edit(self) -> bool:
        return self._active_before is not None

    @property
    def active_context_key(self) -> str:
        return self._active_context_key

    @property
    def _context(self) -> _ContextState:
        return self._contexts[self._active_context_key]

    def snapshot(self) -> HoleEditorSessionSnapshot:
        return HoleEditorSessionSnapshot(
            context_key=self._active_context_key,
            selected_index=self._selected_index,
            features=tuple(self.active_features),
            active_edit=self.has_active_edit,
            undo_depth=len(self._undo),
        )

    def execute(self, action: HoleEditorAction) -> HoleEditorSessionSnapshot:
        kind = action.kind
        if kind == "select":
            self._select(self._required_index(action.index))
        elif kind == "insert":
            self._begin_active_if_needed()
            self.active_features.append(action.feature)
            self._selected_index = len(self.active_features) - 1
        elif kind == "replace_selected":
            index = self._require_selected()
            self._begin_active_if_needed()
            self.active_features[index] = action.feature
        elif kind == "commit_active":
            self._commit_active(keep_selected=action.keep_selected)
        elif kind == "cancel_active":
            self._cancel_active()
        elif kind == "replace_selected_committed":
            index = self._require_selected()
            self._commit_active(keep_selected=True)
            before = list(self.active_features)
            self.active_features[index] = action.feature
            if before != list(self.active_features):
                self._undo.push(before)
            self._active_before = None
        elif kind == "delete_selected":
            index = self._require_selected()
            self._commit_active(keep_selected=True)
            before = list(self.active_features)
            del self.active_features[index]
            self._undo.push(before)
            self._active_before = None
            self._selected_index = -1
        elif kind == "undo":
            if self.has_active_edit:
                self._cancel_active()
            else:
                before = self._undo.pop()
                if before is not None:
                    self.active_features[:] = before
                    self._selected_index = -1
        elif kind == "preview_all":
            self._begin_active_if_needed()
            self.active_features[:] = list(action.features or ())
            index = int(action.selected_index if action.selected_index is not None else -1)
            if index != -1 and not 0 <= index < len(self.active_features):
                raise IndexError(index)
            self._selected_index = index
        else:
            raise ValueError(f"unsupported hole editor action: {kind}")
        return self.snapshot()

    def activate_context(
        self,
        context_key: str,
        feature_list: MutableSequence[Any],
    ) -> HoleEditorSessionSnapshot:
        self._cancel_active()
        key = str(context_key)
        if key in self._contexts:
            self._contexts[key].features = feature_list
        else:
            self._contexts[key] = _ContextState(feature_list, list(feature_list))
        self._active_context_key = key
        self._selected_index = -1
        self._active_before = None
        # 舊版每次切 context 都重建 EditorUndoHistory；保持相同行為。
        self._undo = _UndoHistory(self._max_undo_steps)
        return self.snapshot()

    def finish(self, *, commit: bool) -> HoleEditorSessionSnapshot:
        if commit:
            # Confirm All 保留目前畫面上的 transient 結果，但不需要再建立 Undo，
            # 因為 editor 即將關閉。
            self._active_before = None
        else:
            for state in self._contexts.values():
                state.features[:] = state.original
            self._active_before = None
        self._selected_index = -1
        return self.snapshot()

    def _required_index(self, index: int | None) -> int:
        if index is None:
            raise ValueError("action requires index")
        index = int(index)
        if not 0 <= index < len(self.active_features):
            raise IndexError(index)
        return index

    def _require_selected(self) -> int:
        return self._required_index(self._selected_index)

    def _select(self, index: int) -> None:
        if self.has_active_edit and self._selected_index != index:
            self._commit_active(keep_selected=True)
        self._selected_index = index
        self._begin_active_if_needed()

    def _begin_active_if_needed(self) -> None:
        if self._active_before is None:
            self._active_before = list(self.active_features)

    def _commit_active(self, *, keep_selected: bool) -> None:
        if self._active_before is not None:
            before = self._active_before
            if before != list(self.active_features):
                self._undo.push(before)
        self._active_before = None
        if not keep_selected:
            self._selected_index = -1

    def _cancel_active(self) -> bool:
        if self._active_before is None:
            return False
        self.active_features[:] = self._active_before
        self._active_before = None
        self._selected_index = -1
        return True
