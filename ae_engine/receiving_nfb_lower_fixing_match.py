# -*- coding: utf-8 -*-
"""#1502 compare only true NFB LOWER source CIRCLEs to middle-base fixings.

The lower NFB DXF group is NOT wholly discarded, but only its four native
CIRCLE objects are eligible for geometric comparison. Remaining lower
LINE/ARC/pad/mark geometry is excluded. Comparison is translation invariant:
a nominal source-DXF world X/Y is never a cabinet part-placement coordinate.

Several source quartets may share the same pattern (three 30x132), so
ambiguity is reported and NEVER resolved by arbitrarily selecting a first
group. Actual per-NFB count/position remains owned by existing verified
inner-door NFBConfig. This is source evidence, not manufacturing approval.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from .receiving_nfb_dxf_source import inspect_nfb_dxf_source
from .receiving_nfb_middle_fixing_holes import NfbMiddleFixingEvidence
from .receiving_nfb_source_regions import (
    LOWER, inspect_nfb_original_source_regions,
)

STATUS = "MFG2_NFB_LOWER_4_CIRCLES_TO_CENTER_BASE_PATTERN_MATCH_NOT_CUTTING"


@dataclass(frozen=True)
class NfbLowerSourceFixingMatch:
    nfb_lower_source_sha256: str
    nfb_lower_circle_handles: tuple[str, ...]
    lower_source_spacing_mm: tuple[float, float]
    lower_source_radius_mm: float
    candidate_quartet_indices: tuple[int, ...]
    ambiguous_source_quartet: bool
    status: str = STATUS
    manufacturing_ready: bool = False


def match_lower_nfb_source_fixing_circles(
    middle_base: NfbMiddleFixingEvidence,
    nfb_source_path: str | Path, *,
    indexed_filename: str,
    nfb_source_sha256: str,
    upper_reference_handle: str,
    lower_reference_handle: str,
    upper_width_mm: float = 57.,
    upper_height_mm: float = 96.,
) -> NfbLowerSourceFixingMatch:
    """Read native four lower CIRCLE handles, compare quartet signatures.

    The user-confirmed SOURCE semantic is not by itself mathematical
    evidence that a source contour is in the same physical blank location:
    only dimensions/radius may be checked here, not assignment to Set/Bay.
    """
    if not isinstance(middle_base,NfbMiddleFixingEvidence) or (
        middle_base.manufacturing_ready or len(middle_base.quartets) != 4
    ):
        raise ValueError("NFB actual middle-base fixing provenance unresolved")
    regions=inspect_nfb_original_source_regions(
        nfb_source_path,
        indexed_filename=indexed_filename,
        expected_sha256=nfb_source_sha256,
        upper_reference_handle=upper_reference_handle,
        lower_reference_handle=lower_reference_handle,
        expected_upper_width_mm=upper_width_mm,
        expected_upper_height_mm=upper_height_mm,
    )
    if regions.lower.region != LOWER:
        raise ValueError("NFB lower original group identity unavailable")
    inventory=inspect_nfb_dxf_source(nfb_source_path)
    lower=set(regions.lower.entity_handles)
    circles=[
        e for e in inventory.entities
        if e.handle_path in lower and e.dxf_type == "CIRCLE"
    ]
    if len(circles)!=4:
        raise ValueError("NFB lower fixing source needs exactly four native CIRCLEs")
    if len({e.handle_path for e in circles})!=4:
        raise ValueError("NFB lower fixing circle handles not unique")
    radius=[float(e.radius) for e in circles]
    if any(not isfinite(r) or r<=0 or abs(r-radius[0])>1e-5 for r in radius):
        raise ValueError("NFB lower fixing source radii invalid or mixed")
    centers=[
        (float(e.center_xy[0]),float(e.center_xy[1]))
        for e in circles if e.center_xy is not None
    ]
    if len(centers)!=4:
        raise ValueError("NFB lower source circle centers missing")
    xs={round(x,5) for x,y in centers}
    ys={round(y,5) for x,y in centers}
    if len(xs)!=2 or len(ys)!=2 or (
        set((round(x,5),round(y,5)) for x,y in centers)
        !=set((x,y) for x in xs for y in ys)
    ):
        raise ValueError("NFB lower native circles do not form a four-corner fixing pattern")
    dx=max(xs)-min(xs)
    dy=max(ys)-min(ys)
    matches=[]
    for idx, group in enumerate(middle_base.quartets):
        if abs(group.circle_radius-radius[0])>1e-5:
            continue
        width=float(group.horizontal_pitch)
        height=float(group.vertical_pitch)
        if ((abs(dx-width)<=1e-4 and abs(dy-height)<=1e-4)
                or (abs(dx-height)<=1e-4 and abs(dy-width)<=1e-4)):
            matches.append(idx)
    if not matches:
        raise ValueError("NFB lower original four-circle spacing differs from center-base fixing holes")
    return NfbLowerSourceFixingMatch(
        nfb_lower_source_sha256=regions.source_sha256,
        nfb_lower_circle_handles=tuple(e.handle_path for e in circles),
        lower_source_spacing_mm=(dx,dy),
        lower_source_radius_mm=radius[0],
        candidate_quartet_indices=tuple(matches),
        ambiguous_source_quartet=len(matches)!=1,
    )
