# -*- coding: utf-8 -*-
"""#2517: canonical Receiving singleton-Bay Door operator Save projection.

The main GUI's live inner-door controls belong to the sole persisted Bay only
when Receiving has exactly one Set and one Bay. For a multi-Bay/Set project,
root controls must NEVER rewrite independent Bay door_state authority.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Mapping

from .operator_settings_transactions import normalize_operator_source_dimension
from .receiving_layout import RECEIVING_DOOR_STATE_KEYS, update_receiving_bay, HORIZONTAL_DIVIDER_OCCUPANCY


def project_receiving_single_bay_door_controls(snapshot: Mapping[str, object]):
    """Return an isolated persisted layout if root Door controls own its only Bay.

    None means no eligible singleton projection; callers leave saved layout
    untouched. An eligible but malformed layout fails closed via the existing
    canonical Receiving layout validator.
    """
    return _project_single_bay_door_controls(snapshot, allocate_divider_owner=False)


def commit_receiving_single_bay_door_controls(snapshot: Mapping[str, object]):
    """Commit an accepted Main Door-grid edit, not a passive refresh or Open."""
    return _project_single_bay_door_controls(snapshot, allocate_divider_owner=True)


def _project_single_bay_door_controls(snapshot, *, allocate_divider_owner):
    if (not isinstance(snapshot, Mapping)
            or snapshot.get("model") not in ("受電箱", "RECEIVING")
            or snapshot.get("active_mode", "set_bay") != "set_bay"):
        return None
    layout = snapshot.get("receiving_layout")
    if not isinstance(layout, Mapping):
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
    # Legacy no-inner-door calls retain their original non-owning behavior.
    # An enrolled Bay can explicitly lose its C boundary even if the edit
    # removed the last inner door. Never infer a new occupant from a read.
    bay = bays[0]
    if not snapshot.get("inner_doors") and not (
            isinstance(bay, Mapping) and HORIZONTAL_DIVIDER_OCCUPANCY in bay
            and "multi_door_enabled" in snapshot and "door_layout_columns" in snapshot):
        return None
    # The global Door grid and a Bay edited in Receiving may have different
    # finished dimensions even after that Bay becomes the only remaining one.
    # A passive snapshot must not replace the saved Bay's own partition with
    # a valid grid for a different physical box.
    if (not allocate_divider_owner and isinstance(bay, Mapping)
            and "w" in snapshot and "h" in snapshot):
        root_wh = tuple(normalize_operator_source_dimension(snapshot[key], field=key)
                        for key in ("w", "h"))
        bay_wh = tuple(normalize_operator_source_dimension(bay.get(name), field=key)
                       for name, key in (("width", "w"), ("height", "h")))
        if root_wh != bay_wh:
            return None
    source_door = {
        key: deepcopy(snapshot[key]) for key in RECEIVING_DOOR_STATE_KEYS
        if key in snapshot
    }
    return update_receiving_bay(
        layout, set_index=0, bay_index=0, door_state=source_door,
        _allocate_divider_owner=allocate_divider_owner,
    )
