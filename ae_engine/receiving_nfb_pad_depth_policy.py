"""#1503 read-only NFB PAD depth eligibility from current editable CSV.

Compute EACH physical tier independently; no hardcoded two-NFB or
one-tier limit. The non-manufacturing count is only an informational
requirement, never an approved PAD part or DXF/BOM release.
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
    tier_pad_counts: tuple[int, ...] = ()

    @property
    def candidate(self) -> bool:
        return self.status == DIFFERENT_DEPTH


def preview_nfb_pad_depth(
    draft: Mapping[str, object], *, index_path: str | Path | None = None,
) -> NfbPadDepthPreview:
    """Show PAD demand by source depth PER TIER; no manufacturing release.

    No NFB model, depth, installation-X, geometry or material is invented.
    Numeric V5 identities come from the per-brand CSV; legacy filenames
    retain their own catalog source. Full PAD geometry is owned by the
    single generic generate_nfb_pad_patterns() in the committed path.
    """
    if not isinstance(draft, Mapping):
        raise TypeError("NFB draft must be a mapping")
    count = draft.get("layer_count")
    if type(count) is not int or count not in (1, 2):
        raise ValueError("NFB physical layer count invalid")
    layers = draft.get("layers")
    if not isinstance(layers, (list, tuple)) or len(layers) != 2:
        raise ValueError("NFB physical layers missing")
    active_slots=[]
    for layer_index in range(count):
        layer=layers[layer_index]
        slots=layer.get("slots",()) if isinstance(layer,Mapping) else None
        if not isinstance(slots,(list,tuple)):
            raise ValueError("NFB physical slots invalid")
        active_slots.append(tuple(slots))
    if count==1 and isinstance(layers[1],Mapping) and layers[1].get("slots"):
        raise ValueError("NFB hidden second tier cannot contain switches")
    total=sum(len(slots) for slots in active_slots)
    if not total:
        return NfbPadDepthPreview(
            NOT_APPLICABLE,count,0,(),None,None,None,
            tier_pad_counts=tuple(0 for _ in active_slots),
        )

    per_tier=[]
    for layer_index,slots in enumerate(active_slots):
        depths=[]
        for slot_index,slot in enumerate(slots):
            if not isinstance(slot,Mapping):
                raise ValueError("NFB slot must be a mapping")
            brand=effective_nfb_slot_brand(draft,layer_index,slot_index)
            filename=slot.get("filename")
            if (not isinstance(filename,str) or not filename
                    or slot.get("source_brand") != brand):
                depths.append(None)
                continue
            from .receiving_nfb_model_identity import (
                parse_numeric_model_ref,selected_numeric_spec,
            )
            if filename.startswith("nfbv5:"):
                parsed=parse_numeric_model_ref(filename)
                spec=selected_numeric_spec(brand,filename) if parsed else None
                depths.append(float(spec.depth_mm) if (spec is not None and spec.depth_mm is not None) else None)
            else:
                depths.append(model_depth_mm(brand,filename,path=index_path))
        per_tier.append(tuple(depths))
    observed=tuple(value for depths in per_tier for value in depths)
    if any(depth is None for depth in observed):
        return NfbPadDepthPreview(
            NEEDS_SOURCE,count,total,observed,None,None,None,
            tier_pad_counts=tuple(0 for _ in per_tier),
        )

    pad_counts=[]
    steps=[]
    for depths in per_tier:
        if not depths:
            pad_counts.append(0)
            continue
        deep=max(depths)
        shallows=tuple(depth for depth in depths if deep-depth>1e-8)
        pad_counts.append(len(shallows))
        if shallows:
            steps.append(deep-min(depths))
    required=sum(pad_counts)
    if total < 2 or required==0:
        return NfbPadDepthPreview(
            NOT_APPLICABLE if total < 2 else NO_PAD_NEEDED,
            count,total,observed,0.0,None,None,
            required_pad_count=0,tier_pad_counts=tuple(pad_counts),
        )
    # Compatibility pair indices are meaningful ONLY for exactly two
    # switches in ONE physical tier. A multi-NFB/multi-tier group has no
    # unique deeper/shallow pair and must not pretend otherwise.
    single_pair=(count==1 and len(per_tier[0])==2)
    shallow=(
        0 if per_tier[0][0]<per_tier[0][1] else 1
    ) if single_pair else None
    deep=(1-shallow) if single_pair else None
    return NfbPadDepthPreview(
        DIFFERENT_DEPTH,count,total,observed,max(steps),
        shallow,deep,required_pad_count=required,
        manufacturing_ready=False,tier_pad_counts=tuple(pad_counts),
    )
