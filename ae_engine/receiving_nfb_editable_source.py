# -*- coding: utf-8 -*-
"""Runtime NFB source format resolver: operator DXFs are EDITABLE.

CSV source_sha256/upper_handle/size identify a previous observation, not a
permanent allow-list for an editable original. When the DXF is modified,
derive a NEW transient profile from its real Color150 upper cutting geometry.
All later manufacturing operations use the *current* source SHA as a proof of
the single read/verification session (never a permit for unrelated bytes).
No CSV, source DXF, or indexed model name is overwritten.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from math import isfinite
from pathlib import Path
import re

from .receiving_nfb_cutting_manufacturing import NfbUpperSourceProfile
from .receiving_nfb_dxf_source import (
    inspect_nfb_dxf_source, resolve_upper_color150_reference,
)


def resolve_editable_nfb_source_profile(
    source_path: str | Path, *, profile: NfbUpperSourceProfile,
) -> NfbUpperSourceProfile:
    """Use current valid DXF format, not a pinned historical byte hash.

    Format here means one unambiguous closed rectangle on process ACI 150,
    supported graphic types and resolvable process colors. For Base Plate
    processing the existing UPPER/LOWER split plus original four screw
    circles are separately required by that manufacturing action.
    """
    if not isinstance(profile, NfbUpperSourceProfile):
        raise TypeError("NFB requires a typed editable source profile")
    source = Path(source_path)
    if not re.fullmatch(
        re.escape(Path(profile.indexed_filename).stem)
        + r"(?:[(][1-9][0-9]*[)])?[.]dxf",
        source.name, re.IGNORECASE,
    ):
        raise ValueError("NFB editable source must keep indexed model filename")
    raw = source.read_bytes()
    actual_sha = sha256(raw).hexdigest()
    # Preserve legacy exact source profiles without reselecting handles:
    # editing an unrelated CSV column must not silently change original owner.
    if actual_sha == profile.source_sha256:
        # Existing SHA is an identity witness, not permission to trust a
        # malformed typed profile. NaN defeats the downstream size-difference
        # comparison (abs(source - NaN) > tolerance is false).
        size = profile.upper_size_mm
        if (not isinstance(size, (list, tuple)) or len(size) != 2
                or any(type(mm) not in (int, float) for mm in size)):
            raise ValueError("NFB source profile upper dimensions invalid")
        try:
            good = all(isfinite(float(mm)) and float(mm) > 0 for mm in size)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError("NFB source profile upper dimensions invalid") from exc
        if not good:
            raise ValueError("NFB source profile upper dimensions invalid")
        return profile
    inventory = inspect_nfb_dxf_source(source)
    if (inventory.source_sha256 != actual_sha or inventory.diagnostics
            or inventory.unresolved_color_entities):
        raise ValueError("NFB edited DXF format has unsupported geometry or colors")
    choices = []
    for entity in inventory.entities:
        if entity.effective_color_aci != 150:
            continue
        if entity.dxf_type not in ("LWPOLYLINE", "POLYLINE") or not entity.closed:
            continue
        try:
            reference = resolve_upper_color150_reference(
                inventory, upper_source_entity_ids=(entity.source_id,),
            )
        except ValueError:
            continue
        # Manufacturing upper+lower source region inspection uses an original
        # modelspace handle, not a flattened virtual INSERT child.
        if "/" in entity.handle_path:
            raise ValueError("NFB edited source has unsupported virtual upper reference")
        choices.append((entity.handle_path, reference))
    if len(choices) != 1:
        raise ValueError("NFB edited DXF must have one unambiguous upper Color150 rectangle")
    handle, reference = choices[0]
    return replace(
        profile, source_sha256=actual_sha,
        upper_handle=handle, upper_size_mm=reference.size_mm,
    )
