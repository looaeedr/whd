# -*- coding: utf-8 -*-
"""Headless Engine manual CornerType state transactions for GUI and other clients.

Moves the existing Settings write semantics unchanged; Certified Registry retains
all geometric/relief CUTTING authority. No second production formula is created.
"""
from __future__ import annotations
from copy import deepcopy
import configparser
from dataclasses import dataclass
from typing import Mapping
from .endcap_factory_fold import selection_from_raw, selection_to_raw
from .operator_settings_transactions import (normalize_operator_settings_boolean, normalize_operator_settings_updates)
from .sheetmetal_geometry import (
    CornerDirection, CornerTypeId, CornerTypeSelection, CrossCornerMode,
)

MANUAL_CORNER_KEYS = ("top_left", "top_right", "bottom_left", "bottom_right")
MANUAL_CORNER_PAIR_KEYS = {
    "top": ("top_left", "top_right"),
    "bottom": ("bottom_left", "bottom_right"),
}
CORNER_KEYS = MANUAL_CORNER_KEYS
CORNER_PAIR_KEYS = MANUAL_CORNER_PAIR_KEYS

@dataclass(frozen=True)
class CornerStateTransition:
    corner_state: dict[str, object]
    corner_pair_same: dict[str, object]
    value: object = None


def replace_corner_state(
    corner_state: Mapping[str, object] | None,
    corner_pair_same: Mapping[str, object] | None,
) -> CornerStateTransition:
    """Engine-owned detached replacement of persisted manual Corner state."""
    return CornerStateTransition(
        deepcopy(dict(corner_state or {})),
        deepcopy(dict(corner_pair_same or {})),
        None,
    )


def project_operator_corner_ini_rotation(type_id: object, value: object) -> int:
    """Engine-only legacy C02 rotation normalization for persisted Corner INI.

    A C02's saved quadrant encodes width/height manufacturing direction.
    Other types never take an INI rotation override; old wire IDs stay intact
    until the existing EndCap Corner selection codec normalizes them.
    """
    kind = str(getattr(type_id, "value", type_id) or "").strip().upper()
    if kind != CornerTypeId.C02.value:
        return 0
    return CornerTypeSelection(
        CornerTypeId.C02, rotation_quadrants=value,
    ).rotation_quadrants



def project_operator_corner_ini_load_section(options: Mapping[str, object]):
    """Project one persisted Corner INI section without file or Tk dependencies.

    The GUI supplies already-interpolated INI key/value strings.  Preserve the
    original ConfigParser boolean/integer semantics, including failure on
    malformed saved data and legacy C02-only rotation handling.
    """
    if not isinstance(options, Mapping):
        raise ValueError("CORNER_INI_SOURCE_INVALID")
    parser = configparser.ConfigParser(interpolation=None)
    parser.add_section("corner")
    for key, value in options.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError("CORNER_INI_SOURCE_INVALID")
        parser.set("corner", key, value)
    pairs = {
        "top": parser.getboolean("corner", "top_same", fallback=True),
        "bottom": parser.getboolean("corner", "bottom_same", fallback=True),
    }
    corners = {}
    for key in MANUAL_CORNER_KEYS:
        if not parser.has_option("corner", key):
            continue
        type_id = parser.get("corner", key, fallback="CROSS").strip().upper()
        rotation = project_operator_corner_ini_rotation(
            type_id, parser.getint("corner", f"{key}_rotation", fallback=0),
        )
        raw = {"type_id": type_id, "rotation_quadrants": rotation}
        for field in ("cross_mode", "direction"):
            option = f"{key}_{field}"
            if parser.has_option("corner", option):
                value = parser.get("corner", option).strip().lower()
                if value:
                    raw[field] = value
        for field in ("amount_t", "secondary_retain_t", "secondary_depth_t"):
            option = f"{key}_{field}"
            if parser.has_option("corner", option):
                normalized = normalize_operator_settings_updates(
                    {field: 0.0}, {field: parser.get("corner", option)},
                )
                if field in normalized:
                    raw[field] = normalized[field]
        corners[key] = raw
    return corners, pairs


