# -*- coding: utf-8 -*-
"""Shared Set/Bay quantity and allocation checks, independent of part payload."""
from collections.abc import Mapping


def validate_positions(layout, available_ids, quantities, assigned, *, expected_counts=None):
    if not isinstance(layout, Mapping) or not isinstance(layout.get("sets"), (list, tuple)):
        raise ValueError("受電箱套／連資料不合法")
    sets = layout["sets"]
    if any(not isinstance(row, Mapping) or not isinstance(row.get("bays"), (list, tuple))
           for row in sets):
        raise ValueError("受電箱套／連資料不合法")
    counts = tuple(len(row["bays"]) for row in sets)
    if not counts or any(n < 1 for n in counts):
        raise ValueError("受電箱沒有可配置的連")
    if expected_counts is not None:
        if (not isinstance(expected_counts, (list, tuple))
                or any(type(value) is not int for value in expected_counts)
                or tuple(expected_counts) != counts):
            raise ValueError("總連數已變動，請重新確認數量配置")
    if not isinstance(quantities, Mapping) or not quantities:
        raise ValueError("請先加入候選版本與數量")
    if not isinstance(assigned, Mapping):
        raise ValueError("配置對應必須是連位與候選版本的映射")
    # Candidate inventories are sequences of version IDs, not a single
    # string (set("v1") would otherwise authorize fake "v" and "1" IDs).
    # The persisted candidate libraries own real nonempty string identities.
    if isinstance(available_ids, (str, bytes, Mapping)):
        raise ValueError("候選版本 ID 清單不合法")
    try:
        source_ids = tuple(available_ids)
    except TypeError as exc:
        raise ValueError("候選版本 ID 清單不合法") from exc
    if any(not isinstance(version_id, str) or not version_id
           for version_id in source_ids):
        raise ValueError("候選版本 ID 清單不合法")
    ids = set(source_ids)
    if not ids:
        raise ValueError("沒有可配置的候選版本")
    required = sum(counts)
    if any(not isinstance(version_id, str) or not version_id
           or version_id not in ids or type(qty) is not int or qty <= 0
           for version_id, qty in quantities.items()):
        raise ValueError("版本或配置數量不合法")
    if sum(quantities.values()) != required:
        raise ValueError(f"配置數量必須等於總連數 {required}")
    if len(assigned) != required:
        raise ValueError("每一連均須指定版本，不得重複或遺漏")
    positions = tuple((si, bi) for si, count in enumerate(counts)
                      for bi in range(count))
    if (any(not isinstance(key, tuple) or len(key) != 2
            or type(key[0]) is not int or type(key[1]) is not int
            for key in assigned) or set(assigned) != set(positions)):
        raise ValueError("配置連位與目前套／連不一致")
    used = dict.fromkeys(quantities, 0)
    for version_id in assigned.values():
        if not isinstance(version_id, str) or version_id not in used:
            raise ValueError("配置中含未選擇的候選版本")
        used[version_id] += 1
    if any(used[key] != count for key, count in quantities.items()):
        raise ValueError("實際配置的版本數量不符合設定")
    return positions
