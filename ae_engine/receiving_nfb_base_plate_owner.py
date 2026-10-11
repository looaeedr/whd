# -*- coding: utf-8 -*-
"""#1502 identify actual upper Receiving Base Plate from real physical inventory.

The existing base_plate_cN_rN already has a stable Phase6 identity and
assembly placement. Never substitute legacy whole-cabinet base_plate, infer
a new plate name, move the plate, or approve a DXF from source colors alone.
The NFB center/X is inherited from the already verified INNER-DOOR source.
This returns physical *ownership evidence*, not a machining UV or permit.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from .assembly_placement import resolve_base_plate_placement
from .cabinet_types import policy as cabinet_family_policy
from .receiving_nfb_manufacturing_release import (
    NfbValidatedInnerDoorRender, VALIDATED,
)
from .receiving_nfb_upper_base_source import NfbUpperBaseSourceProcess

IDENTIFIED = "MFG2_BASE_UPPER_REAL_PHYSICAL_OWNER_IDENTIFIED_UV_NOT_CERTIFIED"


@dataclass(frozen=True)
class NfbUpperBasePlateOwner:
    physical_part_id: str
    nfb_inner_door_part_id: str
    source_sha256: str
    source_color150_handle: str
    receiving_cell_key: str
    assembly_anchor: str
    unchanged_world_offset: tuple[float, float, float]
    physical_blank_width_mm: float
    physical_blank_height_mm: float
    status: str = IDENTIFIED
    manufacturing_ready: bool = False


def resolve_upper_nfb_base_plate_owner(
    snapshot: Mapping[str, object],
    resolved_geometry,
    *,
    verified_inner_door: NfbValidatedInnerDoorRender,
    source_process: NfbUpperBaseSourceProcess,
) -> NfbUpperBasePlateOwner:
    """Select by real assembly anchor after checking actual resolved parts.

    No "base_plate_c1_r1" construction or guessing from W/2, filenames,
    color count or Bay number. An absent/multiple physical plate fails closed.
    """
    if not isinstance(snapshot,Mapping) or (
            snapshot.get("model")!="受電箱" or not snapshot.get("multi_door_enabled")):
        raise ValueError("NFB base owner needs current Receiving physical layout")
    if not isinstance(source_process,NfbUpperBaseSourceProcess):
        raise TypeError("NFB upper base owner needs the native DXF source process")
    if (source_process.manufacturing_ready
            or not source_process.base_cutting_circles
            or not source_process.base_marking_entities):
        raise ValueError("NFB base Color30/212 source identity incomplete")
    if (not isinstance(verified_inner_door,NfbValidatedInnerDoorRender)
            or not verified_inner_door.manufacturing_ready
            or verified_inner_door.source_sha256!=source_process.source_sha256
            or verified_inner_door.indexed_model_key[1]
               !=source_process.indexed_filename):
        raise ValueError("NFB verified inner-door/source identity mismatch")
    metadata=getattr(verified_inner_door.render_data,"metadata",{})
    if (metadata.get("nfb_trial_status")!=VALIDATED
            or metadata.get("nfb_trial_export_approved") is not True
            or metadata.get("nfb_source_handle")
               !=source_process.source_sha256+":"+source_process.upper_color150_handle):
        raise ValueError("NFB base source pivot not the verified inner-door Color150")
    inner=tuple(
        p for p in cabinet_family_policy.derive_inner_door_panels(snapshot)
        if p.stable_id==verified_inner_door.part_id
    )
    if len(inner)!=1:
        raise ValueError("NFB base cannot identify unique verified upper inner door")
    cell=str(inner[0].cell_key)
    if not cell.endswith(":0") or not cell.count(":")==1:
        raise ValueError("NFB base candidate is not bound to an upper physical cell")
    try:
        column,row=(int(x) for x in cell.split(":"))
    except ValueError as exc:
        raise ValueError("NFB upper cell key has invalid physical indices") from exc
    if column<0 or row!=0 or cell!=f"{column}:{row}":
        raise ValueError("NFB upper cell key is noncanonical")
    anchor=f"door_layout_cell:{column}:{row}:base_plate"
    parts=tuple(getattr(resolved_geometry,"parts",()) or ())
    if not parts:
        raise ValueError("NFB base requires real resolved physical parts")
    physical=[]
    seen=set()
    for part in parts:
        key=str(getattr(part,"part_key","") or "")
        if not key or key in seen:
            raise ValueError("NFB resolved physical identity missing/duplicate")
        seen.add(key)
        if not key.startswith("base_plate_c"):
            # Legacy "base_plate" has a different assembly contract and
            # cannot stand in for an actual upper Receiving cell.
            continue
        try:
            placement=resolve_base_plate_placement(snapshot,key)
        except ValueError:
            raise ValueError("NFB physical Base Plate identity is invalid") from None
        if placement.anchor!=anchor:
            continue
        if (placement.placement_kind!="receiving_base_plate"
                or placement.relationship!="BASE_PLATE"
                or placement.parent_assembly_node!="box_body"
                or tuple(placement.rotation)!=(0.,0.,0.)):
            raise ValueError("NFB upper base has noncanonical assembly placement")
        render=getattr(part,"render_data",None)
        material=getattr(render,"material",None)
        # The real BasePlate PartSpec currently has no
        # UnfoldedBlankTopology; its authoritative actual FinalScene material
        # owns the blank, and four-side BENDs stay with its renderer.
        # Do not fabricate a topology just to pass an MFG-2 identity check.
        if material is None or material.is_empty or not material.is_valid:
            raise ValueError("NFB upper base has no real unfolded manufacturing material")
        minx,miny,maxx,maxy=map(float,material.bounds)
        width=maxx-minx
        height=maxy-miny
        if not all(isfinite(v) for v in (width,height)) or min(width,height)<=0:
            raise ValueError("NFB upper base has invalid physical blank dimensions")
        physical.append((key,placement,width,height))
    if len(physical)!=1:
        raise ValueError("NFB upper base actual per-cell physical part absent/ambiguous")
    key,placement,width,height=physical[0]
    return NfbUpperBasePlateOwner(
        physical_part_id=key,
        nfb_inner_door_part_id=verified_inner_door.part_id,
        source_sha256=source_process.source_sha256,
        source_color150_handle=source_process.upper_color150_handle,
        receiving_cell_key=cell,
        assembly_anchor=anchor,
        unchanged_world_offset=tuple(placement.world_offset),
        physical_blank_width_mm=width,
        physical_blank_height_mm=height,
    )
