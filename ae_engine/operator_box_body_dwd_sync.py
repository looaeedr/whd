"""Canonical Engine transaction for the legacy D-W-D BoxBody Fold sync.

The editor submits operator dimensions and stored Fold rows; only Engine may
decide whether a changed top W/D or a changed physical Fold core wins.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Mapping, Sequence

from .box_body_editor_readback import box_body_ui_segment_length_to_material
from .box_body_fold_profile import merge_box_body_fold_profile
from .cabinet_types.policy import canonical_family_name
from .operator_settings_transactions import normalize_operator_source_dimension


@dataclass(frozen=True)
class OperatorBoxBodyDwdSyncPlan:
    profile: tuple[dict[str, object], ...] | None
    last_width: float | None
    last_depth: float | None
    display_width: float | None = None
    display_depth: float | None = None
    replace_profile: bool = False


def _core_outside_length(row: Mapping[str, object], *, field: str) -> float:
    # These two source lengths are material and adjacent-BEND metadata;
    # this is a readback of the existing Engine Fold contract, not UI geometry.
    raw = row.get("len")
    add = row.get("ui_len_add", 0.0)
    if isinstance(raw, bool) or isinstance(add, bool):
        raise ValueError("BOX_BODY_DWD_CORE_SOURCE_INVALID")
    try:
        material, compensation = float(raw), float(add)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("BOX_BODY_DWD_CORE_SOURCE_INVALID") from exc
    normalize_operator_source_dimension(material, field=field)
    if compensation < 0:
        raise ValueError("BOX_BODY_DWD_CORE_SOURCE_INVALID")
    return normalize_operator_source_dimension(
        material + compensation, field=field,
    )


def _fold_value_changed(current: float, previous: float) -> bool:
    # Legacy manual Fold rows display whole millimetres. When a fractional
    # committed outside W/D is merely shown as round(W/D), this is not an edit
    # and must never reverse a previously committed physical source.
    return current != previous and current != float(round(previous))


def plan_operator_box_body_dwd_sync(
    snapshot: Mapping[str, object],
    profile: Sequence[Mapping[str, object]],
    *,
    top_width: object,
    top_depth: object,
    previous_width: object | None,
    previous_depth: object | None,
) -> OperatorBoxBodyDwdSyncPlan:
    """Project one detached BoxBody D-W-D source plan with no GUI/Tk imports.

    Quantity/Receiving Bay saved dimensions override manual Fold readback.
    Otherwise explicit W/D edits outrank the previous Fold core; untouched
    fractional outside dimensions cannot be reset by integer Fold display.
    Invalid live dimensions or late malformed core rows fail before commit.
    """
    source = dict(snapshot)
    rows = [deepcopy(dict(row)) for row in profile]

    quantity = (
        source.get("receiving_quantity_box")
        if source.get("active_mode") == "quantity" else None
    )
    if quantity:
        if not isinstance(quantity, Mapping):
            raise ValueError("BOX_BODY_DWD_QUANTITY_SOURCE_INVALID")
        w = normalize_operator_source_dimension(quantity.get("w"), field="w")
        d = normalize_operator_source_dimension(quantity.get("d"), field="d")
        # Canonical Quantity common-box dimensions, not stale global Settings,
        # feed the original Engine BoxBody Fold material generator.
        source.update({"w": w, "d": d})
        merged = merge_box_body_fold_profile(rows, source)
        return OperatorBoxBodyDwdSyncPlan(tuple(merged), w, d, replace_profile=True)

    if canonical_family_name(source) == "受電箱" and source.get("receiving_layout"):
        w = normalize_operator_source_dimension(source.get("w"), field="w")
        d = normalize_operator_source_dimension(source.get("d"), field="d")
        merged = merge_box_body_fold_profile(rows, source)
        return OperatorBoxBodyDwdSyncPlan(tuple(merged), w, d, replace_profile=True)

    top_w = normalize_operator_source_dimension(top_width, field="w")
    top_d = normalize_operator_source_dimension(top_depth, field="d")
    last_w = (top_w if previous_width is None else
              normalize_operator_source_dimension(previous_width, field="w"))
    last_d = (top_d if previous_depth is None else
              normalize_operator_source_dimension(previous_depth, field="d"))

    w_rows = [row for row in rows if row.get("core") == "W"]
    d_rows = [row for row in rows if row.get("core") == "D"]
    if len(w_rows) != 1 or len(d_rows) != 2:
        return OperatorBoxBodyDwdSyncPlan(None, last_w, last_d)

    core_w = _core_outside_length(w_rows[0], field="w")
    d_values = [_core_outside_length(row, field="d") for row in d_rows]
    display_w = None
    display_d = None

    if top_w != last_w:
        width = top_w
    elif _fold_value_changed(core_w, last_w):
        width = core_w
        display_w = core_w
    else:
        width = last_w
    w_rows[0]["len"] = box_body_ui_segment_length_to_material(
        w_rows[0], width, preserve_precision=True, field="w",
    )

    if top_d != last_d:
        depth = top_d
    else:
        changed = [value for value in d_values if _fold_value_changed(value, last_d)]
        depth = changed[0] if changed else last_d
        if depth != top_d:
            display_d = depth
    for row in d_rows:
        row["len"] = box_body_ui_segment_length_to_material(
            row, depth, preserve_precision=True, field="d",
        )

    return OperatorBoxBodyDwdSyncPlan(
        tuple(rows), width, depth, display_w, display_d,
    )
