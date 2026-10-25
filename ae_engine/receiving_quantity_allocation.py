# -*- coding: utf-8 -*-
"""Two-step Receiving hole-candidate quantity/allocation validation.

The candidate library remains project-global. The draft is only UI state;
the returned allocation plan becomes real per-Bay features only when confirmed.
"""
from __future__ import annotations
from collections.abc import Mapping
from copy import deepcopy
from ae_engine.receiving_hole_candidates import (
    role_key, candidates_for, candidate_features,
)


def validate_quantity_allocation(layout, library, role, quantities, assigned, *, expected_counts=None):
    """Return ordered (set, bay, features) rows or raise before touching product.

    quantities maps candidate IDs to positive Bay counts. assigned maps
    (zero-based Set, Bay) to a candidate ID. All Sets count, not highlights.
    """
    role_key(role)
    from ae_engine.receiving_assignment_core import validate_positions
    positions = validate_positions(
        layout, (row["id"] for row in candidates_for(library, role)),
        quantities, assigned, expected_counts=expected_counts,
    )
    snapshots = {key: candidate_features(library, role, key) for key in quantities}
    return tuple(
        (si, bi, deepcopy(snapshots[assigned[(si, bi)]]))
        for si, bi in positions
    )


class AllocationDraft:
    """Per-side quantity and 2D draft, never written to candidate library."""

    def __init__(self, counts, *, roles=("head", "tail"), validate_role=role_key):
        self.counts = tuple(counts)
        self.roles = tuple(roles)
        self.validate_role = validate_role
        self.quantities = {role: {} for role in self.roles}
        self.assigned = {role: {} for role in self.roles}
        self.step = {role: 1 for role in self.roles}
        self.active_version = {role: None for role in self.roles}

    def reconcile(self, counts, available):
        """Invalidate assignments when topology or candidates have changed."""
        # Validate every source inventory before changing any draft state.
        # set("v1") would silently authorize bogus candidate IDs "v"/"1".
        if not isinstance(available, Mapping):
            raise ValueError("候選版本清單必須是映射")
        inventories = {}
        for role in self.roles:
            try:
                candidate_rows = available[role]
                if isinstance(candidate_rows, (str, bytes, Mapping)):
                    raise ValueError("候選版本 ID 清單不合法")
                ids = tuple(candidate_rows)
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                raise ValueError("候選版本 ID 清單不合法") from exc
            if any(not isinstance(value, str) or not value for value in ids):
                raise ValueError("候選版本 ID 清單不合法")
            inventories[role] = set(ids)
        latest = tuple(counts)
        if latest != self.counts:
            self.counts = latest
            for role in self.roles:
                self.assigned[role].clear()
                self.step[role] = 1
        for role in self.roles:
            ids = inventories[role]
            if any(key not in ids for key in self.quantities[role]):
                self.quantities[role] = {
                    key: qty for key, qty in self.quantities[role].items()
                    if key in ids
                }
                self.assigned[role].clear()
                self.step[role] = 1
            if self.active_version[role] not in self.quantities[role]:
                self.active_version[role] = next(iter(self.quantities[role]), None)

    def add_version(self, role, version_id):
        self.validate_role(role)
        if version_id in self.quantities[role]:
            raise ValueError("同一候選版本不能重複配置")
        self.quantities[role][version_id] = 0
        self.assigned[role].clear()
        self.step[role] = 1
        self.active_version[role] = version_id

    def set_quantity(self, role, version_id, count):
        self.validate_role(role)
        if version_id not in self.quantities[role] or type(count) is not int or count < 0:
            raise ValueError("數量不合法")
        if self.quantities[role][version_id] != count:
            self.quantities[role][version_id] = count
            self.assigned[role].clear()
            self.step[role] = 1

    def remove_version(self, role, version_id):
        self.validate_role(role)
        if version_id not in self.quantities[role]:
            raise ValueError("候選版本不存在")
        del self.quantities[role][version_id]
        self.assigned[role].clear()
        self.step[role] = 1
        self.active_version[role] = next(iter(self.quantities[role]), None)

    def assign(self, role, set_index, bay_index):
        """Toggle or replace a 2D Bay in the draft, never product data."""
        self.validate_role(role)
        if (type(set_index) is not int or type(bay_index) is not int or
                not 0 <= set_index < len(self.counts) or
                not 0 <= bay_index < self.counts[set_index]):
            raise ValueError("指定的連不存在")
        selected = self.active_version[role]
        if selected not in self.quantities[role] or self.quantities[role][selected] <= 0:
            raise ValueError("請先選擇有設定數量的版本")
        allocations = self.assigned[role]
        key = (set_index, bay_index)
        if allocations.get(key) == selected:
            del allocations[key]
            return
        used = sum(value == selected for value in allocations.values())
        if used >= self.quantities[role][selected]:
            raise ValueError("此版本已達設定連數，請先取消或改派其他連")
        allocations[key] = selected

    def ready_for_positioning(self, role):
        rows = self.quantities[role]
        return bool(rows) and all(type(n) is int and n > 0 for n in rows.values()) and (
            sum(rows.values()) == sum(self.counts)
        )
