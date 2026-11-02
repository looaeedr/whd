# -*- coding: utf-8 -*-
"""Engine-owned Receiving operator projection and Family capability.

These are read-only projections of the existing canonical Receiving defaults,
Family registry and BoxBody topology.  They do not grant manufacturing export.
"""
from __future__ import annotations

from .box_body_structure_state import BoxBodyStructureType
from .cabinet_types.policy import canonical_family_name
from .cabinet_types.receiving import BOX_BODY_DEFAULTS


def receiving_default_box_dimensions() -> dict[str, int]:
    """Fresh W/H/D operator values from Receiving Family, never a shared dict."""
    return {axis: int(BOX_BODY_DEFAULTS[axis]) for axis in ("w", "h", "d")}


def receiving_default_preview_dimensions(snapshot) -> tuple[float, float, float]:
    """Read-only active mode dimensions for the Receiving settings preview."""
    data = dict(snapshot or {})
    if data.get("active_mode") == "quantity":
        box = data.get("receiving_quantity_box") or BOX_BODY_DEFAULTS
    else:
        sets = (data.get("receiving_layout") or {}).get("sets") or ()
        bays = sets[0].get("bays") or () if sets else ()
        box = ({"w": bays[0]["width"], "h": bays[0]["height"],
                "d": bays[0]["depth"]} if bays else BOX_BODY_DEFAULTS)
    return tuple(float(box[axis]) for axis in ("w", "h", "d"))


def receiving_family_supports_back_panel_mode(snapshot) -> bool:
    """Use the registered Family identity, never GUI string matching."""
    return canonical_family_name(snapshot) == "受電箱"


def receiving_back_panel_mode_control_applicable(snapshot, structure_state) -> bool:
    """Only Receiving's physical three-piece side/back split exposes this mode."""
    return (
        receiving_family_supports_back_panel_mode(snapshot)
        and str((structure_state or {}).get("active_type") or "")
        == BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
    )
