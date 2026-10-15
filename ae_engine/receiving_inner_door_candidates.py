# -*- coding: utf-8 -*-
"""Independent Receiving inner-door candidates.

Only version operations are parallel to head/tail; payload authority is never
merged with receiving_hole_candidates or the quantity-mode product model.
A candidate has no Bay owner before explicit Apply.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import re

from ae_engine.receiving_shared_settings import validate_setting, SETTING_DEFAULTS

KEY = "receiving_inner_door_candidates"
SCHEMA = "receiving-inner-door-candidates-v1"
ROLE = "inner-door"


def validate_door_config(config):
    if not isinstance(config, Mapping):
        raise ValueError("內門版本設定須為物件")
    required = {"layers", "models"}
    if not required.issubset(config) or set(config) - (required | {"layer_heights_mm"}):
        raise ValueError("內門版本設定須包含 layers／models，及可選的每層高度")
    layers = validate_setting("inner_door_layers", config["layers"])
    models = validate_setting("inner_door_models", config["models"])
    if layers == 1 and models[1]:
        raise ValueError("單層內門不能配置第二層開關")
    result = {"layers": layers, "models": models}
    if "layer_heights_mm" in config:
        result["layer_heights_mm"] = validate_setting(
            "inner_door_layer_heights_mm", config["layer_heights_mm"]
        )
    return result


def normalize_inner_candidates(value=None):
    if value is None:
        return {"schema": SCHEMA, "next_number": 1, "versions": []}
    if not isinstance(value, Mapping) or set(value) != {"schema", "next_number", "versions"}:
        raise ValueError("內門候選版本資料不合法")
    if value["schema"] != SCHEMA:
        raise ValueError("內門候選版本格式不支援")
    number, versions = value["next_number"], value["versions"]
    if type(number) is not int or number < 1 or not isinstance(versions, (list, tuple)):
        raise ValueError("內門版本計數不合法")
    seen = set()
    entries = []
    for row in versions:
        if not isinstance(row, Mapping) or set(row) != {"id", "config"}:
            raise ValueError("內門版本只能包含 id 與 config")
        version_id = row["id"]
        if not isinstance(version_id, str) or not re.fullmatch(r"inner-door-v[1-9][0-9]*", version_id):
            raise ValueError("內門候選版本 ID 不合法")
        if version_id in seen:
            raise ValueError("內門候選版本 ID 重複")
        seen.add(version_id)
        entries.append({"id": version_id, "config": validate_door_config(row["config"])})
    if number <= max((int(v.split("-v")[1]) for v in seen), default=0):
        raise ValueError("內門版本流水號不得復用")
    return {"schema": SCHEMA, "next_number": number, "versions": entries}


def inner_versions(value):
    return deepcopy(normalize_inner_candidates(value)["versions"])


def inner_config(value, version_id):
    for row in inner_versions(value):
        if row["id"] == version_id:
            return row["config"]
    raise ValueError("內門版本不存在")


def create_inner_candidate(value, config):
    result = normalize_inner_candidates(value)
    version_id = f"inner-door-v{result['next_number']}"
    result["next_number"] += 1
    result["versions"].append({"id": version_id, "config": validate_door_config(config)})
    return result, version_id


def update_inner_candidate(value, version_id, config):
    result = normalize_inner_candidates(value)
    for row in result["versions"]:
        if row["id"] == version_id:
            row["config"] = validate_door_config(config)
            return result
    raise ValueError("內門版本不存在")


def delete_inner_candidate(value, version_id):
    result = normalize_inner_candidates(value)
    for pos, row in enumerate(result["versions"]):
        if row["id"] == version_id:
            result["versions"].pop(pos)
            return result
    raise ValueError("內門版本不存在")


def duplicate_inner_candidate(value, version_id):
    return create_inner_candidate(value, inner_config(value, version_id))
