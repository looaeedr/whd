"""Canonical Engine owner for operator Settings numeric and dimension commits.

The GUI handles UI-only choices; physical W/H/D are never rounded, made
absolute or replaced with a default during a Save/Reload transaction.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
from typing import Mapping


PHYSICAL_DIMENSION_KEYS = frozenset({"w", "h", "d"})
PHYSICAL_SNAPSHOT_SOURCE_KEYS = ("w", "h", "d", "t", "fw")


@dataclass(frozen=True)
class OperatorSettingsCommitTransition:
    settings_values: dict[str, object]
    input_snapshot: dict[str, object]
    box_whd: dict[str, object]
    committed: dict[str, object]


@dataclass(frozen=True)
class OperatorExternalSyncPlan:
    """Engine-owned source/revision decision for operator Settings updates."""
    accepted: bool
    revision: int
    transaction_id: str
    settings: dict[str, object]
    reason: str


def plan_operator_external_sync(
    envelope: Mapping[str, object] | None, *, last_external_revision: int,
) -> OperatorExternalSyncPlan:
    """Validate the existing external Settings source/revision contract.

    Keep exact historical revision handling and fail-closed reasons so older
    GUI projects still read the same transaction; UI merely applies the plan.
    """
    raw = dict(envelope or {})
    current_revision = int(last_external_revision or 0)
    if str(raw.get("origin") or "") != "main_gui":
        return OperatorExternalSyncPlan(
            False, current_revision, "", {}, "WRONG_ORIGIN",
        )
    try:
        revision = int(raw.get("revision", 0) or 0)
    except (TypeError, ValueError):
        return OperatorExternalSyncPlan(
            False, current_revision, "", {}, "INVALID_REVISION",
        )
    if revision <= current_revision:
        return OperatorExternalSyncPlan(
            False, revision, str(raw.get("transaction_id") or ""),
            {}, "STALE_REVISION",
        )
    transaction_id = str(raw.get("transaction_id") or "")
    delta = dict(raw.get("delta") or {})
    settings = dict(delta.get("settings") or {})
    return OperatorExternalSyncPlan(
        True, revision, transaction_id, settings, "OK",
    )


def normalize_operator_settings_boolean(raw: object) -> bool:
    """Decode serialized operator bools without bool('false') == True."""
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        value = raw.strip().lower()
        if value in {"true", "1", "on", "yes"}:
            return True
        if value in {"false", "0", "off", "no", ""}:
            return False
    elif isinstance(raw, (int, float)) and not isinstance(raw, bool):
        if math.isfinite(raw) and raw in (0, 1):
            return bool(raw)
    raise ValueError("設定的布林值只接受 true/false、on/off 或 1/0")


def _positive_physical_dimension(value: object, key: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{key.upper()} 包外尺寸必須是大於 0 的有限數值")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{key.upper()} 包外尺寸必須是大於 0 的有限數值") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{key.upper()} 包外尺寸必須是大於 0 的有限數值")
    return number


def normalize_operator_source_dimension(value: object, *, field: str) -> float:
    """Validate the exact UI-supplied finished physical source before fallback.

    W/H/D, plate thickness T and frame width FW are operator manufacturing
    inputs. Absence, invalid Tk reads, bool, NaN, zero and negative values must
    not become AE factory defaults during Fold Designer Save→Reload.
    """
    name = str(field).strip().lower()
    if name not in PHYSICAL_SNAPSHOT_SOURCE_KEYS:
        raise ValueError(f"未支援的實體來源欄位：{name}")
    return _positive_physical_dimension(value, name)


def normalize_operator_source_dimensions(
    values: Mapping[str, object],
) -> dict[str, float]:
    """Read-only physical snapshot input contract, preserving fractional mm."""
    source = dict(values)
    return {
        key: normalize_operator_source_dimension(source.get(key), field=key)
        for key in PHYSICAL_SNAPSHOT_SOURCE_KEYS
    }


def normalize_operator_settings_updates(
    settings_values: Mapping[str, object],
    updates: Mapping[str, object] | None,
    *,
    external_apply_guard: bool = False,
) -> dict[str, object]:
    """Normalize physical/numeric settings independently of any GUI widget.

    Unknown keys and malformed *nonphysical* legacy numeric settings retain
    the existing skip behavior. Invalid W/H/D and explicit invalid bools cannot
    silently fall back to previously committed manufacturing values.
    UI-only choice keys are applied by the client, not inferred by Engine.
    """
    clean: dict[str, object] = {}
    for key, raw in dict(updates or {}).items():
        if key not in settings_values or key == "ui_text_size":
            continue
        if key in PHYSICAL_DIMENSION_KEYS:
            value: object = _positive_physical_dimension(raw, key)
        elif isinstance(settings_values.get(key), bool):
            value = normalize_operator_settings_boolean(raw)
        else:
            if isinstance(raw, bool):
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError, OverflowError):
                continue
            if not math.isfinite(value):
                continue
        if external_apply_guard and settings_values.get(key) == value:
            continue
        clean[key] = value
    return clean


def commit_operator_settings_state(
    settings_values: Mapping[str, object],
    input_snapshot: Mapping[str, object],
    box_whd: Mapping[str, object],
    values: Mapping[str, object] | None,
) -> OperatorSettingsCommitTransition:
    """Copy-on-write commit of the SAME physical W/H/D to each state owner.

    Any invalid physical dimension aborts before mutation. Display-only
    integer lengths in Fold editors are not the canonical enclosure W/H/D.
    """
    committed = deepcopy(dict(values or {}))
    for key in PHYSICAL_DIMENSION_KEYS:
        if key in committed:
            committed[key] = _positive_physical_dimension(committed[key], key)
    for key, raw in tuple(committed.items()):
        if key in settings_values and isinstance(settings_values[key], bool):
            committed[key] = normalize_operator_settings_boolean(raw)

    next_settings = deepcopy(dict(settings_values))
    next_snapshot = deepcopy(dict(input_snapshot))
    next_box = deepcopy(dict(box_whd))
    next_settings.update(deepcopy(committed))
    next_snapshot.update(deepcopy(committed))
    for key in PHYSICAL_DIMENSION_KEYS:
        if key in committed:
            next_box[key] = committed[key]
    return OperatorSettingsCommitTransition(
        next_settings, next_snapshot, next_box, committed
    )


def project_receiving_manufacturing_request_settings(
    input_snapshot: Mapping[str, object],
    settings_values: Mapping[str, object],
    working_box: Mapping[str, object],
) -> dict[str, object]:
    """Use Engine Family identity for current Receiving Bay request dimensions.

    The detached Settings projection must never depend on a GUI model-string
    allowlist. A malformed live physical value must not replace trusted data.
    """
    from .cabinet_types.policy import canonical_family_name

    result = deepcopy(dict(settings_values))
    if canonical_family_name(input_snapshot) != "受電箱":
        return result
    for axis in ("w", "h", "d"):
        if axis in working_box:
            result[axis] = normalize_operator_source_dimension(
                working_box[axis], field=axis,
            )
    return result