def project_operator_corner_ini_save_options(
    corners: Mapping[str, object], pairs: Mapping[str, object],
):
    """Project CornerType source to detached INI options; None removes an option.

    No GUI client should replicate the manufacturing rotation, semantic-field
    conversion or finite-number validation performed here.
    """
    if not isinstance(corners, Mapping) or not isinstance(pairs, Mapping):
        raise ValueError("CORNER_INI_SOURCE_INVALID")
    top_same = normalize_operator_settings_boolean(pairs.get("top", True))
    bottom_same = normalize_operator_settings_boolean(pairs.get("bottom", True))
    options = {
        "top_same": "true" if top_same else "false",
        "bottom_same": "true" if bottom_same else "false",
    }
    for key in MANUAL_CORNER_KEYS:
        raw = corners.get(key)
        if not isinstance(raw, Mapping):
            continue
        type_id = str(raw.get("type_id", "CROSS")).strip().upper()
        rotation = project_operator_corner_ini_rotation(
            type_id, raw.get("rotation_quadrants", 0),
        )
        options[key] = type_id
        options[f"{key}_rotation"] = str(rotation)
        for field in (
            "cross_mode", "direction", "amount_t",
            "secondary_retain_t", "secondary_depth_t",
        ):
            value = raw.get(field)
            option = f"{key}_{field}"
            if value is None or value == "":
                options[option] = None
                continue
            if field.endswith("_t"):
                normalized = normalize_operator_settings_updates(
                    {field: 0.0}, {field: value},
                )
                if field not in normalized:
                    raise ValueError(f"截角 {field} 必須是有限數值")
                options[option] = f"{normalized[field]:g}"
            else:
                options[option] = str(getattr(value, "value", value)).strip().lower()
    return options


def ensure_corner_part(
    corner_state: Mapping[str, object] | None,
    corner_pair_same: Mapping[str, object] | None,
    part_key: str,
) -> CornerStateTransition:
    all_state = deepcopy(dict(corner_state or {}))
    all_pairs = deepcopy(dict(corner_pair_same or {}))
    part = str(part_key)
    state = all_state.setdefault(part, {})
    for corner_key in CORNER_KEYS:
        state[corner_key] = selection_to_raw(
            selection_from_raw(state.get(corner_key))
        )
    pairs = all_pairs.setdefault(part, {})
    pairs.setdefault("top", True)
    pairs.setdefault("bottom", True)
    return CornerStateTransition(all_state, all_pairs, deepcopy(state))


def project_operator_corner_pair_members(pair_key: object) -> tuple[str, str]:
    """Canonical physical pair membership for GUI clients and manufacturing.

    Unknown or malformed pair identities cannot create an accidental
    manufacturing-side target.  The returned pair is an immutable tuple.
    """
    if type(pair_key) is not str or pair_key not in MANUAL_CORNER_PAIR_KEYS:
        raise ValueError("CORNER_PAIR_KEY_INVALID")
    return MANUAL_CORNER_PAIR_KEYS[pair_key]


def project_operator_corner_selection_target(target_key: object) -> str:
    """Map UI pair selection onto the existing Engine physical corner."""
    if type(target_key) is not str:
        raise ValueError("CORNER_SELECTION_TARGET_INVALID")
    if target_key in MANUAL_CORNER_PAIR_KEYS:
        return project_operator_corner_pair_members(target_key)[0]
    if target_key in MANUAL_CORNER_KEYS:
        return target_key
    raise ValueError("CORNER_SELECTION_TARGET_INVALID")


def corner_selection(
    part_state: Mapping[str, object],
    pairs: Mapping[str, object],
    target_key: str,
) -> CornerTypeSelection:
    del pairs
    current_key = (
        CORNER_PAIR_KEYS[target_key][0]
        if target_key in CORNER_PAIR_KEYS
        else str(target_key)
    )
    return selection_from_raw(part_state[current_key])


def corner_targets(
    pairs: Mapping[str, object],
    target_key: str,
) -> tuple[str, ...]:
    del pairs
    key = str(target_key)
    if key in CORNER_PAIR_KEYS:
        return CORNER_PAIR_KEYS[key]
    return (key,)


def commit_corner_pair(
    corner_state: Mapping[str, object] | None,
    corner_pair_same: Mapping[str, object] | None,
    part_key: str,
    pair_key: str,
    enabled: bool,
) -> CornerStateTransition:
    normalized = ensure_corner_part(
        corner_state, corner_pair_same, part_key
    )
    all_state = normalized.corner_state
    all_pairs = normalized.corner_pair_same
    state = all_state[str(part_key)]
    pairs = all_pairs[str(part_key)]
    pair = str(pair_key)
    if pair not in CORNER_PAIR_KEYS:
        raise ValueError(f"unknown corner pair: {pair}")
    pairs[pair] = bool(enabled)
    if enabled:
        left_key, right_key = CORNER_PAIR_KEYS[pair]
        state[right_key] = deepcopy(state[left_key])
    return CornerStateTransition(
        all_state, all_pairs, (deepcopy(state), deepcopy(pairs))
    )


