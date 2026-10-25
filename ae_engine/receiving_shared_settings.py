# -*- coding: utf-8 -*-
"""Receiving 每連設定的獨立共享關係；UI 只保存選取，不擁有設定值。"""
from copy import deepcopy
from collections.abc import Mapping
from math import isfinite

from .sheetmetal_feature_core import CircleFeature, RectFeature, ProfileFeature

SETTING_DEFAULTS = {
    "back_panel_mode": "FULL",
    "head_features": [],
    "tail_features": [],
    "inner_door_layers": 1,
    # Two independent layers; each slot may retain legacy DXF or typed V5
    # brand/model identities. Repeated physical instances are not deduplicated.
    "inner_door_models": ["", ""],
    # Per physical inner-door sheet, not a second NFB or generic hole owner.
    "inner_door_features": {},
    # NFB opening-row centers measured from the TOP edge of the selected work area.
    "inner_door_layer_heights_mm": [330.0, 830.0],
    # Per-Bay display provenance. None=never applied, ""=explicit 即時.
    "head_version_id": None,
    "tail_version_id": None,
    "inner_door_version_id": None,
}

def default_receiving_nfb_layer_heights(layer_count):
    """One manufacturing Y authority for newly chosen 1/2 NFB tiers.

    Keep the stored two-slot schema: in one-tier mode the second slot is
    inactive, while the visible first tier uses the approved 1100-cell 550.
    The existing shared 330/830 defaults apply only once two tiers exist.
    """
    if type(layer_count) is not int or layer_count not in (1, 2):
        raise ValueError("NFB height defaults require exactly 1 or 2 tiers")
    heights = list(SETTING_DEFAULTS["inner_door_layer_heights_mm"])
    if layer_count == 1:
        from .receiving_nfb_y_projection import approved_nominal_y_mm
        heights[0] = float(approved_nominal_y_mm(1)[0])
    return heights


def transition_receiving_nfb_layer_heights(heights, *, old_count, new_count):
    """Change untouched defaults on a tier-count edit, never rewrite custom Y."""
    old = default_receiving_nfb_layer_heights(old_count)
    target = default_receiving_nfb_layer_heights(new_count)
    actual = validate_setting("inner_door_layer_heights_mm", heights)
    return target if old_count != new_count and actual == old else actual


def switch_filenames_in_layer(slot):
    """Return physical switch occurrences, never deduplicate quantity."""
    if isinstance(slot, str):
        names = () if not slot else (slot,)
    elif isinstance(slot, (list, tuple)):
        names = tuple(slot)
        if not names:
            return ()
    else:
        raise ValueError("每層開關須為型號或型號清單")
    from .receiving_nfb_model_identity import validate_stored_model_ref
    for name in names:
        validate_stored_model_ref(name)
    return names


def pack_switch_layer(names):
    """Canonical compact slot: keep old 0/1-string project data compatible."""
    items = switch_filenames_in_layer(list(names))
    return "" if not items else items[0] if len(items) == 1 else list(items)


