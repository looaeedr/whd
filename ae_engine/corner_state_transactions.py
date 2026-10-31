# -*- coding: utf-8 -*-
"""Headless Engine manual CornerType state transactions for GUI and other clients.

Moves the existing Settings write semantics unchanged; Certified Registry retains
all geometric/relief CUTTING authority. No second production formula is created.
"""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
from typing import Mapping
from .endcap_factory_fold import selection_from_raw, selection_to_raw
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


