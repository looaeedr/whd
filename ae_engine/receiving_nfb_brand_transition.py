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


def saved_parent_reselection_hole_ids(scope, current_brand, proposed_brand):
    """Read-only exact physical IDs for inherited models made stale by brand."""
    _require_brand(current_brand)
    _require_brand(proposed_brand)
    if current_brand == proposed_brand or scope.get("nfb_config_submitted") is not True:
        return ()
    from .receiving_nfb_persistence import normalize_nfb_saved_fields
    fields = normalize_nfb_saved_fields(scope)
    impacted = []
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
            impacted.append(hole["physical_hole_id"])
    return tuple(impacted)


def saved_parent_new_reselections(scope, current_brand, proposed_brand):
    """Count the same exact physical IDs exposed to the saved-state rebasing."""
    return len(saved_parent_reselection_hole_ids(
        scope, current_brand, proposed_brand,
    ))


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


def _quantity_nfb_parent_context(snapshot):
    """Resolve only persisted Quantity-version NFB parent state, not Tk aliases."""
    from collections.abc import Mapping
    from .receiving_quantity_versions import QuantityModel
    from .receiving_quantity_box import normalize_common_box

    if not isinstance(snapshot, Mapping) or snapshot.get("active_mode") != "quantity":
        raise ValueError("單只品牌需在單箱體模式設定")
    quantity = QuantityModel.from_payload(snapshot["quantity"])
    box = normalize_common_box(snapshot.get("receiving_quantity_box"))
    brand = quantity.nfb_parent_brand_for_version(
        quantity.selected_version_id, legacy_default=box["switch_brand"],
    )
    return quantity, box, brand


def project_receiving_quantity_nfb_parent_brand(snapshot):
    """Public read-only selected Quantity version's actual NFB brand."""
    return _quantity_nfb_parent_context(snapshot)[2]


def update_receiving_quantity_nfb_parent_brand(snapshot, proposed_brand):
    """Return detached state + changed flag for one Quantity brand transaction.

    The current selected version is authoritative; legacy common-box brand is
    migration-only. Preserve other versions and every physical NFB source.
    """
    from copy import deepcopy

    quantity, box, old_brand = _quantity_nfb_parent_context(snapshot)
    candidate = deepcopy(dict(snapshot))
    if (old_brand == proposed_brand
            and all("nfb_parent_brand" in row
                    for row in quantity.snapshot()["versions"])):
        return candidate, False
    changed = quantity.set_version_nfb_parent_brand(
        quantity.selected_version_id, proposed_brand,
        legacy_default=box["switch_brand"],
    )
    if changed:
        candidate["quantity"] = quantity.snapshot()
    return candidate, changed


def project_receiving_parent_brand_change_impact(source, proposed_brand, *, mode):
    """Read-only real saved hole IDs newly stale across Quantity or ALL Sets.

    Do not infer manufacturing readiness, unset a valid override, or count
    unsubmitted NFB draft slots. All actual Set/Bay ownership is Engine-side.
    """
    _require_brand(proposed_brand)
    if mode == "quantity":
        quantity, _box, old_brand = _quantity_nfb_parent_context(source)
        return saved_parent_new_reselections(
            quantity.nfb_config_for_version(quantity.selected_version_id),
            old_brand, proposed_brand,
        )
    if mode == "set_bay":
        from .receiving_layout import normalize_receiving_layout
        layout = normalize_receiving_layout(source)
        return sum(
            saved_parent_new_reselections(
                bay, set_row.get("switch_brand", "士林"), proposed_brand,
            )
            for set_row in layout["sets"] for bay in set_row["bays"]
        )
    raise ValueError("NFB 品牌預告模式不合法")



def update_receiving_one_set_nfb_parent_brand(layout, set_index, proposed_brand):
    """Commit one selected real Set's inherited NFB brand as an atomic Layout.

    The complete persisted Layout is verified before selecting the Set.  A
    rejected brand, malformed Set identity or invalid saved source cannot
    partially change the caller's Layout, its holes or approved world X.
    """
    from .receiving_layout import normalize_receiving_layout

    try:
        _require_brand(proposed_brand)
    except ValueError as exc:
        raise ValueError("不支援的開關品牌") from exc
    if type(set_index) is not int:
        raise ValueError("Receiving Set index must be an integer")
    candidate = normalize_receiving_layout(layout)
    if not 0 <= set_index < len(candidate["sets"]):
        raise IndexError("Receiving Set index out of range")

    updated, changed = rebase_receiving_set_parent_nfb_brand(
        candidate["sets"][set_index], proposed_brand,
    )
    if changed:
        candidate["sets"][set_index] = updated
    return candidate, changed


def update_receiving_all_set_nfb_parent_brand(layout, proposed_brand):
    """Atomically rebase every real Set's parent brand via the existing owner.

    A failed later Set must not leave earlier saved Bay NFB sources rebased.
    Return a detached canonical layout and whether any Set changed; do not
    infer models, manufacturing X or verified export eligibility.
    """
    from .receiving_layout import normalize_receiving_layout

    # Preserve the original all-Set GUI/API error contract while keeping the
    # single source of truth for accepted physical switch brands.
    try:
        _require_brand(proposed_brand)
    except ValueError as exc:
        raise ValueError("不支援的開關品牌") from exc
    candidate = normalize_receiving_layout(layout)
    changed = False
    for index, set_row in enumerate(candidate["sets"]):
        updated, set_changed = rebase_receiving_set_parent_nfb_brand(
            set_row, proposed_brand,
        )
        if set_changed:
            candidate["sets"][index] = updated
            changed = True
    return candidate, changed


def rebase_receiving_set_parent_nfb_brand(set_row, proposed_brand):
    """Return a detached Set row with stale inherited physical NFB X revoked.

    This Engine operation handles brand-dependent manufacturing proof state;
    callers only commit the returned candidate after successful validation.
    An explicit OVERRIDE and the saved source, model and X stay untouched.
    """
    from copy import deepcopy
    from .receiving_nfb_persistence import normalize_nfb_saved_fields

    _require_brand(proposed_brand)
    old_brand = set_row.get("switch_brand", "士林")
    _require_brand(old_brand)
    candidate = deepcopy(set_row)
    if old_brand == proposed_brand:
        return candidate, False

    for bay in candidate["bays"]:
        impacted = set(saved_parent_reselection_hole_ids(
            bay, old_brand, proposed_brand,
        ))
        if not impacted:
            continue
        saved = normalize_nfb_saved_fields(bay)
        changed = False
        for hole in saved["nfb_config"]["holes"]:
            if (hole["physical_hole_id"] in impacted
                    and hole["manual_x_state"] == "CONFIRMED"):
                hole["manual_x_state"] = "RECONFIRM_REQUIRED"
                changed = True
        if changed:
            bay["nfb_config"] = saved["nfb_config"]
    candidate["switch_brand"] = proposed_brand
    return candidate, True
