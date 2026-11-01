# -*- coding: utf-8 -*-
"""Immutable manufacturing cache-source plan owned by the headless Engine.

Receiving undo receipts may be kept only while the physical baseline source
and the active multipart BoxBody structure have unambiguous provenance.
No GUI/phase6 or Tk imports. This is a cache policy, not MFG release.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .box_body_structure_state import BoxBodyStructureType


@dataclass(frozen=True)
class ManufacturingCacheSourcePlan:
    history_capacity: int
    witness_required: bool
    include_physical_panels: bool


def plan_manufacturing_cache_source(snapshot, workspace_structure=None):
    """Resolve exact old Receiving undo eligibility and physical DXF coverage.

    Unknown structure must NOT certify cached material; the GUI clears old
    receipts instead of silently retaining a prior 3-piece sheet.
    """
    eligible = (
        isinstance(snapshot, Mapping)
        and str(snapshot.get("model") or "") in {"受電箱", "RECEIVING"}
        and snapshot.get("active_mode") == "set_bay"
    )
    if not eligible:
        return ManufacturingCacheSourcePlan(1, False, False)
    structure = workspace_structure
    if not structure and isinstance(snapshot.get("box_body_structure"), Mapping):
        structure = snapshot["box_body_structure"]
    active = (
        getattr(structure.get("active_type"), "value", structure.get("active_type"))
        if isinstance(structure, Mapping) else None
    )
    recognized = {kind.value for kind in BoxBodyStructureType}
    if active not in recognized:
        return ManufacturingCacheSourcePlan(2, False, False)
    return ManufacturingCacheSourcePlan(
        2, True,
        active == BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value,
    )
