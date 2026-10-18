# -*- coding: utf-8 -*-
"""#1503 source-corroborated XY witness for each tier's two side-weld ears.

The Base Plate is ALWAYS laterally centered on the CABINET X=0.
The *NFB opening group height* owns each tier Base Plate's Y, while
each switch's horizontal offset only locates its NFB screw holes.
The 670-mm ear support pitch places its left/right columns at X +/-335
regardless of selected NFB manual X. Each large source ear has 4 slots,
with the selected 210 or 140mm *longitudinal* pair centered on the same
tier Y. Left/right side-wall inner skins supply the intended weld X.

This is a 2D nominal mounting witness ONLY. The original 受電耳朵.dxf
large-ear BEND orientation, true physical skin contact Z, welding seam
and reverse projected MARKING remain unverified. No manufacturing export.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from .receiving_base_fixing_plate import (
    SOURCE_FLAT_SIZE_MM,
    receiving_base_fixing_plate_previews,
)
from .receiving_weld_ear_policy import (
    RECEIVING_ASSEMBLED_FIXING_PITCH_X_MM,
    resolve_receiving_large_weld_ear_fit,
)

STATUS = "EAR_XY_SOURCE_WITNESS_ONLY_Z_AND_MARKING_UNVERIFIED"


@dataclass(frozen=True)
class ReceivingTierEarMatingXY:
    ear_id: str
    parent_base_id: str
    layer_index: int
    side: str
    base_center_y_mm: float
    base_center_x_mm: float
    nfb_group_x_mm: float | None
    side_inside_weld_x_mm: float
    selected_slot_column_x_mm: float
    selected_slot_pair_world_y_mm: tuple[float, float]
    all_source_slots_world_y_mm: tuple[float, float, float, float]
    selected_fixing_pitch_y_mm: float
    nominal_fold_reference_mm: float
    manufacturing_status: str = STATUS

    @property
    def manufacturing_ready(self) -> bool:
        return False


def resolve_receiving_tier_ear_mating_xy(
    snapshot: Mapping[str, object],
) -> tuple[ReceivingTierEarMatingXY, ...]:
    """Read-only, current submitted Set/Bay source witness for 1/2 NFB tiers.

    Unlike a completed manufacturing locator this result has NO true Z or
    side-sheet unfolded UV. Do not call it MARKING or a certified weld.
    """
    if not isinstance(snapshot, Mapping):
        raise TypeError("RECEIVING_EAR_XY_REQUIRES_SNAPSHOT")
    if snapshot.get("nfb_config_submitted") is not True:
        return ()
    config = snapshot.get("receiving_base_plate")
    if not isinstance(config, Mapping) or not config.get("pattern"):
        return ()
    doors=tuple(
        row for row in tuple(snapshot.get("inner_doors") or ())
        if isinstance(row, Mapping)
        and str(row.get("cell_key") or "").split(":")[-1] == "0"
        and str(row.get("stable_id") or "").strip()
    )
    if len(doors) != 1:
        return ()
    from .receiving_nfb_base_assembly_xy import receiving_nfb_layer_centers
    try:
        centers = receiving_nfb_layer_centers(
            snapshot, str(doors[0]["stable_id"])
        )
    except ValueError as exc:
        if str(exc) in {
            "RECEIVING_NFB_LAYER_SET_IDENTITY_DRIFT",
            "RECEIVING_NFB_LAYER_BAY_IDENTITY_DRIFT",
            "RECEIVING_NFB_LAYER_CONFIG_IDENTITY_DRIFT",
        }:
            return ()  # Transitional GUI source is not a valid weld locator.
        raise
    if not centers:
        return ()
    if len(centers) not in (1, 2):
        raise ValueError("RECEIVING_EAR_XY_UNSUPPORTED_NFB_TIER_COUNT")
    w=float(snapshot["w"])
    t=float(snapshot["t"])
    previews = receiving_base_fixing_plate_previews(
        snapshot,
        available_parts=(
            "base_plate",
            *(center.layer_part_id for center in centers),
        ),
    )
    by_owner_side={(row.parent_part_id,row.side):row for row in previews}
    if len(by_owner_side)!=len(previews):
        raise ValueError("RECEIVING_EAR_XY_DUPLICATE_EAR_ID")
    # Source 256-mm long ear: longitudinal slot X = 23,58,198,233;
    # centre of BOTH selected pairs is 128 = 256/2, not a second
    # independently specified welding Y from a separate hole editor.
    source_mid = SOURCE_FLAT_SIZE_MM[0] / 2.0
    output=[]
    for center in centers:
        owner = (
            center.layer_part_id if len(centers)==2 else "base_plate"
        )
        y=float(center.world_y_mm)
        x=center.verified_world_x_mm
        if not isfinite(y) or (x is not None and not isfinite(float(x))):
            raise ValueError("RECEIVING_EAR_XY_NFB_CENTER_INVALID")
        # Cabinet-fixed Base Plate/ear columns do NOT depend on NFB X.
        # The NFB group X is kept separately for screw-hole CUTTING only.
        cx=0.0
        fit=None
        for side in ("left","right"):
            ear = by_owner_side.get((owner,side))
            if ear is None or ear.applicable_slot_pair_indexes is None:
                raise ValueError("RECEIVING_EAR_XY_SOURCE_PAIR_MISSING")
            first,last=ear.applicable_slot_pair_indexes
            if not (0<=first<last<4):
                raise ValueError("RECEIVING_EAR_XY_SLOT_PAIR_INVALID")
            source_slots=tuple(
                float(row[0])-source_mid
                for row in ear.nominal_source_slot_centers_mm
            )
            hole_y=(y+source_slots[first],y+source_slots[last])
            pitch_y=hole_y[1]-hole_y[0]
            fit=resolve_receiving_large_weld_ear_fit(
                box_outer_width_mm=w,box_side_thickness_mm=t,
                fixing_hole_pitch_x_mm=RECEIVING_ASSEMBLED_FIXING_PITCH_X_MM,
                fixing_hole_pitch_y_mm=pitch_y,
            )
            # Plate/side-wall support is fixed to cabinet center in X.
            # Operator X changes NFB screw holes, never these columns.
            sign=-1.0 if side=="left" else +1.0
            weld_x=sign*(w/2.0-t)
            slot_x=cx+sign*(fit.fixing_hole_pitch_x_mm/2.0)
            deviation=abs(weld_x-slot_x)
            if abs(deviation-fit.fixing_center_from_inside_skin_mm)>1e-6:
                raise ValueError("RECEIVING_EAR_XY_SIDE_SKIN_REACH_MISMATCH")
            output.append(ReceivingTierEarMatingXY(
                ear_id=ear.part_id,
                parent_base_id=ear.parent_part_id,
                layer_index=int(center.layer_index),
                side=side,
                base_center_y_mm=y,
                base_center_x_mm=cx,
                nfb_group_x_mm=float(x) if x is not None else None,
                side_inside_weld_x_mm=weld_x,
                selected_slot_column_x_mm=slot_x,
                selected_slot_pair_world_y_mm=hole_y,
                all_source_slots_world_y_mm=tuple(y+dy for dy in source_slots),
                selected_fixing_pitch_y_mm=pitch_y,
                nominal_fold_reference_mm=fit.nominal_fold_from_weld_edge_mm,
            ))
    return tuple(output)
