# -*- coding: utf-8 -*-
"""Engine-owned Assembly Intent state commit (Joint Graph + legacy Corner mirror).

A GUI may supply available physical parts as temporary execution context, but
only the input snapshot is the project's persisted source. Registry-backed
Assembly Intent and Engine Joint Graph own all manufacturing semantics.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Mapping

from .assembly_intent import normalize_assembly_intent_id
from .assembly_joint import sync_snapshot_intent_joints
from .endcap_factory_fold import (
    apply_box_assembly_type_to_raw_state as apply_endcap_box_assembly_type_to_raw_state,
    legacy_corner_projection_for_intent as legacy_endcap_corner_projection_for_intent,
)
from .sheetmetal_geometry import CornerTypeId


@dataclass(frozen=True)
class AssemblyIntentTransition:
    input_snapshot: dict[str, object]
    corner_state: dict[str, object]
    corner_pair_same: dict[str, object]
    assembly_type: object


def normalize_assembly_type(value: object) -> object:
    """Keep the historical enum/string response while validating the Registry."""
    stable = normalize_assembly_intent_id(value)
    return stable if stable == "WRAP_OVERLAY" else CornerTypeId(stable)


def commit_assembly_intent_state(
    input_snapshot: Mapping[str, object],
    corner_state: Mapping[str, object] | None,
    corner_pair_same: Mapping[str, object] | None,
    type_id: object,
    *,
    available_parts: tuple[object, ...] | list[object] = (),
    project_legacy_corner: bool = False,
    reset_bottom_defaults: bool = False,
) -> AssemblyIntentTransition:
    canonical = normalize_assembly_type(type_id)
    stable = normalize_assembly_intent_id(type_id)
    snapshot = deepcopy(dict(input_snapshot))
    corners = deepcopy(dict(corner_state or {}))
    pairs = deepcopy(dict(corner_pair_same or {}))
    parts = tuple(str(key) for key in tuple(available_parts or ()) if str(key))
    had_existing_parts = "existing_parts" in snapshot
    authoritative_existing_parts = deepcopy(snapshot.get("existing_parts"))
    if parts:
        # available_parts is an execution context for joint projection only.
        # The predecessor controller never promoted this temporary live
        # workspace list into authoritative project topology.
        snapshot["existing_parts"] = list(parts)
    snapshot = sync_snapshot_intent_joints(snapshot, canonical)
    if had_existing_parts:
        snapshot["existing_parts"] = authoritative_existing_parts
    else:
        snapshot.pop("existing_parts", None)
    if project_legacy_corner:
        apply_endcap_box_assembly_type_to_raw_state(
            corners,
            pairs,
            legacy_endcap_corner_projection_for_intent(stable),
            reset_bottom_defaults=bool(reset_bottom_defaults),
        )
    return AssemblyIntentTransition(
        input_snapshot=snapshot,
        corner_state=corners,
        corner_pair_same=pairs,
        assembly_type=canonical,
    )




def commit_box_assembly_joint_state(
    prior_state: Mapping[str, object] | None,
    type_id: object,
    *,
    available_parts,
) -> dict[str, object]:
    """Commit main GUI's independent Joint state through the canonical Engine.

    Unlike persisted project AssemblyIntentTransition, the main window Joint
    workspace explicitly keeps its active physical parts.  Legacy snapshots
    must use the operator's newly selected intent at migration time, before
    the normal v2 intent sync.  The input is detached and never partially
    modified on invalid values.
    """
    stable = normalize_assembly_intent_id(type_id)
    state = deepcopy(dict(prior_state or {}))
    state["existing_parts"] = list(available_parts)
    if not state.get("assembly_joint_schema_version"):
        state["assembly_type"] = stable
        from .assembly_joint import migrate_legacy_snapshot_joints
        state = migrate_legacy_snapshot_joints(state)
    return sync_snapshot_intent_joints(state, stable)
