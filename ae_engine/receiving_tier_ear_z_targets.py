# -*- coding: utf-8 -*-
"""#1503: per-tier, read-only fixing-plate Z TARGETS, not weld approvals.

Single-tier actual Base Plate skin can supply an evidenced contact target.
Two-tier Base Plate Z still inherits an unverified preview: never use that
value to claim source-verified contact or generate ear BEND / MARKING / DXF.
"""
from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from .receiving_tier_ear_assembly_xy import resolve_receiving_tier_ear_mating_xy

@dataclass(frozen=True)
class ReceivingTierEarContactTarget:
    ear_id: str
    parent_base_id: str
    layer_index: int
    side: str
    fixing_hole_world_x_mm: float
    fixing_hole_world_y_mm: tuple[float, float]
    side_inside_weld_x_mm: float
    base_back_skin_world_z_mm: float | None
    target_ear_contact_world_z_mm: float | None
    base_skin_z_source_verified: bool
    source_bend_verified: bool = False
    formed_weld_contact_verified: bool = False
    side_plate_marking_export_approved: bool = False
    manufacturing_ready: bool = False


def resolve_receiving_tier_ear_contact_targets(
    snapshot: Mapping[str, object],
) -> tuple[ReceivingTierEarContactTarget, ...]:
    """Use current per-layer source IDs and XY; never manufacture from targets."""
    rows = resolve_receiving_tier_ear_mating_xy(snapshot)
    if not rows:
        return ()
    parents = {row.parent_base_id for row in rows}
    single = parents == {"base_plate"} and len(rows) == 2
    if (len(rows) not in (2, 4)
            or len({row.ear_id for row in rows}) != len(rows)):
        raise ValueError("EAR_CONTACT_TARGET_IDENTITY_INCOMPLETE")
    base_back_z = None
    if single:
        from .receiving_base_plate_config import receiving_base_plate_values
        from .assembly_placement import resolve_base_plate_placement
        from .receiving_base_plate_real_skins import receiving_base_actual_local_nfb_skins
        physical = receiving_base_plate_values(snapshot)
        if physical is None:
            raise ValueError("EAR_CONTACT_TARGET_NO_SOURCE_PLATE")
        if (physical.get("receiving_nfb_depth_pair_mm") is not None
                or physical.get("receiving_nfb_reference_depth_mm") is not None):
            placement = resolve_base_plate_placement(snapshot, "base_plate")
            if (placement.relationship != "RECEIVING_NFB_SKIN_DEPTH"
                    or abs(float(placement.world_offset[0])) > 1e-6):
                raise ValueError("EAR_CONTACT_TARGET_UNVERIFIED_BASE_DATUM")
            front, _ = receiving_base_actual_local_nfb_skins(snapshot, physical)
            t = float(snapshot["t"])
            base_back_z = float(placement.world_offset[2]) + float(front) - t
            if not (isfinite(base_back_z) and isfinite(t) and t > 0):
                raise ValueError("EAR_CONTACT_TARGET_INVALID_BASE_SKIN")
    elif (len(rows) != 4 or parents != {
        "base_plate:nfb_layer:0", "base_plate:nfb_layer:1"
    }):
        raise ValueError("EAR_CONTACT_TARGET_TIER_OWNERS_INCOMPLETE")
    # For two tiers source-backed Z is NOT known. Even though the assembled
    # preview has root.offset[2], it does not certify either separate tier.
    output = []
    for row in rows:
        if (abs(row.base_center_x_mm) > 1e-6
                or abs(abs(row.selected_slot_column_x_mm) - 335) > 1e-6):
            raise ValueError("EAR_CONTACT_TARGET_670_HOLES_MUST_STAY_FIXED")
        output.append(ReceivingTierEarContactTarget(
            ear_id=row.ear_id, parent_base_id=row.parent_base_id,
            layer_index=row.layer_index, side=row.side,
            fixing_hole_world_x_mm=row.selected_slot_column_x_mm,
            fixing_hole_world_y_mm=row.selected_slot_pair_world_y_mm,
            side_inside_weld_x_mm=row.side_inside_weld_x_mm,
            base_back_skin_world_z_mm=base_back_z,
            target_ear_contact_world_z_mm=base_back_z,
            base_skin_z_source_verified=base_back_z is not None,
        ))
    return tuple(output)
