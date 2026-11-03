# -*- coding: utf-8 -*-
"""Engine-owned persisted Phase6 Feature/Vec2 JSON compatibility codec.

This is a move-only transfer of the existing .p6fold wire representation.
The GUI remains the filesystem and file-dialog client; it never resolves
physical Hole/Feature types or manufacturing source from serialized JSON.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum

from .sheetmetal_features import (
    CircleFeature, RectFeature, ProfileFeature, FeatureAnchor,
)
from .sheetmetal_geometry import Vec2


def _encode(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Vec2):
        return {"__phase6_type__": "Vec2", "x": float(value.x), "y": float(value.y)}
    if isinstance(value, (CircleFeature, RectFeature, ProfileFeature)):
        row = {"__phase6_type__": type(value).__name__}
        for field in fields(value):
            row[field.name] = _encode(getattr(value, field.name))
        return row
    if is_dataclass(value):
        return {field.name: _encode(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(k): _encode(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_encode(v) for v in value]
    return repr(value)


def _as_vec2(value):
    if isinstance(value, Vec2):
        return value
    if isinstance(value, dict):
        return Vec2(float(value.get("x", 0.0)), float(value.get("y", 0.0)))
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return Vec2(float(value[0]), float(value[1]))
    raise ValueError(f"invalid Vec2 value: {value!r}")


def _decode_feature(type_name, row):
    data = {k: _decode(v) for k, v in row.items() if k != "__phase6_type__"}
    data["anchor"] = FeatureAnchor(data.get("anchor", FeatureAnchor.PANEL_CENTER.value))
    data["offset"] = _as_vec2(data.get("offset", {"x": 0.0, "y": 0.0}))
    data["source_params"] = tuple(tuple(v) for v in data.get("source_params", ()) or ())
    if type_name == "CircleFeature":
        return CircleFeature(**data)
    if type_name == "RectFeature":
        return RectFeature(**data)
    if type_name == "ProfileFeature":
        data["points"] = tuple(_as_vec2(v) for v in data.get("points", ()) or ())
        layered = []
        for item in data.get("layered_profiles", ()) or ():
            layer, points, closed = item
            layered.append((str(layer), tuple(_as_vec2(v) for v in points), bool(closed)))
        data["layered_profiles"] = tuple(layered)
        return ProfileFeature(**data)
    raise ValueError(f"unsupported feature type: {type_name}")


def _decode(value):
    if isinstance(value, list):
        return [_decode(v) for v in value]
    if not isinstance(value, dict):
        return value
    type_name = value.get("__phase6_type__")
    if type_name == "Vec2":
        return Vec2(float(value["x"]), float(value["y"]))
    if type_name in {"CircleFeature", "RectFeature", "ProfileFeature"}:
        return _decode_feature(type_name, value)
    return {str(k): _decode(v) for k, v in value.items()}


