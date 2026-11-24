"""Receiving singleton Head lifetime identity (not a manufacturing release).

A role-bound legacy hole list is not a physical occupant. Only the actual
workspace presence/Family/Set-Bay lifecycle allocates a new occupant.
Persist retired IDs so a saved source cannot silently follow a replacement.
This increment does not store or enable any new MARKING feature.
"""
from collections.abc import Mapping
from copy import deepcopy
import re
from uuid import uuid4

from .cabinet_types.policy import canonical_family_name
from .receiving_layout import normalize_receiving_layout

HEAD_OCCUPANCY_KEY = "receiving_head_occupancy"
_ID = re.compile(r"receiving:head:[0-9a-f]{32}")


def receiving_head_scope(snapshot):
    """A standard single Set/Bay source only; no Quantity or grouped owner."""
    if (not isinstance(snapshot, Mapping)
            or canonical_family_name(snapshot) != "受電箱"
            or snapshot.get("active_mode", "set_bay") != "set_bay"):
        return None
    try:
        layout = normalize_receiving_layout(snapshot.get("receiving_layout"))
    except (ValueError, TypeError, KeyError):
        return None
    sets = layout["sets"]
    if len(sets) != 1 or len(sets[0]["bays"]) != 1:
        return None
    # Counter is a conservative topology witness, not the occupant ID.
    # A recycled Bay label never authorizes an older Head.
    return [sets[0]["stable_id"], sets[0]["bays"][0]["stable_id"],
            layout.get("base_plate_owner_namespace"), layout["next_panel_number"]]


def normalize_receiving_head_occupancy(raw):
    if not isinstance(raw, Mapping) or set(raw) != {"scope", "active", "retired"}:
        raise ValueError("HEAD_OCCUPANCY_INVALID")
    scope, active, retired = raw["scope"], raw["active"], raw["retired"]
    if scope is not None:
        if (not isinstance(scope, (list, tuple)) or len(scope) != 4
                or any(not isinstance(x, str) or not x for x in scope[:2])
                or (scope[2] is not None and
                    (not isinstance(scope[2], str) or not re.fullmatch("[0-9a-f]{32}", scope[2])))
                or type(scope[3]) is not int or scope[3] < 1):
            raise ValueError("HEAD_OCCUPANCY_SCOPE_INVALID")
        scope = list(scope)
    def valid(owner):
        return isinstance(owner, str) and _ID.fullmatch(owner) is not None
    if (not isinstance(retired, (list, tuple)) or not all(valid(x) for x in retired)
            or len(set(retired)) != len(retired)
            or (active is not None and
                (not valid(active) or active in retired or scope is None))):
        raise ValueError("HEAD_OCCUPANCY_OWNER_INVALID")
    return {"scope": scope, "active": active, "retired": list(retired)}


def transition_receiving_head_occupancy(raw, scope, present, *, allocate=True):
    """Pure transition except Engine allocation; never consume role features."""
    if raw is None and scope is None:
        return None
    state = (normalize_receiving_head_occupancy(raw) if raw is not None
             else {"scope": None, "active": None, "retired": []})
    if state["active"] is not None and (not present or scope != state["scope"]):
        state["retired"].append(state["active"])
        state["active"] = None
    state["scope"] = deepcopy(scope)
    if allocate and present and scope is not None and state["active"] is None:
        owner = "receiving:head:" + uuid4().hex
        while owner in state["retired"]:
            owner = "receiving:head:" + uuid4().hex
        state["active"] = owner
    return normalize_receiving_head_occupancy(state)


def reconcile_receiving_head_occupancy(snapshot, *, raw=None, parts=None, allocate=False):
    """Revalidate the saved/live scope without manufacturing or geometry guesses."""
    if raw is None and HEAD_OCCUPANCY_KEY in snapshot:
        raw = normalize_receiving_head_occupancy(snapshot[HEAD_OCCUPANCY_KEY])
    if parts is None:
        parts = snapshot.get("existing_parts")
        if parts is None:
            parts = (snapshot.get("workspace") or {}).get("existing_parts", ())
    return transition_receiving_head_occupancy(
        raw, receiving_head_scope(snapshot), "head" in parts, allocate=allocate,
    )


def receiving_head_occupant_status(snapshot, owner):
    """An old owner is invalid even when the replacement has identical holes."""
    state = reconcile_receiving_head_occupancy(snapshot)
    if state is None or not isinstance(owner, str):
        return "unknown"
    if state["active"] == owner:
        return "present"
    return "orphaned" if owner in state["retired"] else "unknown"
