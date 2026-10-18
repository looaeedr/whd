# -*- coding: utf-8 -*-
"""#1503: source-anchored left/right ear installation targets, NOT machine release.

The large original 受電耳朵.dxf has no independently verified BEND direction
or station. Therefore these targets identify only the required final contact
surfaces and welded-ear bolt locations. They must not fabricate a formed ear,
issue side-wall MARKING, or make its manufacturing_ready flag True.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping


@dataclass(frozen=True)
class ReceivingFixingPlateInstallationTarget:
    part_id: str
    side: str
    welded_side_inside_world_x_mm: float
    fixing_hole_world_x_mm: float
    fixing_hole_world_y_mm: tuple[float, float]
    base_back_skin_world_z_mm: float
    fixing_plate_contact_skin_world_z_mm: float
    fixing_plate_back_skin_world_z_mm: float
    selected_source_slot_indexes: tuple[int, int]
    source_bend_verified: bool = False
    formed_weld_contact_verified: bool = False
    side_plate_marking_export_approved: bool = False
    manufacturing_ready: bool = False


def resolve_receiving_fixing_plate_installation_targets(
    snapshot: Mapping[str, object],
) -> tuple[ReceivingFixingPlateInstallationTarget, ...]:
    """Two physical ears move with the correctly positioned original Base Plate.

    Use the SAME live submitted NFB pair and real base 3D assembly Z plus the
    verified original source ear's nominal LEFT/RIGHT XY slot mating.
    No artificial cut/BEND or MARKING is emitted from this target function.
    """
    from .assembly_placement import resolve_base_plate_placement
    from .receiving_base_plate_config import receiving_base_plate_values
    from .receiving_base_plate_real_skins import receiving_base_actual_local_nfb_skins
    from .receiving_base_fixing_plate_mating import resolve_base_fixing_pair_xy_mating
    if not isinstance(snapshot, Mapping):
        raise TypeError("fixing plate requires real Receiving snapshot")
    physical=receiving_base_plate_values(snapshot)
    if physical is None:
        return ()
    pair=physical.get("receiving_nfb_depth_pair_mm")
    single=physical.get("receiving_nfb_reference_depth_mm")
    if pair is None and single is None:
        return ()
    placement=resolve_base_plate_placement(snapshot,"base_plate")
    if placement.relationship!="RECEIVING_NFB_SKIN_DEPTH":
        raise ValueError("FIXING_PLATE_CANNOT_FOLLOW_UNCERTIFIED_BASE_Z")
    # Real manufactured source base skin owns Z, not an unrelated nominal
    # rear-side 20-mm bend or the ear's unverified 23-mm fold reference.
    local_front,_=receiving_base_actual_local_nfb_skins(snapshot,physical)
    base_front=placement.world_offset[2]+local_front
    t=float(snapshot["t"])
    if not isfinite(base_front) or not isfinite(t) or t<=0:
        raise ValueError("FIXING_PLATE_INVALID_REAL_BASE_SKIN")
    back=base_front-t
    if abs(float(placement.world_offset[0]))>1e-7:
        raise ValueError("FIXING_PLATE_BASE_BOLT_COLUMNS_ARE_NOT_CENTERED")
    left,right=resolve_base_fixing_pair_xy_mating(snapshot)
    out=[]
    for source in (left,right):
        ear_t=3.0  # source original 受電耳朵.dxf; validated in mating fit
        if abs(float(source.selected_fixing_world_x_mm))!=335.0:
            raise ValueError("FIXING_PLATE_SOURCE_BOLT_X_PITCH_DRIFT")
        if abs(float(source.inside_skin_world_x_mm))!=398.0:
            raise ValueError("FIXING_PLATE_SIDE_INSIDE_SKIN_DRIFT")
        y_pair=tuple(float(placement.world_offset[1])+float(v)
                     for v in source.selected_fixing_world_y_mm)
        if len(y_pair)!=2:
            raise ValueError("FIXING_PLATE_SOURCE_Y_SLOT_PAIR_INVALID")
        if abs((y_pair[1]-y_pair[0])-source.selected_fixing_pitch_y_mm)>1e-7:
            raise ValueError("FIXING_PLATE_SOURCE_Y_PITCH_DRIFT")
        out.append(ReceivingFixingPlateInstallationTarget(
            part_id=source.part_id,side=source.side,
            welded_side_inside_world_x_mm=source.inside_skin_world_x_mm,
            fixing_hole_world_x_mm=source.selected_fixing_world_x_mm,
            fixing_hole_world_y_mm=y_pair,
            base_back_skin_world_z_mm=back,
            fixing_plate_contact_skin_world_z_mm=back,
            fixing_plate_back_skin_world_z_mm=back-ear_t,
            selected_source_slot_indexes=source.selected_slot_indexes,
        ))
    if (out[0].fixing_hole_world_x_mm,out[1].fixing_hole_world_x_mm)!=(-335.,335.):
        raise ValueError("FIXING_PLATE_SOURCE_OPPOSING_HOLE_PITCH_DRIFT")
    if out[0].fixing_hole_world_y_mm != out[1].fixing_hole_world_y_mm:
        raise ValueError("FIXING_PLATE_OPPOSING_BOLT_ROWS_DRIFT")
    return tuple(out)
