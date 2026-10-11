# -*- coding: utf-8 -*-
"""Shared Set/Bay quantity and allocation checks, independent of part payload."""
from collections.abc import Mapping


def validate_positions(layout, available_ids, quantities, assigned, *, expected_counts=None):
    if not isinstance(layout, Mapping) or not isinstance(layout.get("sets"), (list, tuple)):
        raise ValueError("受電箱套／連資料不合法")
    counts = tuple(len(row["bays"]) for row in layout["sets"])
    if not counts or any(n < 1 for n in counts):
        raise ValueError("受電箱沒有可配置的連")
    if expected_counts is not None and tuple(expected_counts) != counts:
        raise ValueError("總連數已變動，請重新確認數量配置")
    if not isinstance(quantities, Mapping) or not quantities:
        raise ValueError("請先加入候選版本與數量")
    if not isinstance(assigned, Mapping):
        raise ValueError("配置對應必須是連位與候選版本的映射")
    ids = set(available_ids)
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
    positions = tuple((si, bi) for si, count in enumerate(counts)
                      for bi in range(count))
    if set(assigned) != set(positions):
        raise ValueError("配置連位與目前套／連不一致")
    used = dict.fromkeys(quantities, 0)
    for version_id in assigned.values():
        if version_id not in used:
            raise ValueError("配置中含未選擇的候選版本")
        used[version_id] += 1
    if any(used[key] != count for key, count in quantities.items()):
        raise ValueError("實際配置的版本數量不符合設定")
    return positions
