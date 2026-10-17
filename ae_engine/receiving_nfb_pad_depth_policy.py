# -*- coding: utf-8 -*-
"""#1503 NFB PAD eligibility, using the user's editable switch-depth CSV.

The PAD *preview* never moves a Base Plate or creates an ear. This old
module must not override the later #1502/#1503 physical mounting contract:
inner-door Z stays fixed, while the Base Plate and its two fixing plates
translate TOGETHER with selected NFB depth; see receiving_nfb_depth_surface_policy.
Only one physical NFB layer with exactly two selected switches of *unequal*
known depth qualifies for a PAD proposal. This makes no manufacturing PAD
part, thickness, BEND/DXF or automatic welding/Z adjustment.

Two-layer configs, single or 3+ NFBs, and equal-depth pairs never get a PAD
just because their brand or filenames differ. Missing/conflicting CSV source
depths never turn into an invented 0-mm spacer.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .receiving_nfb_ui1a import effective_nfb_slot_brand
from .receiving_switch_model_catalog import model_depth_mm


NOT_APPLICABLE = "PAD_NOT_APPLICABLE"
NO_PAD_NEEDED = "PAD_NOT_NEEDED_SAME_DEPTH"
NEEDS_SOURCE = "PAD_DEPTH_SOURCE_UNKNOWN"
DIFFERENT_DEPTH = "PAD_DIFFERENT_DEPTH_REVIEW_ONLY"


@dataclass(frozen=True)
class NfbPadDepthPreview:
    status: str
    layer_count: int
    unit_count: int
    depth_mm: tuple[float | None, ...]
    candidate_delta_mm: float | None
    shallower_unit_index: int | None
    deeper_unit_index: int | None
    required_pad_count: int = 0
    manufacturing_ready: bool = False

    @property
    def candidate(self) -> bool:
        return self.status == DIFFERENT_DEPTH


def preview_nfb_pad_depth(
    draft: Mapping[str, object], *, index_path: str | Path | None = None,
) -> NfbPadDepthPreview:
    """Read current *effective* brand per switch, with exact selected DXF.

    'Depth difference' is evidence, NOT an approved spacer thickness: actual
    reference faces, lower-source PAD contour and manufacturing are separate.
    """
    if not isinstance(draft, Mapping):
        raise TypeError("NFB draft must be a mapping")
    count = draft.get("layer_count")
    if type(count) is not int or count not in (1, 2):
        raise ValueError("NFB physical layer count invalid")
    layers = draft.get("layers")
    if not isinstance(layers, (list, tuple)) or len(layers) != 2:
        raise ValueError("NFB physical layers missing")
    slots = layers[0].get("slots", ()) if isinstance(layers[0], Mapping) else ()
    if not isinstance(slots, (list, tuple)):
        raise ValueError("NFB physical slots invalid")
    size = len(slots)
    if count != 1 or size != 2:
        return NfbPadDepthPreview(NOT_APPLICABLE, count, size, (), None, None, None)
    depths = []
    for i, slot in enumerate(slots):
        if not isinstance(slot, Mapping):
            raise ValueError("NFB slot must be a mapping")
        brand = effective_nfb_slot_brand(draft, 0, i)
        filename = slot.get("filename")
        # A brand switch preserves its old filename until the user selects
        # a matching model; never reinterpret that old source as new-brand.
        if (not isinstance(filename, str) or not filename
                or slot.get("source_brand") != brand):
            depths.append(None)
            continue
        from .receiving_nfb_model_identity import (
            parse_numeric_model_ref, selected_numeric_spec,
        )
        if filename.startswith("nfbv5:"):
            parsed = parse_numeric_model_ref(filename)
            spec = selected_numeric_spec(brand, filename) if parsed else None
            depths.append(spec.depth_mm if spec is not None else None)
        else:
            depths.append(model_depth_mm(brand, filename, path=index_path))
    observed = tuple(depths)
    if any(x is None for x in observed):
        return NfbPadDepthPreview(NEEDS_SOURCE, count, size, observed, None, None, None)
    a, b = observed
    if a == b:
        return NfbPadDepthPreview(NO_PAD_NEEDED, count, size, observed, 0.0, None, None)
    shallow = 0 if a < b else 1
    return NfbPadDepthPreview(
        DIFFERENT_DEPTH, count, size, observed,
        abs(b-a), shallow, 1-shallow,
    )
