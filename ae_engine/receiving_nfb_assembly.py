# -*- coding: utf-8 -*-
"""Public Engine boundary for Receiving committed NFB physical assembly parts.

Move-only from the normal Phase6 manufacturing resolver. The existing tier
PartSpecs and committed CSV V5 proof remain the sole numeric source of truth.
"""
from __future__ import annotations

from .receiving_nfb_layer_physical_parts import expand_receiving_nfb_layer_parts
from .receiving_nfb_committed_final_scene import apply_committed_csv_v5_to_canonical_parts


def resolve_receiving_nfb_assembly_parts(snapshot, assembly_parts):
    """Expand actual tier blanks, then apply only genuinely submitted CSV V5.

    No draft/candidate/other-family source can promote holes into canonical
    FinalScene. Keep the historical order and exact snapshot identity gates.
    """
    parts = tuple(expand_receiving_nfb_layer_parts(snapshot, assembly_parts))
    if (snapshot.get("model") in ("受電箱", "RECEIVING")
            and snapshot.get("nfb_config_submitted") is True):
        parts = tuple(apply_committed_csv_v5_to_canonical_parts(snapshot, parts))
    return parts
