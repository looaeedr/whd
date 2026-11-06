# -*- coding: utf-8 -*-
"""Canonical Receiving Set/Bay applied-version provenance transitions.

An explicit operator Live Apply changes the saved applied-version marker only.
It does not replace Hole Editor Features, NFB source, physical X evidence or
certify a new manufacturing result.
"""
from __future__ import annotations

from .receiving_shared_settings import edit_setting, unlink_setting, validate_setting


def mark_receiving_bays_live_version(layout, role, set_index, bay_indices):
    """Return detached layout, validated highlighted indices and Bay identities."""
    if role not in ("head", "tail", "inner-door"):
        raise ValueError("不支援的版本角色")
    if type(set_index) is not int or not 0 <= set_index < len(layout["sets"]):
        raise ValueError("套不存在")
    try:
        supplied = tuple(bay_indices)
    except TypeError as exc:
        raise ValueError("請先高亮有效的連") from exc
    count = len(layout["sets"][set_index]["bays"])
    if not supplied or any(type(bi) is not int or not 0 <= bi < count for bi in supplied):
        raise ValueError("請先高亮有效的連")
    selected = tuple(sorted(set(supplied)))
    kind = role.replace("-", "_") + "_version_id"
    live = validate_setting(kind, "")

    result = layout
    for bi in selected:
        result = unlink_setting(
            result, set_index=set_index, bay_index=bi, kind=kind,
        )
        result = edit_setting(
            result, set_index=set_index, bay_index=bi, kind=kind, value=live,
        )
    ids = tuple(str(result["sets"][set_index]["bays"][bi]["stable_id"])
                for bi in selected)
    return result, selected, ids
