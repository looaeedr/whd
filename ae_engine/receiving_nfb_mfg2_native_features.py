# -*- coding: utf-8 -*-
"""#1502 real native NFB operation geometry, upstream of physical MFG-2 UV.

The operator's indexed original DXF and upper/lower anchor handles own the
geometry. Color30 and 212 describe base-plate cutting/marking *intent*, while
the shared Color150 reference may serve the independently verified inner
door and a not-yet-verified middle plate. These are SOURCE observations,
never DXF manufacturing permission. The LOWER group is deferred and never
projected to a plate under the current v1.4 contract.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import cos, sin, radians, isfinite
from pathlib import Path
import re

from .receiving_nfb_source_regions import (
    UPPER, LOWER, inspect_nfb_original_source_regions,
)

SOURCE_ONLY="NFB_SOURCE_NATIVE_NOT_UV_VERIFIED"
UV_CANDIDATE_ONLY="NFB_PHYSICAL_UV_CANDIDATE_NOT_CUTTING_APPROVED"
BASE="BASE_PLATE"
MIDDLE="MIDDLE_PLATE"
INNER="INNER_DOOR"


@dataclass(frozen=True)
class NfbNativeProcessFeature:
    source_sha256: str
    source_region: str
    source_handle: str
    source_aci: int
    source_entity_type: str
    process_layer: str
    possible_physical_roles: tuple[str,...]
    points_from_upper_center_mm: tuple[tuple[float,float],...]
    circle_radius_mm: float|None
    closed: bool
    disposition: str = SOURCE_ONLY


@dataclass(frozen=True)
class NfbNativeMfg2SourceObservation:
    indexed_filename: str
    source_sha256: str
    upper_handle: str
    upper_center_xy_mm: tuple[float,float]
    upper_features: tuple[NfbNativeProcessFeature,...]
    deferred_lower_handles: tuple[str,...]
    manufacturing_ready: bool=False

    @property
    def base_cutting(self):
        return tuple(f for f in self.upper_features
                     if f.source_aci==30 and f.process_layer=="CUTTING")

    @property
    def base_marking(self):
        return tuple(f for f in self.upper_features
                     if f.source_aci==212 and f.process_layer=="MARKING")


@dataclass(frozen=True)
class NfbUnapprovedUvCandidate:
    physical_part_id: str
    role: str
    source_handle: str
    process_layer: str
    points_uv_mm: tuple[tuple[float,float],...]
    circle_radius_mm:float|None
    closed:bool
    provenance:tuple[str,str,str]  # SHA, source region, handle
    disposition:str=UV_CANDIDATE_ONLY
    manufacturing_ready:bool=False


def _indexed_name_matches(actual:str,indexed:str)->bool:
    if actual.casefold()==indexed.casefold():
        return True
    return bool(re.fullmatch(
        re.escape(Path(indexed).stem)+r"\([1-9][0-9]*\)\.dxf",
        actual,re.IGNORECASE,
    ))


def read_nfb_native_mfg2_features(
    source_path:str|Path,*,indexed_filename:str,expected_sha256:str,
    upper_handle:str,lower_handle:str,
    upper_width_mm:float,upper_height_mm:float,
)->NfbNativeMfg2SourceObservation:
    """Preserve actual source vertex offsets, not just bbox or ACI counts."""
    import ezdxf
    from ezdxf import bbox

    source=Path(source_path)
    if not _indexed_name_matches(source.name,indexed_filename):
        raise ValueError("NFB original source basename disagrees with indexed model")
    groups=inspect_nfb_original_source_regions(
        source,indexed_filename=indexed_filename,
        expected_sha256=expected_sha256,
        upper_reference_handle=upper_handle,
        lower_reference_handle=lower_handle,
        expected_upper_width_mm=upper_width_mm,
        expected_upper_height_mm=upper_height_mm,
    )
    original=ezdxf.readfile(source)
    reference=original.entitydb[upper_handle]
    boundary=bbox.extents([reference])
    cx=(float(boundary.extmin.x)+float(boundary.extmax.x))/2
    cy=(float(boundary.extmin.y)+float(boundary.extmax.y))/2
    upper_handles=set(groups.upper.entity_handles)
    features=[]
    for entity in original.modelspace():
        handle=str(entity.dxf.handle)
        if handle not in upper_handles:
            continue
        aci=int(entity.dxf.get("color",256))
        if aci==30:
            process,roles="CUTTING",(BASE,)
        elif aci==212:
            process,roles="MARKING",(BASE,)
        elif aci==150 and handle==upper_handle:
            # The reference's middle-plate interpretation is not proved by
            # current MFG-1 inner door, despite sharing Color150.
            process,roles="CUTTING",(INNER,MIDDLE)
        else:
            raise ValueError("Unclassified NFB upper source handle/color")
        kind=entity.dxftype()
        if kind=="LINE":
            vertices=(tuple(entity.dxf.start[:2]),tuple(entity.dxf.end[:2]))
            radius=None
            closed=False
        elif kind=="CIRCLE":
            vertices=(tuple(entity.dxf.center[:2]),)
            radius=float(entity.dxf.radius)
            closed=True
        elif kind=="LWPOLYLINE":
            pts=tuple(entity.get_points("xyb"))
            if (not entity.closed or len(pts)<3
                    or any(abs(float(row[2]))>1e-10 for row in pts)):
                raise ValueError("NFB native source polyline needs closed straight segments")
            vertices=tuple((float(p[0]),float(p[1])) for p in pts)
            radius=None
            closed=True
        else:
            raise ValueError("NFB upper operation contains unsupported native entity")
        values=tuple((float(x)-cx,float(y)-cy) for x,y in vertices)
        if not all(isfinite(q) for pair in values for q in pair):
            raise ValueError("NFB native operation has nonfinite coordinates")
        features.append(NfbNativeProcessFeature(
            source_sha256=groups.source_sha256,
            source_region=UPPER,source_handle=handle,source_aci=aci,
            source_entity_type=kind,process_layer=process,
            possible_physical_roles=roles,
            points_from_upper_center_mm=values,
            circle_radius_mm=radius,closed=closed,
        ))
    if set(f.source_handle for f in features)!=upper_handles:
        raise ValueError("NFB upper source contains missing/duplicate operations")
    return NfbNativeMfg2SourceObservation(
        indexed_filename,groups.source_sha256,upper_handle,(cx,cy),
        tuple(features),groups.lower.entity_handles,
    )


def candidate_nfb_base_plate_uv(
    observation:NfbNativeMfg2SourceObservation,*,
    target_physical_part_id:str,
    independently_measured_reference_uv_xy:tuple[float,float],
    rotation_deg:int,
)->tuple[NfbUnapprovedUvCandidate,...]:
    """Only a candidate rigid registration from a REAL supplied plate datum.

    Caller must separately prove physical ownership, flat-face orientation,
    material/fold clearance, collision and acceptance golden before any
    CUTTING/MARKING is emitted. No inferred center, offset or plate movement.
    """
    if not isinstance(observation,NfbNativeMfg2SourceObservation):
        raise TypeError("NFB native original source observation required")
    if not target_physical_part_id or not target_physical_part_id.strip():
        raise ValueError("NFB UV needs real target physical plate ID")
    if type(rotation_deg) is not int or rotation_deg not in (0,90,180,270):
        raise ValueError("NFB physical UV requires explicit quarter-turn orientation")
    if (len(independently_measured_reference_uv_xy)!=2 or
            not all(type(v) in (int,float) and isfinite(float(v))
                    for v in independently_measured_reference_uv_xy)):
        raise ValueError("NFB UV needs independently measured physical reference")
    x,y=(float(v) for v in independently_measured_reference_uv_xy)
    angle=radians(rotation_deg)
    co,si=round(cos(angle)),round(sin(angle))
    out=[]
    for feature in observation.upper_features:
        if BASE not in feature.possible_physical_roles:
            continue
        coords=tuple((x+co*px-si*py,y+si*px+co*py)
                     for px,py in feature.points_from_upper_center_mm)
        out.append(NfbUnapprovedUvCandidate(
            physical_part_id=target_physical_part_id,role=BASE,
            source_handle=feature.source_handle,
            process_layer=feature.process_layer,points_uv_mm=coords,
            circle_radius_mm=feature.circle_radius_mm,closed=feature.closed,
            provenance=(feature.source_sha256,feature.source_region,
                        feature.source_handle),
        ))
    return tuple(out)
