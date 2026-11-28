"""Persistent occupant of the single horizontal Receiving Bay divider.

The part key locates a topology slot, never identifies its occupant.  This
module carries identity only: it does not qualify stock, marks or DXF.
An absent field denotes unprovisioned legacy authority; reading never mints.
"""
from collections.abc import Mapping
from dataclasses import dataclass
from re import fullmatch
from uuid import uuid4

from .door_dividers import divider_stable_id
from .door_layout_numeric_transitions import door_layout_cells
from .operator_settings_transactions import normalize_operator_settings_boolean

OCCUPANCY = "horizontal_divider_occupancy"


def _locator(bay):
    door = bay.get("door_state")
    if not isinstance(door, Mapping):
        return None
    if not normalize_operator_settings_boolean(door.get("multi_door_enabled", False)):
        return None
    columns = door.get("door_layout_columns") or ()
    if not columns:
        return None
    cells = door_layout_cells(columns, total_width=bay["width"], total_height=bay["height"])
    # This slice deliberately does not infer continuity in a multi-boundary
    # layout. Only the canonical single-column, two-row physical C slot.
    if tuple((c.column_index, c.row_index) for c in cells) != ((0, 0), (0, 1)):
        return None
    if cells[0].edges.bottom or not cells[1].edges.bottom:
        return None
    scope = door.get("door_layout_scope")
    if not isinstance(scope, str) or not scope.strip():
        return None
    return divider_stable_id(scope.strip(), "HORIZONTAL", "C0:R0|R1")


def _new_occupant(bay):
    locator = _locator(bay)
    return None if locator is None else {
        "part_key": locator, "owner_id": f"divider-owner:{uuid4().hex}",
    }


def initialize_horizontal_divider_occupancy(bay):
    """Only explicit new Bay creation; never from normalization or Open."""
    bay[OCCUPANCY] = _new_occupant(bay)


def transition_horizontal_divider_occupancy(before, after, *, allocate=True):
    """Committed Bay edit; absent legacy lineage is never backfilled."""
    if OCCUPANCY not in before:
        return
    prior, current = _locator(before), _locator(after)
    if prior != current:
        after[OCCUPANCY] = _new_occupant(after) if allocate else None


def normalize_horizontal_divider_occupancy(raw_bay, bay, seen):
    """Read/validate detached saved authority, never allocate an owner."""
    if OCCUPANCY not in raw_bay:
        return
    value = raw_bay[OCCUPANCY]
    if value is None:
        bay[OCCUPANCY] = None
        return
    if (not isinstance(value, Mapping) or set(value) != {"owner_id", "part_key"}
            or type(value["owner_id"]) is not str
            or not fullmatch(r"divider-owner:[a-f0-9]{12}4[a-f0-9]{3}[89ab][a-f0-9]{15}", value["owner_id"])
            or type(value["part_key"]) is not str
            or value["part_key"] != _locator(bay)):
        raise ValueError("RECEIVING_HORIZONTAL_DIVIDER_OWNER_INVALID")
    if value["owner_id"] in seen:
        raise ValueError("RECEIVING_HORIZONTAL_DIVIDER_OWNER_DUPLICATE")
    seen.add(value["owner_id"])
    bay[OCCUPANCY] = dict(value)


@dataclass(frozen=True)
class ReceivingHorizontalDividerOwnerReceipt:
    """Identity-only witness; no material or manufacturing/marking permission."""
    set_id: str
    bay_id: str
    part_key: str
    owner_id: str


def open_receiving_horizontal_divider_owner_receipt(snapshot, part_key, *, set_index, bay_index, expected=None):
    """Read the exact Bay occupant; reject legacy and Quantity projections."""
    from .cabinet_types.receiving import is_receiving_snapshot
    from .receiving_layout import normalize_receiving_layout
    if (not isinstance(snapshot, Mapping) or not is_receiving_snapshot(snapshot)
            or snapshot.get("active_mode", "set_bay") != "set_bay"
            or "receiving_quantity_box" in snapshot):
        raise ValueError("RECEIVING_HORIZONTAL_DIVIDER_OWNER_SCOPE_UNSUPPORTED")
    layout = normalize_receiving_layout(snapshot.get("receiving_layout"))
    if type(set_index) is not int or not 0 <= set_index < len(layout["sets"]):
        raise ValueError("RECEIVING_HORIZONTAL_DIVIDER_OWNER_SCOPE_INVALID")
    group = layout["sets"][set_index]
    if type(bay_index) is not int or not 0 <= bay_index < len(group["bays"]):
        raise ValueError("RECEIVING_HORIZONTAL_DIVIDER_OWNER_SCOPE_INVALID")
    bay = group["bays"][bay_index]
    occupant = bay.get(OCCUPANCY)
    if occupant is None or occupant["part_key"] != part_key:
        raise ValueError("RECEIVING_HORIZONTAL_DIVIDER_OWNER_STALE" if expected is not None
                         else "RECEIVING_HORIZONTAL_DIVIDER_OWNER_REQUIRED")
    receipt = ReceivingHorizontalDividerOwnerReceipt(group["stable_id"], bay["stable_id"],
                                                       part_key, occupant["owner_id"])
    if expected is not None and receipt != expected:
        raise ValueError("RECEIVING_HORIZONTAL_DIVIDER_OWNER_STALE")
    return receipt
