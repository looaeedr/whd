# -*- coding: utf-8 -*-
"""Project-wide, independent Receiving head/tail Hole Editor candidate versions.

A version is NOT linked to any Set/Bay until Apply copies its feature list.
The QuantityModel for quantity mode remains a separate authority.
"""
from __future__ import annotations
from collections.abc import Mapping
from copy import deepcopy
import re

from .sheetmetal_feature_core import CircleFeature, RectFeature, ProfileFeature


SCHEMA = "receiving-hole-candidates-v1"
ROLES = ("head", "tail")


def role_key(role):
    if role not in ROLES:
        raise ValueError("候選孔位只能是封頭或封尾")
    return role


def version_label(version_id):
    match = re.fullmatch(r"(head|tail|inner-door)-v([1-9][0-9]*)", str(version_id))
    if match is None:
        raise ValueError("候選版本 ID 不合法")
    n = int(match.group(2))
    digits = "零一二三四五六七八九"
    if n < 10:
        suffix = digits[n]
    elif n == 10:
        suffix = "十"
    elif n < 20:
        suffix = "十" + digits[n % 10]
    elif n < 100:
        suffix = digits[n // 10] + "十" + (digits[n % 10] if n % 10 else "")
    else:
        suffix = str(n)
    return "版本" + suffix


def normalize_candidates(value=None):
    if value is None:
        return {"schema": SCHEMA, **{
            role: {"next_number": 1, "versions": []} for role in ROLES
        }}
    if not isinstance(value, Mapping) or set(value) != {"schema", "head", "tail"}:
        raise ValueError("不合法的封頭尾候選庫")
    if value["schema"] != SCHEMA:
        raise ValueError("候選庫格式不支援")
    result = {"schema": SCHEMA}
    for role in ROLES:
        block = value[role]
        if not isinstance(block, Mapping) or set(block) != {"next_number", "versions"}:
            raise ValueError("候選版本欄位不合法")
        number, versions = block["next_number"], block["versions"]
        if type(number) is not int or number < 1 or not isinstance(versions, (tuple, list)):
            raise ValueError("候選版本計數不合法")
        seen, clean = set(), []
        for entry in versions:
            if not isinstance(entry, Mapping) or set(entry) != {"id", "features"}:
                raise ValueError("候選版本只能有 ID 及孔位")
            version_id = entry["id"]
            match = re.fullmatch(rf"{role}-v([1-9][0-9]*)", str(version_id))
            if match is None or version_id in seen:
                raise ValueError("候選版本 ID 重複或不合法")
            if not isinstance(entry["features"], (list, tuple)) or any(
                not isinstance(f, (CircleFeature, RectFeature, ProfileFeature))
                for f in entry["features"]
            ):
                raise ValueError("候選孔位必須為 Feature 清單")
            seen.add(version_id)
            clean.append({"id": version_id, "features": deepcopy(list(entry["features"]))})
        if number <= max((int(x.split("-v")[1]) for x in seen), default=0):
            raise ValueError("候選版本流水號不得復用")
        result[role] = {"next_number": number, "versions": clean}
    return result


def candidates_for(value, role):
    return deepcopy(normalize_candidates(value)[role_key(role)]["versions"])


def candidate_features(value, role, version_id):
    for entry in candidates_for(value, role):
        if entry["id"] == version_id:
            return entry["features"]
    raise ValueError("候選版本不存在")


def create_candidate(value, role, features):
    role = role_key(role)
    if not isinstance(features, (list, tuple)) or any(
        not isinstance(f, (CircleFeature, RectFeature, ProfileFeature))
        for f in features
    ):
        raise ValueError("孔位必須為 Feature 清單")
    result = normalize_candidates(value)
    block = result[role]
    version_id = f"{role}-v{block['next_number']}"
    block["next_number"] += 1
    block["versions"].append({"id": version_id, "features": deepcopy(list(features))})
    return result, version_id


def update_candidate(value, role, version_id, features):
    role = role_key(role)
    if not isinstance(features, (list, tuple)) or any(
        not isinstance(f, (CircleFeature, RectFeature, ProfileFeature))
        for f in features
    ):
        raise ValueError("孔位必須為 Feature 清單")
    result = normalize_candidates(value)
    for item in result[role]["versions"]:
        if item["id"] == version_id:
            item["features"] = deepcopy(list(features))
            return result
    raise ValueError("候選版本不存在")


def delete_candidate(value, role, version_id):
    role = role_key(role)
    result = normalize_candidates(value)
    entries = result[role]["versions"]
    for i, item in enumerate(entries):
        if item["id"] == version_id:
            entries.pop(i)
            return result
    raise ValueError("候選版本不存在")


def duplicate_candidate(value, role, version_id, destination=None):
    return create_candidate(value, role_key(destination or role),
                            candidate_features(value, role, version_id))
