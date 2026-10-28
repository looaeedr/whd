# -*- coding: utf-8 -*-
"""Read saved physical NFB rows into a *reversible* inner-door editor draft.

Some older Receiving projects persisted two NFBConfig rows but never saved
matching inner_door_models or original Hole Editor CSV Features. This helper
does not approve, place or manufacture those holes. It restores only the
saved selected model identities into the native editor for explicit Confirm All.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

from .receiving_nfb_model_identity import parse_numeric_model_ref
from .receiving_shared_settings import switch_filenames_in_layer


def recover_submitted_nfb_models_for_editor(initial, physical_snapshot):
    """Prefer more complete committed physical choices over incomplete UI aliases.

    Keep a candidate editor separate: the caller must restrict this function
    to the real physical Single/SetBay editor, not a version-library editor.
    """
    result = deepcopy(dict(initial))
    if (not isinstance(physical_snapshot, Mapping)
            or physical_snapshot.get("nfb_config_submitted") is not True):
        return result
    saved = physical_snapshot.get("nfb_config")
    if not isinstance(saved, Mapping):
        return result
    count = saved.get("layer_count")
    rows = saved.get("holes")
    if (type(count) is not int or count not in (1, 2)
            or not isinstance(rows, (tuple, list)) or not rows):
        return result

    placements = {}
    for row in rows:
        if not isinstance(row, Mapping):
            return result
        tier = row.get("layer_index", 0 if count == 1 else None)
        slot = row.get("slot_index")
        ref = row.get("model_filename")
        parsed = parse_numeric_model_ref(ref)
        if (type(tier) is not int or not 0 <= tier < count
                or type(slot) is not int or slot < 0 or parsed is None
                or row.get("source_brand", parsed[0]) != parsed[0]
                or (tier, slot) in placements):
            return result  # damaged source must not become visible false proof
        placements[(tier, slot)] = ref
    layers = [[], []]
    for tier in range(count):
        indexes = sorted(slot for t, slot in placements if t == tier)
        if indexes and indexes != list(range(len(indexes))):
            return result
        layers[tier] = [placements[(tier, slot)] for slot in indexes]
    if not layers[0]:
        return result
    existing = result.get("models", ["", ""])
    try:
        existing_count = sum(
            len(switch_filenames_in_layer(row)) for row in existing
        )
    except (ValueError, TypeError):
        existing_count = 0
    # Never overwrite richer, explicit native editor choices with a stale
    # committed Bay alias. The saved source is used only to restore missing
    # physical NFB model occurrences.
    if existing_count >= len(rows):
        return result
    result["layers"] = count
    result["models"] = [row if row else "" for row in layers]
    result["_restored_saved_nfb_models"] = True
    return result
