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
    if not isinstance(layout, Mapping) or not isinstance(layout.get("sets"), (list, tuple)):
        raise ValueError("受電箱套／連資料不合法")
    counts = tuple(len(row["bays"]) for row in layout["sets"])
    if not counts or any(count < 1 for count in counts):
        raise ValueError("受電箱沒有可配置的連")
    if expected_counts is not None and tuple(expected_counts) != counts:
        raise ValueError("總連數已變動，請重新確認數量配置")
    if not isinstance(quantities, Mapping) or not quantities:
        raise ValueError("請先加入候選版本與數量")
    if not isinstance(assigned, Mapping):
        raise ValueError("配置對應必須是連位與候選版本的映射")
    ids = {row["id"] for row in candidates_for(library, role)}
    if not ids:
        raise ValueError("沒有可配置的候選版本")
    required = sum(counts)
    if any(version_id not in ids or type(qty) is not int or qty <= 0
           for version_id, qty in quantities.items()):
        raise ValueError("版本或配置數量不合法")
    if sum(quantities.values()) != required:
        raise ValueError(f"配置數量必須等於總連數 {required}")
    if len(assigned) != required:
        raise ValueError("每一連均須指定版本，不得重複或遺漏")
    targets = {(si, bi) for si, count in enumerate(counts)
               for bi in range(count)}
    if set(assigned) != targets:
        raise ValueError("配置連位與目前套／連不一致")
    used = dict.fromkeys(quantities, 0)
    for version_id in assigned.values():
        if version_id not in used:
            raise ValueError("配置中含未選擇的候選版本")
        used[version_id] += 1
    if any(used[key] != count for key, count in quantities.items()):
        raise ValueError("實際配置的版本數量不符合設定")
    snapshots = {key: candidate_features(library, role, key) for key in quantities}
    return tuple(
        (si, bi, deepcopy(snapshots[assigned[(si, bi)]]))
        for si, count in enumerate(counts)
        for bi in range(count)
    )


class AllocationDraft:
    """Per-side quantity and 2D draft, never written to candidate library."""

    def __init__(self, counts):
        self.counts = tuple(counts)
        self.quantities = {"head": {}, "tail": {}}
        self.assigned = {"head": {}, "tail": {}}
        self.step = {"head": 1, "tail": 1}
        self.active_version = {"head": None, "tail": None}

    def reconcile(self, counts, available):
        """Invalidate assignments when topology or candidates have changed."""
        latest = tuple(counts)
        if latest != self.counts:
            self.counts = latest
            for role in ("head", "tail"):
                self.assigned[role].clear()
                self.step[role] = 1
        for role in ("head", "tail"):
            ids = set(available[role])
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
        role_key(role)
        if version_id in self.quantities[role]:
            raise ValueError("同一候選版本不能重複配置")
        self.quantities[role][version_id] = 0
        self.assigned[role].clear()
        self.step[role] = 1
        self.active_version[role] = version_id

    def set_quantity(self, role, version_id, count):
        role_key(role)
        if version_id not in self.quantities[role] or type(count) is not int or count < 0:
            raise ValueError("數量不合法")
        if self.quantities[role][version_id] != count:
            self.quantities[role][version_id] = count
            self.assigned[role].clear()
            self.step[role] = 1

    def remove_version(self, role, version_id):
        role_key(role)
        if version_id not in self.quantities[role]:
            raise ValueError("候選版本不存在")
        del self.quantities[role][version_id]
        self.assigned[role].clear()
        self.step[role] = 1
        self.active_version[role] = next(iter(self.quantities[role]), None)

    def assign(self, role, set_index, bay_index):
        """Toggle or replace a 2D Bay in the draft, never product data."""
        role_key(role)
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
