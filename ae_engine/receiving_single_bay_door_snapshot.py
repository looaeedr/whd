# -*- coding: utf-8 -*-
"""#2517: canonical Receiving singleton-Bay Door operator Save projection.

The main GUI's live inner-door controls belong to the sole persisted Bay only
when Receiving has exactly one Set and one Bay. For a multi-Bay/Set project,
root controls must NEVER rewrite independent Bay door_state authority.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Mapping

from .receiving_layout import RECEIVING_DOOR_STATE_KEYS, update_receiving_bay


def project_receiving_single_bay_door_controls(snapshot: Mapping[str, object]):
    """Return an isolated persisted layout if root Door controls own its only Bay.

    None means no eligible singleton projection; callers leave saved layout
    untouched. An eligible but malformed layout fails closed via the existing
    canonical Receiving layout validator.
    """
    if (not isinstance(snapshot, Mapping)
            or snapshot.get("model") not in ("受電箱", "RECEIVING")
            or snapshot.get("active_mode", "set_bay") != "set_bay"):
        return None
    layout = snapshot.get("receiving_layout")
    if not isinstance(layout, Mapping) or not snapshot.get("inner_doors"):
        return None
    sets = layout.get("sets") or ()
    if not isinstance(sets, (list, tuple)) or len(sets) != 1:
        return None
    only_set = sets[0]
    if not isinstance(only_set, Mapping):
        raise ValueError("RECEIVING_SINGLE_BAY_SET_SOURCE_INVALID")
    bays = only_set.get("bays") or ()
    if not isinstance(bays, (list, tuple)) or len(bays) != 1:
        return None
    source_door = {
        key: deepcopy(snapshot[key]) for key in RECEIVING_DOOR_STATE_KEYS
        if key in snapshot
    }
    return update_receiving_bay(
        layout, set_index=0, bay_index=0, door_state=source_door,
    )
