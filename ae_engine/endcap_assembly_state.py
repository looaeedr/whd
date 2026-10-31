# -*- coding: utf-8 -*-
"""Headless Engine owner for legacy EndCap Assembly Intent corner-state projection.

The original CornerType conversion and explicit-preset semantics are preserved.
All physical corner policies remain owned by ae_engine.corner_type_ui and the
Assembly Intent / Assembly Joint canonical registries; no GUI reverse import.
"""
from __future__ import annotations

from .assembly_intent import normalize_assembly_intent_id
from .corner_type_ui import apply_box_assembly_type
from .endcap_factory_fold import selection_from_raw
from .sheetmetal_geometry import CornerTypeId, normalize_corner_selection


def legacy_corner_projection_for_intent(value) -> CornerTypeId:
    """Project the canonical high-level Assembly Intent to legacy corner shape.

    WRAP_OVERLAY is NOT ordinary OVERLAY: only this old corner-state mirror
    uses OVERLAY; the actual BOTTOM WRAP belongs to Assembly Joint Graph.
    """
    stable = normalize_assembly_intent_id(getattr(value, "value", value))
    if stable == "WRAP_OVERLAY":
        return CornerTypeId.OVERLAY
    return CornerTypeId(stable)


def endcap_corner_selection_to_raw(selection):
    selection = normalize_corner_selection(selection)
    raw = {"type_id": selection.type_id.value, "rotation_quadrants": 0}
    if selection.cross_mode is not None:
        raw["cross_mode"] = selection.cross_mode.value
    if selection.direction is not None:
        raw["direction"] = selection.direction.value
    if selection.amount_t is not None:
        raw["amount_t"] = float(selection.amount_t)
    if selection.secondary_retain_t is not None:
        raw["secondary_retain_t"] = float(selection.secondary_retain_t)
    if selection.secondary_depth_t is not None:
        raw["secondary_depth_t"] = float(selection.secondary_depth_t)
    return raw



def apply_box_assembly_type_to_raw_state(
    corner_state, pair_same, type_id, *, reset_bottom_defaults=False
):
    """Apply shared box assembly semantics to the bridge's JSON-safe corner state.

    ``reset_bottom_defaults`` is reserved for an explicit operator assembly
    selection.  Normal load/render synchronization leaves manually edited
    EndCap bottom manufacturing corners untouched.
    """
    typed = {}
    for part in ("head", "tail"):
        typed[part] = {
            key: selection_from_raw(value)
            for key, value in dict((corner_state or {}).get(part) or {}).items()
        }
    apply_box_assembly_type(
        typed, pair_same, CornerTypeId(type_id),
        reset_bottom_defaults=bool(reset_bottom_defaults),
    )
    for part, corners in typed.items():
        target = corner_state.setdefault(part, {})
        target.clear()
        target.update({key: endcap_corner_selection_to_raw(value) for key, value in corners.items()})
    return CornerTypeId(type_id)


