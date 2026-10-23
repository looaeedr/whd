# -*- coding: utf-8 -*-
"""#1504 AC-20/SWT-13: read-only brand-change reselection previews.

Derive impacted *already selected* physical sources before any Tk event may
commit a parent/layer/slot brand. Neither helper mutates its inputs, stores a
readiness flag, invents a model or manufactures an X coordinate.
"""
from __future__ import annotations

from .receiving_switch_layout import RECEIVING_SWITCH_BRANDS
from .receiving_nfb_model_identity import parse_numeric_model_ref
from .receiving_nfb_ui1a import effective_nfb_slot_brand


def _require_brand(value):
    if value not in RECEIVING_SWITCH_BRANDS:
        raise ValueError("NFB 預設廠牌不合法")
    return value


def saved_parent_new_reselections(scope, current_brand, proposed_brand):
    """Count brand-following, previously matching submitted V5 holes only."""
    _require_brand(current_brand)
    _require_brand(proposed_brand)
    if current_brand == proposed_brand or scope.get("nfb_config_submitted") is not True:
        return 0
    from .receiving_nfb_persistence import normalize_nfb_saved_fields
    fields = normalize_nfb_saved_fields(scope)
    count = 0
    for hole in fields["nfb_config"]["holes"]:
        mode = hole.get("brand_mode", "INHERIT")
        if mode not in ("INHERIT", "OVERRIDE"):
            raise ValueError("NFB 品牌繼承模式不合法")
        if mode == "OVERRIDE":
            continue
        identity = parse_numeric_model_ref(hole["model_filename"])
        source = identity[0] if identity is not None else hole.get("source_brand")
        # An already stale unit is not newly invalidated by this edit.
        if source == current_brand and source != proposed_brand:
            count += 1
    return count


def draft_new_reselections(before, proposed):
    """Count newly mismatched following slots, respecting explicit overrides."""
    if before["layer_count"] != proposed["layer_count"]:
        raise ValueError("NFB 品牌預告不可改變實體層數")
    count = 0
    for i in range(before["layer_count"]):
        original = before["layers"][i]["slots"]
        updated = proposed["layers"][i]["slots"]
        if len(original) != len(updated):
            raise ValueError("NFB 品牌預告不可更改實體顆位")
        for j, slot in enumerate(original):
            if slot["filename"] is None:
                continue
            old_effective = effective_nfb_slot_brand(before, i, j)
            new_effective = effective_nfb_slot_brand(proposed, i, j)
            if (slot.get("source_brand") == old_effective
                    and slot.get("source_brand") != new_effective):
                count += 1
    return count
