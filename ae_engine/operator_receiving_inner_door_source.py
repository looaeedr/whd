"""#2517 one headless owner for operator Receiving inner-door physical offset.

The GUI selects a Door cell and stages input only. Family policy supplies
the default for an *absent* legacy field; a present invalid physical distance
is always rejected before updating the source or producing geometry.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from copy import deepcopy

from .cabinet_types import policy as cabinet_family_policy
from .door_layout_physical_remap import receiving_inner_door_stable_id_for_cell


def operator_receiving_inner_door_commit_target(settings_mode: object) -> str:
    """Resolve an explicit Hole Editor entry's physical/candidate save authority.

    Project Set/Bay, Quantity and unrelated modals cannot silently choose the
    persistence target. Only this launch identity controls the Confirm All
    route; preview, NFB tab checks and Cancel All never imply a commit.
    """
    if settings_mode is None or settings_mode == "single":
        return "physical"
    if settings_mode == "candidate":
        return "candidate"
    raise ValueError("未知的內門編輯來源")


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


def _stage_operator_receiving_inner_door_rows(rows):
    """Validate and detach all saved Door-cell source identities before edit."""
    if rows is None:
        rows = ()
    if not isinstance(rows, (list, tuple)):
        raise ValueError("內門來源清單必須是列表")
    staged, keys, identities = [], set(), set()
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError("內門來源清單含有無效板件")
        key = item.get("cell_key")
        if not isinstance(key, str) or not key.strip():
            raise ValueError("內門門格來源無效")
        key = key.strip()
        # The original physical Door-cell owner validates nonnegative C/R.
        receiving_inner_door_stable_id_for_cell(key)
        if key in keys:
            raise ValueError(f"內門門格身份重複: {key}")
        keys.add(key)
        raw_id = item.get("stable_id")
        if isinstance(raw_id, bool):
            raise ValueError("內門實體身份無效")
        stable = str(raw_id or "").strip()
        if stable and stable in identities:
            raise ValueError(f"內門實體身份重複: {stable}")
        if stable:
            identities.add(stable)
        staged.append(deepcopy(item))
    return staged


def apply_operator_receiving_inner_door_presence(
    family_source, rows, *, cell_key, enabled,
):
    """Atomic physical inner-door toggle over a detached, validated source list.

    This is only an operator source transaction; saved NFB holes, Fold and
    verified manufacturing eligibility remain owned by their original Engine
    requests. An invalid saved row or ID collision rejects *all* changes.
    """
    if type(enabled) is not bool:
        raise ValueError("內門啟用狀態必須是布林值")
    if not isinstance(cell_key, str) or not cell_key.strip():
        raise ValueError("內門門格來源無效")
    key = cell_key.strip()
    receiving_inner_door_stable_id_for_cell(key)
    staged = _stage_operator_receiving_inner_door_rows(rows)
    prior = next((item for item in staged if item["cell_key"].strip() == key), None)
    result = [item for item in staged if item["cell_key"].strip() != key]
    if enabled:
        result.append(project_operator_receiving_inner_door_enabled_source(
            family_source, key, existing=prior,
        ))
    # A repeated stable identity in the newly generated row is a physical
    # collision, even when every cell key is individually valid.
    result = _stage_operator_receiving_inner_door_rows(result)
    result.sort(key=lambda item: tuple(
        int(part) for part in item["cell_key"].split(":", 1)
    ))
    return result


def apply_operator_receiving_inner_door_inward_offset(
    rows, *, cell_key, inward_offset_mm,
):
    """Return (detached saved rows, validated mm) or reject before any commit."""
    offset = normalize_operator_receiving_inner_door_inward_offset(
        inward_offset_mm,
    )
    if not isinstance(cell_key, str) or not cell_key.strip():
        raise ValueError("內門門格來源無效")
    key = cell_key.strip()
    receiving_inner_door_stable_id_for_cell(key)
    staged = _stage_operator_receiving_inner_door_rows(rows)
    target = next((item for item in staged if item["cell_key"].strip() == key), None)
    if target is None:
        raise ValueError(f"door cell has no enabled inner door: {key!r}")
    target["inward_offset_mm"] = offset
    return staged, offset


def project_operator_receiving_inner_door_cell_source(rows, *, cell_key):
    """Read one saved physical Door cell without GUI-owned identity matching.

    All stored rows are validated first, including duplicates unrelated to the
    selected cell. Returned values are detached copies; absent stays None.
    Only operator source is projected, not NFB or manufacturing verification.
    """
    if not isinstance(cell_key, str) or not cell_key.strip():
        raise ValueError("內門門格來源無效")
    key = cell_key.strip()
    receiving_inner_door_stable_id_for_cell(key)
    staged = _stage_operator_receiving_inner_door_rows(rows)
    return next(
        (item for item in staged if item["cell_key"].strip() == key),
        None,
    )
