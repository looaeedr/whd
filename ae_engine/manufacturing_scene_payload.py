# -*- coding: utf-8 -*-
"""Manufacturing scene payload source decisions, no GUI or Tk dependency.

The GUI supplies edited fields; the Engine alone decides Set/Bay persisted
identity, authoritative Joint source and Family bottom-relief reserve policy.
No new geometry/production certification is issued by these projections.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

from .receiving_layout import (
    RECEIVING_DOOR_STATE_KEYS, RECEIVING_RUNTIME_SELECTION_KEY,
)
from .assembly_joint import migrate_legacy_snapshot_joints
from .endcap_factory_fold import ENDCAP_FW_PARTS
from .endcap_bottom_wrap_state import resolve_endcap_bottom_wrap
from .cabinet_types import policy as cabinet_family_policy


def project_manufacturing_scene_settings_overlay(snapshot, global_settings):
    """Keep selected Receiving Set/Bay Door/NFB source from being overwritten.

    Preserves legacy unrestricted/global overlays when there is no committed
    active Receiving runtime selection. Returns a detached dict.
    """
    overlay = dict(global_settings or {})
    if (
        isinstance(snapshot, Mapping)
        and snapshot.get("model") in ("受電箱", "RECEIVING")
        and isinstance(snapshot.get(RECEIVING_RUNTIME_SELECTION_KEY), Mapping)
    ):
        per_bay = set(RECEIVING_DOOR_STATE_KEYS) | {
            RECEIVING_RUNTIME_SELECTION_KEY, "receiving_layout",
            "nfb_config", "nfb_config_submitted",
        }
        overlay = {key: value for key, value in overlay.items() if key not in per_bay}
    return overlay


def project_manufacturing_scene_joint_source(source_snapshot):
    """Project one canonical persisted assembly graph for every scene part."""
    graph = migrate_legacy_snapshot_joints(dict(source_snapshot or {}))
    return {
        "assembly_joint_schema_version": graph.get("assembly_joint_schema_version"),
        "assembly_joints": deepcopy(graph.get("assembly_joints", ())),
    }


def project_manufacturing_bottom_relief_structure(
    snapshot, part_key, box_body_structure, *, bottom_wrap_state=None,
):
    """Carry existing Family EndCap BOTTOM reserve fields into a scene.

    This is not a relief manufacturing approval. Keep the legacy display
    fallback on unsupported Family or transient incomplete editor state.
    """
    if part_key not in ENDCAP_FW_PARTS:
        return box_body_structure
    if not cabinet_family_policy.supports_bottom_wrap_controls(snapshot):
        return box_body_structure
    try:
        item = resolve_endcap_bottom_wrap(
            snapshot, part_key, state=bottom_wrap_state,
        )
        return cabinet_family_policy.set_bottom_relief_reserves(
            snapshot, box_body_structure,
            reserve_u=item["reserve_u"], reserve_v=item["reserve_v"],
        )
    except Exception:
        # Preserve pre-existing scene-edit fallback, not manufacturing release.
        return box_body_structure
