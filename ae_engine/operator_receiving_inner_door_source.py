"""#2517 one headless owner for operator Receiving inner-door physical offset.

The GUI selects a Door cell and stages input only. Family policy supplies
the default for an *absent* legacy field; a present invalid physical distance
is always rejected before updating the source or producing geometry.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

from .cabinet_types import policy as cabinet_family_policy
from .door_layout_physical_remap import receiving_inner_door_stable_id_for_cell


def normalize_operator_receiving_inner_door_inward_offset(value: object) -> float:
    """0 is valid (flush placement), negative/NaN/bool may never be mm."""
    if isinstance(value, bool):
        raise ValueError("內門內退尺寸必須是有限非負數值")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("內門內退尺寸必須是有限非負數值") from exc
    if not math.isfinite(number) or number < 0.0:
        raise ValueError("內門內退尺寸必須是有限非負數值")
    return number


def resolve_operator_receiving_inner_door_inward_offset(
    family_source: object, saved_item: Mapping[str, object] | None = None,
) -> float:
    """Read the exact saved per-Door physical mm; default only when absent."""
    if saved_item is None:
        item: Mapping[str, object] = {}
    elif isinstance(saved_item, Mapping):
        item = saved_item
    else:
        raise ValueError("內門來源必須是對應表")
    raw = (
        item["inward_offset_mm"] if "inward_offset_mm" in item
        else cabinet_family_policy.default_inner_door_inward_offset_mm(
            family_source, default=0.0,
        )
    )
    return normalize_operator_receiving_inner_door_inward_offset(raw)


def project_operator_receiving_inner_door_enabled_source(
    family_source: object, cell_key: object, *,
    existing: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Prepare identity-preserving physical Door source on an explicit toggle.

    No Set/Bay aggregation and no feature/geometry transformation are done.
    The physical part stable ID and default inward mm are Engine responsibilities.
    """
    if not isinstance(cell_key, str) or not cell_key.strip():
        raise ValueError("內門門格來源無效")
    key = cell_key.strip()
    if existing is not None and not isinstance(existing, Mapping):
        raise ValueError("內門來源必須是對應表")
    prior = dict(existing or {})
    if "cell_key" in prior and str(prior["cell_key"]).strip() != key:
        raise ValueError("內門門格身份與保存來源不一致")
    sides = prior.get("included_frame_sides") or ("top", "left", "right")
    if not isinstance(sides, (tuple, list)):
        raise ValueError("內門框邊來源無效")
    return {
        **prior,
        "stable_id": str(prior.get("stable_id") or receiving_inner_door_stable_id_for_cell(key)).strip(),
        "cell_key": key,
        "included_frame_sides": list(sides),
        "inward_offset_mm": resolve_operator_receiving_inner_door_inward_offset(
            family_source, prior,
        ),
    }
