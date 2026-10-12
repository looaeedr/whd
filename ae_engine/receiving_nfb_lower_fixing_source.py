# -*- coding: utf-8 -*-
"""#1502: ONLY the NFB's four native lower-source CIRCLE fixing holes.

These are hardware fixing-hole locations, not the lower region's spacer
outline, ARCs, marking or a new physical plate. The group is bound to the
SAME original DXF model/SHA and upper opening as the verified inner door.
Its centroid is the NFB screw-group center; never use raw DXF world X/Y.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path

from .receiving_nfb_cutting_manufacturing import NfbUpperSourceProfile
from .receiving_nfb_dxf_source import inspect_nfb_dxf_source
from .receiving_nfb_source_regions import (
    LOWER, inspect_nfb_original_source_regions,
)

@dataclass(frozen=True)
class NfbLowerFixingCircle:
    source_handle: str
    center_xy_mm: tuple[float, float]
    radius_mm: float


@dataclass(frozen=True)
class NfbVerifiedLowerFixingGroup:
    source_sha256: str
    indexed_filename: str
    source_lower_reference_handle: str
    screw_group_center_xy_mm: tuple[float, float]
    circles: tuple[NfbLowerFixingCircle, ...]
    status: str = "NFB_LOWER_FOUR_SOURCE_CIRCLES_IDENTIFIED_ONLY"
    manufacturing_ready: bool = False


def inspect_nfb_lower_four_fixing_circles(
    source_path: str | Path,
    *,
    profile: NfbUpperSourceProfile,
    lower_reference_handle: str,
) -> NfbVerifiedLowerFixingGroup:
    """Use original 4 circles, not a duplicate drawing or inferred hole pitch."""
    if not isinstance(profile, NfbUpperSourceProfile):
        raise TypeError("NFB screw source requires original indexed model profile")
    split = inspect_nfb_original_source_regions(
        source_path,
        indexed_filename=profile.indexed_filename,
        expected_sha256=profile.source_sha256,
        upper_reference_handle=profile.upper_handle,
        lower_reference_handle=lower_reference_handle,
        expected_upper_width_mm=profile.upper_size_mm[0],
        expected_upper_height_mm=profile.upper_size_mm[1],
    )
    if split.lower.region != LOWER:
        raise ValueError("NFB screw circles not in verified LOWER source group")
    original=inspect_nfb_dxf_source(source_path)
    if original.source_sha256!=split.source_sha256 or original.diagnostics:
        raise ValueError("NFB lower screw original source changed")
    members={row.handle_path:row for row in original.entities}
    circles=[]
    for handle in split.lower.entity_handles:
        entity=members[handle]
        if entity.dxf_type != "CIRCLE":
            continue  # Spacer outlines, ARCs and marking are NOT screw holes.
        if (entity.effective_color_aci != 3
                or entity.center_xy is None or entity.radius is None
                or not isfinite(float(entity.radius)) or entity.radius <= 0):
            raise ValueError("NFB lower fixing CIRCLE has invalid native geometry")
        circles.append(NfbLowerFixingCircle(
            entity.handle_path,
            (float(entity.center_xy[0]), float(entity.center_xy[1])),
            float(entity.radius),
        ))
    if len(circles)!=4 or len({c.center_xy_mm for c in circles})!=4:
        raise ValueError("NFB lower fixing requires exactly four distinct native CIRCLEs")
    # Raw drawing group offsets are schematic: only the native quartet's
    # internal relative coordinates survive manufacturing projection.
    x=sum(v.center_xy_mm[0] for v in circles)/4.0
    y=sum(v.center_xy_mm[1] for v in circles)/4.0
    return NfbVerifiedLowerFixingGroup(
        source_sha256=split.source_sha256,
        indexed_filename=profile.indexed_filename,
        source_lower_reference_handle=lower_reference_handle,
        screw_group_center_xy_mm=(x,y),
        circles=tuple(circles),
    )


def resolve_unique_nfb_lower_reference_handle(source_path, *, profile: NfbUpperSourceProfile) -> str:
    """Resolve one original lower closed Color-3 source reference, or refuse.

    The chosen handle must be uniquely evidenced by the SAME original DXF.
    It is a source-group identity only, NEVER the assembly world-coordinate
    origin, a pad/ear plate, or an invented NFB screw pitch.
    """
    from hashlib import sha256
    import ezdxf

    source = Path(source_path)
    if source.name.casefold() != profile.indexed_filename.casefold():
        raise ValueError("NFB lower source filename does not match verified index")
    if sha256(source.read_bytes()).hexdigest() != profile.source_sha256:
        raise ValueError("NFB lower source SHA does not match verified index")
    document = ezdxf.readfile(source)
    candidates = tuple(
        str(entity.dxf.handle)
        for entity in document.modelspace()
        if entity.dxftype() == "LWPOLYLINE"
        and entity.closed
        and int(entity.dxf.get("color", 256)) == 3
    )
    if len(candidates) != 1:
        raise ValueError("NFB lower source reference is absent or ambiguous")
    # Structural provenance is not sufficient: the same source must also
    # contain the exact four native screws in a strictly separate lower group.
    inspected = inspect_nfb_lower_four_fixing_circles(
        source, profile=profile, lower_reference_handle=candidates[0],
    )
    if inspected.source_sha256 != profile.source_sha256:
        raise ValueError("NFB lower group proof changed")
    return candidates[0]
