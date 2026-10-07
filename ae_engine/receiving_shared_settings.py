# -*- coding: utf-8 -*-
"""Receiving 每連設定的獨立共享關係；UI 只保存選取，不擁有設定值。"""
from copy import deepcopy
from collections.abc import Mapping

SETTING_DEFAULTS = {
    "back_panel_mode": "FULL",
    "head_features": [],
    "tail_features": [],
    "inner_door_layers": 1,
}


def validate_setting(kind, value):
    if kind not in SETTING_DEFAULTS:
        raise ValueError("不支援的每連設定")
    if kind == "back_panel_mode":
        value = str(value).upper()
        if value not in {"FULL", "HALF", "BACK_OPENING"}:
            raise ValueError("不支援的背板型式")
    elif kind == "inner_door_layers":
        if value not in (1, 2) or isinstance(value, bool):
            raise ValueError("內門層數必須為 1 或 2")
    elif not isinstance(value, (list, tuple)):
        raise ValueError("封頭尾設定必須是 Hole Editor feature 清單")
    return deepcopy(value)


def normalize_set_settings(raw, bays):
    """每項設定各自有 refs/values；只保留仍被實體連引用的值。"""
    source = dict(raw or {})
    unknown = set(source) - set(SETTING_DEFAULTS)
    if unknown:
        raise ValueError(f"不支援的每連設定：{sorted(unknown)}")
    result = {}
    for kind, default in SETTING_DEFAULTS.items():
        row = source.get(kind, {})
        if not isinstance(row, Mapping):
            raise ValueError("共享設定必須為物件")
        refs, values = dict(row.get("refs", {})), dict(row.get("values", {}))
        new_refs, new_values = {}, {}
        for bay in bays:
            bay_id = str(bay["stable_id"])
            ref = refs.get(bay_id)
            if ref is None:
                ref = f"{bay_id}:{kind}"
                value = bay.get(kind, default)
            else:
                if not isinstance(ref, str) or not ref or ref not in values:
                    raise ValueError("共享設定引用不存在")
                value = values[ref]
            new_refs[bay_id] = ref
            new_values[ref] = validate_setting(kind, value)
        result[kind] = {"refs": new_refs, "values": new_values}
    return result


def setting_value(set_row, bay_index, kind):
    bay = set_row["bays"][bay_index]
    if kind not in SETTING_DEFAULTS:
        raise ValueError("不支援的每連設定")
    if "settings" not in set_row:
        return validate_setting(kind, bay.get(kind, SETTING_DEFAULTS[kind]))
    row = set_row["settings"][kind]
    return deepcopy(row["values"][row["refs"][bay["stable_id"]]])


def edit_setting(layout, *, set_index, bay_index, kind, value):
    from ae_engine.receiving_layout import normalize_receiving_layout
    result = normalize_receiving_layout(layout)
    selected = result["sets"][set_index]
    selected["settings"] = normalize_set_settings(selected.get("settings"), selected["bays"])
    row = selected["settings"][kind]
    bay_id = selected["bays"][bay_index]["stable_id"]
    row["values"][row["refs"][bay_id]] = validate_setting(kind, value)
    return normalize_receiving_layout(result)


def share_setting(layout, *, set_index, bay_indices, kind, source_bay_index):
    from ae_engine.receiving_layout import normalize_receiving_layout
    result = normalize_receiving_layout(layout)
    selected = result["sets"][set_index]
    indices = tuple(dict.fromkeys(bay_indices))
    if len(indices) < 2 or source_bay_index not in indices:
        raise ValueError("連動需選擇至少兩連，並包含來源連")
    selected["settings"] = normalize_set_settings(selected.get("settings"), selected["bays"])
    row = selected["settings"][kind]
    source_id = selected["bays"][source_bay_index]["stable_id"]
    ref = row["refs"][source_id]
    for index in indices:
        if index < 0 or index >= len(selected["bays"]):
            raise IndexError("連選取超出範圍")
        row["refs"][selected["bays"][index]["stable_id"]] = ref
    return normalize_receiving_layout(result)


def unlink_setting(layout, *, set_index, bay_index, kind):
    from ae_engine.receiving_layout import normalize_receiving_layout
    result = normalize_receiving_layout(layout)
    selected = result["sets"][set_index]
    selected["settings"] = normalize_set_settings(selected.get("settings"), selected["bays"])
    row = selected["settings"][kind]
    bay_id = selected["bays"][bay_index]["stable_id"]
    old_ref = row["refs"][bay_id]
    if list(row["refs"].values()).count(old_ref) == 1:
        return result
    base = f"{bay_id}:{kind}"
    ref, ordinal = base, 1
    while ref in row["values"]:
        ordinal += 1
        ref = f"{base}:{ordinal}"
    row["values"][ref] = deepcopy(row["values"][old_ref])
    row["refs"][bay_id] = ref
    return normalize_receiving_layout(result)
