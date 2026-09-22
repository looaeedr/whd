"""Neutral live-sync envelope helpers for Main GUI <-> Fold Designer.

This module owns transport planning/metadata only. It does not own callbacks,
Tk state, mechanical state, geometry, persistence, or manufacturing rules.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


def _json_default(value):
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return enum_value
    if isinstance(value, set):
        return sorted(value, key=repr)
    return repr(value)


def stable_fingerprint(value) -> str:
    text = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def actual_delta(before, after):
    """Return only semantically changed mapping leaves; lists are atomic."""
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        out = {}
        for key in after:
            if key not in before:
                out[key] = deepcopy(after[key])
                continue
            child = actual_delta(before[key], after[key])
            if child is not _UNCHANGED:
                out[key] = child
        return out if out else _UNCHANGED
    if before == after:
        return _UNCHANGED
    return deepcopy(after)


class _Unchanged:
    pass


_UNCHANGED = _Unchanged()


def mapping_delta(before, after) -> dict:
    delta = actual_delta(before or {}, after or {})
    return {} if delta is _UNCHANGED else dict(delta)


class _FrozenList(tuple):
    pass


class _FrozenTuple(tuple):
    pass


def _freeze_sync_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {key: _freeze_sync_value(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return _FrozenList(_freeze_sync_value(item) for item in value)
    if isinstance(value, tuple):
        return _FrozenTuple(_freeze_sync_value(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze_sync_value(item) for item in value)
    return deepcopy(value)


def materialize_sync_value(value: Any) -> Any:
    """Return a detached plain representation of an immutable sync plan value."""
    if isinstance(value, Mapping):
        return {
            key: materialize_sync_value(item)
            for key, item in value.items()
        }
    if isinstance(value, _FrozenList):
        return [materialize_sync_value(item) for item in value]
    if isinstance(value, _FrozenTuple):
        return tuple(materialize_sync_value(item) for item in value)
    if isinstance(value, frozenset):
        return {materialize_sync_value(item) for item in value}
    return deepcopy(value)


@dataclass(frozen=True)
class LiveSyncPublicationPlan:
    """Pure publication decision/result; contains no callback or runtime owner."""

    should_publish: bool
    next_revision: int
    transaction_id: str
    delta: Any
    fingerprint: str
    payload: Any
    host_relief_repair: Any

    def __post_init__(self) -> None:
        object.__setattr__(self, "should_publish", bool(self.should_publish))
        object.__setattr__(self, "next_revision", int(self.next_revision))
        object.__setattr__(self, "transaction_id", str(self.transaction_id or ""))
        object.__setattr__(self, "delta", _freeze_sync_value(self.delta or {}))
        object.__setattr__(
            self,
            "payload",
            None if self.payload is None else _freeze_sync_value(self.payload),
        )
        object.__setattr__(
            self,
            "host_relief_repair",
            _freeze_sync_value(self.host_relief_repair or {}),
        )


def plan_live_sync_envelope(
    *,
    current_state,
    previous_state,
    previous_fingerprint,
    current_revision,
    active_transaction_id,
    host_relief_present,
    host_relief,
    force=False,
) -> LiveSyncPublicationPlan:
    """Plan one Fold Designer publication without performing runtime effects."""
    state = deepcopy(dict(current_state or {}))
    fingerprint = stable_fingerprint(state)
    current_revision = int(current_revision or 0)
    canonical_relief = deepcopy(state.get("assembly_relief") or {})
    host_relief = deepcopy(host_relief or {})

    force_host_relief_sync = bool(
        force
        and host_relief_present
        and stable_fingerprint(host_relief)
        != stable_fingerprint(canonical_relief)
    )

    if fingerprint == previous_fingerprint and not force_host_relief_sync:
        return LiveSyncPublicationPlan(
            should_publish=False,
            next_revision=current_revision,
            transaction_id=str(active_transaction_id or "").strip(),
            delta={},
            fingerprint=fingerprint,
            payload=None,
            host_relief_repair=canonical_relief,
        )

    previous = deepcopy(dict(previous_state or {}))
    if force_host_relief_sync:
        previous = deepcopy(state)
        previous["assembly_relief"] = host_relief

    delta = mapping_delta(previous, state)
    if not delta and previous:
        return LiveSyncPublicationPlan(
            should_publish=False,
            next_revision=current_revision,
            transaction_id=str(active_transaction_id or "").strip(),
            delta={},
            fingerprint=fingerprint,
            payload=None,
            host_relief_repair=canonical_relief,
        )

    next_revision = current_revision + 1
    transaction_id = (
        str(active_transaction_id or "").strip()
        or f"fold_designer:{next_revision}"
    )
    payload = deepcopy(state)
    payload.update(
        {
            "origin": "fold_designer",
            "revision": next_revision,
            "transaction_id": transaction_id,
            "delta": deepcopy(delta),
            "fingerprint": fingerprint,
        }
    )
    return LiveSyncPublicationPlan(
        should_publish=True,
        next_revision=next_revision,
        transaction_id=transaction_id,
        delta=delta,
        fingerprint=fingerprint,
        payload=payload,
        host_relief_repair=canonical_relief,
    )


__all__ = [
    "LiveSyncPublicationPlan",
    "actual_delta",
    "mapping_delta",
    "materialize_sync_value",
    "plan_live_sync_envelope",
    "stable_fingerprint",
]