def switch_model_layers(value):
    """Normalize old [str,str] and new [str|list,str|list] without data loss."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("內門須包含兩層獨立的開關清單")
    return [pack_switch_layer(switch_filenames_in_layer(slot)) for slot in value]


def validate_setting(kind, value):
    if kind not in SETTING_DEFAULTS:
        raise ValueError("不支援的每連設定")
    if kind == "back_panel_mode":
        value = str(value).upper()
        if value not in {"FULL", "HALF", "BACK_OPENING"}:
            raise ValueError("不支援的背板型式")
    elif kind.endswith("_version_id"):
        import re
        role = {
            "head_version_id": "head",
            "tail_version_id": "tail",
            "inner_door_version_id": "inner-door",
        }[kind]
        if value is not None and value != "" and (
            not isinstance(value, str)
            or re.fullmatch(rf"{re.escape(role)}-v[1-9][0-9]*", value) is None
        ):
            raise ValueError("不合法的已套用版本編號")
    elif kind == "inner_door_layers":
        if value not in (1, 2) or isinstance(value, bool):
            raise ValueError("內門層數必須為 1 或 2")
    elif kind == "inner_door_models":
        value = switch_model_layers(value)
    elif kind == "inner_door_features":
        # The feature classes are imported at module scope. A local import
        # would shadow them for the sibling head/tail branches (UnboundLocalError).
        if not isinstance(value, Mapping):
            raise ValueError("內門孔位必須依實體板件 ID 保存")
        normalized = {}
        for part_key, features in value.items():
            if (not isinstance(part_key, str) or not part_key.startswith("inner_door:")
                    or not part_key.endswith(":panel")
                    or not isinstance(features, (list, tuple))
                    or any(not isinstance(feature, (CircleFeature, RectFeature, ProfileFeature))
                           for feature in features)):
                raise ValueError("內門候選只能保存真實門板的 Hole Editor Feature")
            normalized[part_key] = list(features)
        value = normalized
    elif kind == "inner_door_layer_heights_mm":
        # Old saved NFB projects have no operator-height authority; None
        # retains their original certified nominal 290/790 Y until edited.
        if value is None:
            return None
        message = "第一層／第二層高度須為正數、由上往下遞增（mm）"
        if (not isinstance(value, (list, tuple)) or len(value) != 2
                or any(type(v) not in (int, float) for v in value)):
            raise ValueError(message)
        try:
            heights = [float(v) for v in value]
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(message) from exc
        if (not all(isfinite(v) and v > 0 for v in heights)
                or heights[0] >= heights[1]):
            raise ValueError(message)
        value = heights
    elif not isinstance(value, (list, tuple)) or any(
        not isinstance(f, (CircleFeature, RectFeature, ProfileFeature))
        for f in value
    ):
        raise ValueError("封頭尾設定必須是 Hole Editor feature 清單")
    else:
        value = list(value)
    return deepcopy(value)


def normalize_set_settings(raw, bays):
    """每項設定各自有 refs/values；只保留仍被實體連引用的值。"""
    # Only an absent saved source denotes default settings. Explicit [] or
    # invalid scalar payloads must not silently erase physical Bay references.
    if raw is not None and not isinstance(raw, Mapping):
        raise ValueError("共享設定必須為物件")
    source = dict(raw or {})
    legacy_height_absent = (
        "inner_door_layer_heights_mm" not in source
        and (bool(source) or any(bay.get("nfb_config_submitted") is True for bay in bays))
    )
    unknown = set(source) - set(SETTING_DEFAULTS)
    if unknown:
        raise ValueError(f"不支援的每連設定：{sorted(unknown)}")
    result = {}
    for kind, default in SETTING_DEFAULTS.items():
        row = source.get(kind, {})
        if not isinstance(row, Mapping):
            raise ValueError("共享設定必須為物件")
        raw_refs, raw_values = row.get("refs", {}), row.get("values", {})
        if not isinstance(raw_refs, Mapping) or not isinstance(raw_values, Mapping):
            raise ValueError("共享設定 refs/values 必須為物件")
        refs, values = dict(raw_refs), dict(raw_values)
        new_refs, new_values = {}, {}
        for bay in bays:
            bay_id = str(bay["stable_id"])
            ref = refs.get(bay_id)
            if ref is None:
                ref = f"{bay_id}:{kind}"
                value = bay.get(
                    kind,
                    None if legacy_height_absent and kind == "inner_door_layer_heights_mm"
                    else default,
                )
            else:
                if not isinstance(ref, str) or not ref or ref not in values:
                    raise ValueError("共享設定引用不存在")
                value = values[ref]
            new_refs[bay_id] = ref
            new_values[ref] = validate_setting(kind, value)
        result[kind] = {"refs": new_refs, "values": new_values}
    return result


def _require_valid_index(index, length, message):
    if isinstance(index, bool) or not isinstance(index, int) or index < 0 or index >= length:
        raise IndexError(message)


def setting_value(set_row, bay_index, kind):
    _require_valid_index(bay_index, len(set_row["bays"]), "連選取超出範圍")
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
    _require_valid_index(set_index, len(result["sets"]), "組選取超出範圍")
    selected = result["sets"][set_index]
    _require_valid_index(bay_index, len(selected["bays"]), "連選取超出範圍")
    selected["settings"] = normalize_set_settings(selected.get("settings"), selected["bays"])
    row = selected["settings"][kind]
    bay_id = selected["bays"][bay_index]["stable_id"]
    row["values"][row["refs"][bay_id]] = validate_setting(kind, value)
    return normalize_receiving_layout(result)


def share_setting(layout, *, set_index, bay_indices, kind, source_bay_index):
    from ae_engine.receiving_layout import normalize_receiving_layout
    result = normalize_receiving_layout(layout)
    _require_valid_index(set_index, len(result["sets"]), "組選取超出範圍")
    selected = result["sets"][set_index]
    # Validate real Set/Bay owners *before* dict.fromkeys(): bool aliases
    # integer Bay 1, and nested UI selections may be unhashable.  Neither
    # can create a valid shared reference for a different physical Bay.
    try:
        supplied = tuple(bay_indices)
    except TypeError as exc:
        raise IndexError("連選取超出範圍") from exc
    _require_valid_index(source_bay_index, len(selected["bays"]), "連選取超出範圍")
    for index in supplied:
        _require_valid_index(index, len(selected["bays"]), "連選取超出範圍")
    indices = tuple(dict.fromkeys(supplied))
    if len(indices) < 2 or source_bay_index not in indices:
        raise ValueError("連動需選擇至少兩連，並包含來源連")
    selected["settings"] = normalize_set_settings(selected.get("settings"), selected["bays"])
    row = selected["settings"][kind]
    source_id = selected["bays"][source_bay_index]["stable_id"]
    ref = row["refs"][source_id]
    for index in indices:
        row["refs"][selected["bays"][index]["stable_id"]] = ref
    return normalize_receiving_layout(result)


def unlink_setting(layout, *, set_index, bay_index, kind):
    from ae_engine.receiving_layout import normalize_receiving_layout
    result = normalize_receiving_layout(layout)
    _require_valid_index(set_index, len(result["sets"]), "組選取超出範圍")
    selected = result["sets"][set_index]
    _require_valid_index(bay_index, len(selected["bays"]), "連選取超出範圍")
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