def commit_corner_type(
    corner_state: Mapping[str, object] | None,
    corner_pair_same: Mapping[str, object] | None,
    part_key: str,
    target_key: str,
    type_id: object,
) -> CornerStateTransition:
    normalized = ensure_corner_part(
        corner_state, corner_pair_same, part_key
    )
    all_state = normalized.corner_state
    all_pairs = normalized.corner_pair_same
    state = all_state[str(part_key)]
    pairs = all_pairs[str(part_key)]
    current = corner_selection(state, pairs, target_key)
    wanted = CornerTypeId(type_id)
    selection = (
        current if current.type_id is wanted else CornerTypeSelection(wanted)
    )
    raw = selection_to_raw(selection)
    for corner_key in corner_targets(pairs, target_key):
        state[corner_key] = deepcopy(raw)
    return CornerStateTransition(all_state, all_pairs, deepcopy(raw))


def commit_corner_mode(
    corner_state: Mapping[str, object] | None,
    corner_pair_same: Mapping[str, object] | None,
    part_key: str,
    target_key: str,
    mode: object,
) -> CornerStateTransition:
    normalized = ensure_corner_part(
        corner_state, corner_pair_same, part_key
    )
    all_state = normalized.corner_state
    all_pairs = normalized.corner_pair_same
    state = all_state[str(part_key)]
    pairs = all_pairs[str(part_key)]
    current = corner_selection(state, pairs, target_key)
    if current.type_id is not CornerTypeId.CROSS:
        raw = selection_to_raw(current)
        return CornerStateTransition(all_state, all_pairs, deepcopy(raw))
    selection = CornerTypeSelection(
        CornerTypeId.CROSS,
        cross_mode=CrossCornerMode(mode),
    )
    raw = selection_to_raw(selection)
    for corner_key in corner_targets(pairs, target_key):
        state[corner_key] = deepcopy(raw)
    return CornerStateTransition(all_state, all_pairs, deepcopy(raw))


def commit_corner_parameters(
    corner_state: Mapping[str, object] | None,
    corner_pair_same: Mapping[str, object] | None,
    part_key: str,
    target_key: str,
    *,
    amount_t: float | None = None,
    cross_mode: object = None,
    direction: object = None,
    secondary_retain_t: float | None = None,
    secondary_depth_t: float | None = None,
) -> CornerStateTransition:
    normalized = ensure_corner_part(
        corner_state, corner_pair_same, part_key
    )
    all_state = normalized.corner_state
    all_pairs = normalized.corner_pair_same
    state = all_state[str(part_key)]
    pairs = all_pairs[str(part_key)]
    current = corner_selection(state, pairs, target_key)
    amount = current.amount_t if amount_t is None else float(amount_t)

    if current.type_id is CornerTypeId.CROSS:
        mode = (
            current.cross_mode
            if cross_mode is None
            else CrossCornerMode(cross_mode)
        )
        if mode is CrossCornerMode.STANDARD:
            selection = CornerTypeSelection(
                CornerTypeId.CROSS,
                cross_mode=mode,
            )
        else:
            selected_direction = (
                current.direction
                if direction is None
                else CornerDirection(direction)
            )
            selection = CornerTypeSelection(
                CornerTypeId.CROSS,
                cross_mode=mode,
                direction=selected_direction,
                amount_t=amount,
            )
    elif current.type_id is CornerTypeId.OVERLAY:
        selection = CornerTypeSelection(
            CornerTypeId.OVERLAY,
            amount_t=amount,
        )
    elif current.type_id is CornerTypeId.INSERT:
        selection = CornerTypeSelection(
            CornerTypeId.INSERT,
            amount_t=amount,
        )
    else:
        selection = CornerTypeSelection(
            CornerTypeId.INSERT_OVERLAY,
            amount_t=amount,
            secondary_retain_t=(
                current.secondary_retain_t
                if secondary_retain_t is None
                else float(secondary_retain_t)
            ),
            secondary_depth_t=(
                current.secondary_depth_t
                if secondary_depth_t is None
                else float(secondary_depth_t)
            ),
        )

    raw = selection_to_raw(selection)
    for corner_key in corner_targets(pairs, target_key):
        state[corner_key] = deepcopy(raw)
    return CornerStateTransition(all_state, all_pairs, deepcopy(raw))


def apply_corner_preset(
    corner_state: Mapping[str, object] | None,
    corner_pair_same: Mapping[str, object] | None,
    fixed_corner_state: Mapping[str, object] | None,
) -> CornerStateTransition:
    next_state = deepcopy(dict(corner_state or {}))
    next_pairs = deepcopy(dict(corner_pair_same or {}))
    for part_key, corners in dict(fixed_corner_state or {}).items():
        state = next_state.setdefault(str(part_key), {})
        for corner_key, raw in dict(corners or {}).items():
            if isinstance(raw, Mapping):
                state[str(corner_key)] = selection_to_raw(
                    selection_from_raw(raw)
                )
            else:
                state[str(corner_key)] = selection_to_raw(raw)
        pairs = next_pairs.setdefault(str(part_key), {})
        pairs["top"] = True
        pairs["bottom"] = True
    return CornerStateTransition(next_state, next_pairs, None)


