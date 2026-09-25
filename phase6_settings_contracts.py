"""Immutable Phase 4 Settings contracts.

T1 introduces data boundaries only. Runtime Settings behavior remains owned by
Phase6SettingsTransactionController until later Phase 4 tasks.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
import hashlib
import json
from numbers import Real
from typing import Any


@dataclass(frozen=True)
class FrozenSettingsMapping(Mapping[str, Any]):
    """Small immutable, hashable, key-canonical Settings mapping."""

    _items: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        seen: set[str] = set()
        normalized: list[tuple[str, Any]] = []
        for key, value in tuple(self._items):
            skey = str(key)
            if skey in seen:
                raise ValueError(
                    f"duplicate settings mapping key after normalization: {skey!r}"
                )
            seen.add(skey)
            normalized.append((skey, value))
        normalized.sort(key=lambda item: item[0])
        object.__setattr__(self, "_items", tuple(normalized))

    def __getitem__(self, key: str) -> Any:
        skey = str(key)
        for item_key, value in self._items:
            if item_key == skey:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def items(self):
        return self._items


def _freeze_dataclass(value: Any) -> FrozenSettingsMapping:
    payload = {
        "__dataclass_type__": (
            f"{value.__class__.__module__}.{value.__class__.__qualname__}"
        )
    }
    for field in fields(value):
        payload[field.name] = getattr(value, field.name)
    frozen = freeze_settings_value(payload)
    assert isinstance(frozen, FrozenSettingsMapping)
    return frozen


def freeze_settings_value(value: Any) -> Any:
    """Recursively freeze supported Settings data and fail closed on runtime objects."""

    if isinstance(value, FrozenSettingsMapping):
        return value
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, Enum):
        return freeze_settings_value(value.value)
    if isinstance(value, Real):
        return round(float(value), 12)
    if callable(value):
        raise TypeError(f"callable is not valid Settings contract data: {value!r}")
    if isinstance(value, Mapping):
        frozen_items = []
        seen: set[str] = set()
        for key, item in value.items():
            skey = str(key)
            if skey in seen:
                raise ValueError(
                    f"duplicate Settings key after string normalization: {skey!r}"
                )
            seen.add(skey)
            frozen_items.append((skey, freeze_settings_value(item)))
        return FrozenSettingsMapping(tuple(frozen_items))
    if isinstance(value, (list, tuple)):
        return tuple(freeze_settings_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        frozen = [freeze_settings_value(item) for item in value]
        return tuple(sorted(frozen, key=repr))
    if is_dataclass(value):
        return _freeze_dataclass(value)

    module = str(getattr(value.__class__, "__module__", "") or "")
    if module == "tkinter" or module.startswith("tkinter."):
        raise TypeError(
            f"Tk object is not valid Settings contract data: "
            f"{value.__class__.__name__}"
        )
    if module == "fold_designer_bridge" or module.startswith("gui"):
        raise TypeError(
            f"application/UI object is not valid Settings contract data: "
            f"{value.__class__.__module__}.{value.__class__.__qualname__}"
        )
    raise TypeError(
        "unsupported Settings contract value "
        f"{value.__class__.__module__}.{value.__class__.__qualname__}"
    )


def _thaw_json_value(value: Any) -> Any:
    if isinstance(value, FrozenSettingsMapping):
        return {key: _thaw_json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json_value(item) for item in value]
    if value is None or isinstance(value, (bool, str, int, float)):
        return value
    if is_dataclass(value):
        return _thaw_json_value(_freeze_dataclass(value))
    raise TypeError(f"value is not canonical JSON-safe Settings data: {value!r}")


def canonical_settings_json(value: Any) -> str:
    frozen = freeze_settings_value(value)
    return json.dumps(
        _thaw_json_value(frozen),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def settings_fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_settings_json(value).encode("utf-8")).hexdigest()


def _as_mapping(value: Any, *, field_name: str) -> FrozenSettingsMapping:
    frozen = freeze_settings_value({} if value is None else value)
    if not isinstance(frozen, FrozenSettingsMapping):
        raise TypeError(f"{field_name} must be mapping-like")
    return frozen


@dataclass(frozen=True)
class SettingsStateSnapshot:
    settings_values: Any = None
    input_snapshot: Any = None
    box_whd: Any = None
    pending_settings: Any = None
    endcap_fw_state: Any = None
    endcap_bottom_wrap_state: Any = None
    corner_state: Any = None
    corner_pair_same: Any = None
    assembly_type: str = ""
    last_external_revision: int = 0
    last_external_transaction_id: str = ""
    active_transaction_id: str = ""
    debounce_pending: bool = False
    workspace_dirty: bool = False

    def __post_init__(self) -> None:
        for name in (
            "settings_values",
            "input_snapshot",
            "box_whd",
            "pending_settings",
            "endcap_fw_state",
            "endcap_bottom_wrap_state",
            "corner_state",
            "corner_pair_same",
        ):
            object.__setattr__(
                self,
                name,
                _as_mapping(getattr(self, name), field_name=name),
            )
        object.__setattr__(self, "assembly_type", str(self.assembly_type or ""))
        object.__setattr__(
            self, "last_external_revision", int(self.last_external_revision or 0)
        )
        object.__setattr__(
            self,
            "last_external_transaction_id",
            str(self.last_external_transaction_id or ""),
        )
        object.__setattr__(
            self, "active_transaction_id", str(self.active_transaction_id or "")
        )
        object.__setattr__(self, "debounce_pending", bool(self.debounce_pending))
        object.__setattr__(self, "workspace_dirty", bool(self.workspace_dirty))


@dataclass(frozen=True)
class SettingsEffect:
    kind: str
    payload: Any = None

    def __post_init__(self) -> None:
        kind = str(self.kind or "").strip()
        if not kind:
            raise ValueError("SettingsEffect.kind must be non-empty")
        object.__setattr__(self, "kind", kind)
        object.__setattr__(
            self, "payload", _as_mapping(self.payload, field_name="payload")
        )


class SettingsApplicationEffectKind(str, Enum):
    """Bounded application-effect identities for Phase 5 Settings orchestration."""

    SAVE_CURRENT_PART = "save_current_part"
    APPLY_PROFILE_PLAN = "apply_profile_plan"
    SYNC_DERIVED_PARTS = "sync_derived_parts"
    PROJECT_UI_VALUES = "project_ui_values"
    RENDER_BENDING = "render_bending"
    REFRESH_SETTINGS_PANEL = "refresh_settings_panel"
    REFRESH_TOPOLOGY = "refresh_topology"
    REFRESH_PERSISTENT_CONTROLS = "refresh_persistent_controls"
    SUBMIT_UPDATE_INTENT = "submit_update_intent"
    PUBLISH_LIVE_STATE = "publish_live_state"
    PROJECT_STATUS = "project_status"
    MARK_WORKSPACE_DIRTY = "mark_workspace_dirty"


@dataclass(frozen=True)
class SettingsApplicationEffect:
    """Immutable, fail-closed application effect request.

    This contract carries only bounded effect identity plus frozen payload data.
    Runtime callables, Tk objects, bridge/app instances, and manufacturing objects
    remain outside this pure contract.
    """

    kind: SettingsApplicationEffectKind | str
    payload: Any = None

    def __post_init__(self) -> None:
        try:
            kind = (
                self.kind
                if isinstance(self.kind, SettingsApplicationEffectKind)
                else SettingsApplicationEffectKind(str(self.kind or "").strip())
            )
        except ValueError as exc:
            raise ValueError(
                f"unknown Settings application effect kind: {self.kind!r}"
            ) from exc
        object.__setattr__(self, "kind", kind)
        object.__setattr__(
            self, "payload", _as_mapping(self.payload, field_name="payload")
        )


@dataclass(frozen=True)
class SettingsMutationResult:
    state: SettingsStateSnapshot
    updates: Any = None
    effects: Any = ()

    def __post_init__(self) -> None:
        if not isinstance(self.state, SettingsStateSnapshot):
            raise TypeError("state must be SettingsStateSnapshot")
        object.__setattr__(
            self, "updates", _as_mapping(self.updates, field_name="updates")
        )
        normalized = tuple(self.effects or ())
        if not all(isinstance(item, SettingsEffect) for item in normalized):
            raise TypeError("effects must contain SettingsEffect values")
        object.__setattr__(self, "effects", normalized)


@dataclass(frozen=True)
class SettingsStageRequest:
    key: str
    value: Any
    transaction_id: str = ""

    def __post_init__(self) -> None:
        key = str(self.key or "").strip()
        if not key:
            raise ValueError("SettingsStageRequest.key must be non-empty")
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "value", freeze_settings_value(self.value))
        object.__setattr__(
            self, "transaction_id", str(self.transaction_id or "")
        )


@dataclass(frozen=True)
class SettingsCommitRequest:
    updates: Any = None
    transaction_id: str = ""
    source: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "updates", _as_mapping(self.updates, field_name="updates")
        )
        object.__setattr__(
            self, "transaction_id", str(self.transaction_id or "")
        )
        object.__setattr__(self, "source", str(self.source or ""))


@dataclass(frozen=True)
class ExternalSettingsSyncRequest:
    revision: int
    transaction_id: str = ""
    settings_delta: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "revision", int(self.revision))
        object.__setattr__(
            self, "transaction_id", str(self.transaction_id or "")
        )
        object.__setattr__(
            self,
            "settings_delta",
            _as_mapping(self.settings_delta, field_name="settings_delta"),
        )


@dataclass(frozen=True)
class ExternalModelTransitionRequest:
    model: str
    revision: int = 0
    transaction_id: str = ""
    snapshot: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "model", str(self.model or ""))
        object.__setattr__(self, "revision", int(self.revision or 0))
        object.__setattr__(
            self, "transaction_id", str(self.transaction_id or "")
        )
        object.__setattr__(
            self, "snapshot", _as_mapping(self.snapshot, field_name="snapshot")
        )


__all__ = [
    "FrozenSettingsMapping",
    "SettingsStateSnapshot",
    "SettingsMutationResult",
    "SettingsEffect",
    "SettingsApplicationEffectKind",
    "SettingsApplicationEffect",
    "SettingsStageRequest",
    "SettingsCommitRequest",
    "ExternalSettingsSyncRequest",
    "ExternalModelTransitionRequest",
    "canonical_settings_json",
    "freeze_settings_value",
    "settings_fingerprint",
]
