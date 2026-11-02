# -*- coding: utf-8 -*-
"""Canonical Settings -> physical Fold profile projection for headless and GUI.

Only the Engine selects physical panels, merges operator-added folds, normalizes
Tail topology, and produces the authoritative profile plan. Callers supply
operator inputs; they do not reconstruct fabrication data.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Mapping

from .box_body_fold_profile import (
    build_box_body_profile,
    merge_box_body_fold_profile,
)
from .custom_fold_api import build_custom_part_profiles
from .custom_part_catalog import is_custom_part
from .endcap_factory_fold import (
    build_endcap_xy_fold_profiles,
    normalize_endcap_profile_order,
)
from .keyed_fold_reconciliation import merge_keyed_fold_profiles
from .part_dimension_projection import project_part_dimensions
from .physical_part_identity import is_derived_physical_part_key
from .standard_part_fold_profiles import build_standard_part_fold_profiles


def plan_operator_settings_fold_profiles(
    *,
    settings_values: Mapping[str, object],
    input_snapshot: Mapping[str, object],
    available_parts: tuple[str, ...] = (),
    existing_profiles: Mapping[str, object] | None = None,
    box_body_profile=(),
    active_part: str = "box_body",
    reset_box_profile: bool = False,
    reset_all_profiles: bool = False,
) -> dict:
    """Return detached physical profiles and dimensions without GUI state.

    This preserves keyed operator-added segments and saved Tail Y ordering,
    while deriving every reset/merge and derived-part exclusion in Engine.
    """
    snapshot = deepcopy(dict(input_snapshot or {}))
    snapshot.update(deepcopy(dict(settings_values or {})))
    part_dimensions = project_part_dimensions(snapshot)
    snapshot["part_dimensions"] = part_dimensions

    current_box = deepcopy(list(box_body_profile or ()))
    box_profile = (
        build_box_body_profile(snapshot)
        if reset_box_profile
        else merge_box_body_fold_profile(current_box, snapshot)
    )

    saved = deepcopy(dict(existing_profiles or {}))
    planned = {}
    for key in tuple(available_parts or ()):
        if key == "box_body" or is_derived_physical_part_key(key):
            continue
        if key in {"head", "tail"}:
            defaults = build_endcap_xy_fold_profiles(snapshot, part_key=key)
        elif is_custom_part(key):
            defaults = build_custom_part_profiles(snapshot, key)
        else:
            defaults = build_standard_part_fold_profiles(snapshot, key)
        existing = dict(saved.get(key, {}) or {})
        updated = (
            defaults
            if reset_all_profiles
            else merge_keyed_fold_profiles(existing, defaults)
        )
        if key in {"head", "tail"}:
            updated = normalize_endcap_profile_order(updated, snapshot, key)
        planned[key] = updated

    active_profiles = {}
    if active_part == "box_body":
        active_profiles = {"X": box_profile}
    elif active_part in planned and not is_derived_physical_part_key(active_part):
        active_profiles = planned[active_part]

    return {
        "snapshot": snapshot,
        "part_dimensions": part_dimensions,
        "box_body_profile": box_profile,
        "part_profiles": planned,
        "active_part": active_part,
        "active_profiles": active_profiles,
        "derived_sync_required": True,
    }
