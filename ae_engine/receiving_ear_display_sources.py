# -*- coding: utf-8 -*-
"""Engine-only Receiving EAR assembled 3D display source and fail-closed gate.

Every triangle comes from the existing authentic T2 BEND23 formed-skin solver.
This view is *not* a side-sheet UV MARKING, weld, or manufacturing release.
"""
from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256

from .receiving_base_fixing_plate_geometry import SOURCE_DXF_SHA256
from .receiving_fixed_plate_formed_skins import (
    build_receiving_formed_fixing_plate_skins,
    ReceivingFormedFixingPlateSkin,
)
from .receiving_tier_ear_assembly_xy import resolve_receiving_tier_ear_mating_xy


def receiving_ear_assembly_display_source_key(snapshot: Mapping[str, object]) -> str:
    """Keep the existing operator-view cache key, with provenance in Engine."""
    if not isinstance(snapshot, Mapping):
        raise TypeError("EAR_DISPLAY_SOURCE_REQUIRES_SNAPSHOT")
    return sha256((SOURCE_DXF_SHA256 + repr(snapshot)).encode("utf-8")).hexdigest()


def resolve_receiving_ear_assembly_display_skins(
    snapshot: Mapping[str, object],
) -> tuple[ReceivingFormedFixingPlateSkin, ...]:
    """Validate real one/two-tier owners and return display-only formed skins.

    The physical source, owner matching, BEND verification and withholding of
    manufacturing/weld readiness belong here, never in the 3D Tk adapter.
    """
    if not isinstance(snapshot, Mapping):
        raise TypeError("EAR_DISPLAY_SOURCE_REQUIRES_SNAPSHOT")
    if (snapshot.get("model") not in ("受電箱", "RECEIVING")
            or snapshot.get("nfb_config_submitted") is not True):
        return ()

    owners = tuple(resolve_receiving_tier_ear_mating_xy(snapshot))
    if len(owners) not in (2, 4):
        raise ValueError("EAR_ASSEMBLY_DISPLAY_OWNER_COUNT_INVALID")
    formed = tuple(
        build_receiving_formed_fixing_plate_skins(snapshot, owner.ear_id)
        for owner in owners
    )
    if (len({row.part_id for row in formed}) != len(formed)
            or {row.base_part_id for row in formed}
               != {owner.parent_base_id for owner in owners}
            or any(row.manufacturing_ready or row.weld_contact_verified
                   or not row.source_bend_verified for row in formed)):
        raise ValueError("EAR_ASSEMBLY_DISPLAY_SOURCE_INCONSISTENT")
    return formed
