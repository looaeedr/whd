# -*- coding: utf-8 -*-
"""Source-backed Receiving NFB PAD assembly display-only public API.

Keep true CSV/tooling/physical Base CUTTING recheck owned by canonical Engine
solvers. An optional view skin never grants weld/contact or DXF manufacture.
"""
from __future__ import annotations

from collections.abc import Mapping


def receiving_pad_assembly_display_active(snapshot) -> bool:
    """Whether this client may request committed Receiving PAD trial skins."""
    return (isinstance(snapshot, Mapping)
            and snapshot.get("model") in ("受電箱", "RECEIVING")
            and snapshot.get("nfb_config_submitted") is True)


def receiving_pad_assembly_display_source_key(snapshot, assembly_parts):
    """Recheck real CUTTING scene, CSV bytes and tooling before any cache hit."""
    from .receiving_nfb_pad_preview_cache import pad_preview_source_fingerprint
    return pad_preview_source_fingerprint(snapshot, assembly_parts)


def resolve_receiving_pad_assembly_display_skins(snapshot, assembly_parts):
    """Return genuine preview skins only; reject all claimed MFG/contact flags.

    This delegates the entire geometry, per-Bay identity, four-square
    engagement and formed-world placement to the existing Engine solver.
    """
    if not receiving_pad_assembly_display_active(snapshot):
        return ()
    from .receiving_nfb_pad_assembly_preview import build_committed_pad_assembly_display
    skins = tuple(build_committed_pad_assembly_display(snapshot, assembly_parts))
    if any(skin.manufacturing_ready or skin.assembly_contact_certified for skin in skins):
        raise ValueError("PAD_DISPLAY_MFG_OR_CONTACT_GATE_INVALID")
    return skins
