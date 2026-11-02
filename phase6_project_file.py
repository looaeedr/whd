# -*- coding: utf-8 -*-
"""Phase6 all-in-one fold workspace project file support."""
from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
import json
import os
from pathlib import Path
import sys

from ae_engine.sheetmetal_features import (
    CircleFeature, RectFeature, ProfileFeature, FeatureAnchor,
)
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine import manufacturing_api

PROJECT_SCHEMA_V1 = manufacturing_api.PROJECT_SCHEMA_V1
PROJECT_SCHEMA_V2 = manufacturing_api.PROJECT_SCHEMA_V2
PROJECT_SCHEMA_V3 = manufacturing_api.PROJECT_SCHEMA_V3
# Existing generic callers still construct v1 payloads. Receiving projects are
# promoted to v2 by write_project once ReceivingLayout is present.
PROJECT_SCHEMA = PROJECT_SCHEMA_V1
PROJECT_EXTENSION = ".p6fold"
PROJECT_CLASS = "Phase6.FoldProject"

def _normalize_authoritative_door_state(snapshot):
    """Compatibility adapter: Engine owns saved physical Door authority."""
    return manufacturing_api.normalize_authoritative_door_state(snapshot)


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


def validate_project(payload, *, for_read=False):
    """Compatibility port: Engine owns the saved project schema decision."""
    return manufacturing_api.validate_operator_project_payload(
        payload, for_read=for_read,
    )


def _materialize_project_snapshot(snapshot):
    """Compatibility adapter: Engine owns saved source normalization."""
    return manufacturing_api.normalize_project_snapshot_authority(snapshot)


def write_project(path, payload):
    materialized = manufacturing_api.project_operator_project_for_write(payload)
    target = Path(path)
    if target.suffix.lower() != PROJECT_EXTENSION:
        target = target.with_suffix(PROJECT_EXTENSION)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(_encode(materialized), ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def read_project(path):
    source = Path(path)
    raw = json.loads(source.read_text(encoding="utf-8"))
    return manufacturing_api.project_operator_project_for_read(_decode(raw))


def project_path_from_argv(argv):
    for raw in argv or ():
        try:
            path = Path(raw)
        except TypeError:
            continue
        if path.suffix.lower() == PROJECT_EXTENSION and path.is_file():
            return path
    return None


def windows_open_command(executable=None, *, script_path=None, frozen=None):
    executable = str(executable or sys.executable)
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        return f'"{executable}" "%1"'
    script = str(script_path or Path(__file__).with_name("gui.py"))
    return f'"{executable}" "{script}" "%1"'


def register_windows_file_association(*, executable=None, script_path=None, frozen=None):
    """Register .p6fold per-user; no administrator privilege is required."""
    if os.name != "nt":
        return False
    import winreg

    command = windows_open_command(executable, script_path=script_path, frozen=frozen)
    base = r"Software\Classes"
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + r"\.p6fold") as key:
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, PROJECT_CLASS)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + rf"\{PROJECT_CLASS}") as key:
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, "Phase6 折彎專案")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, base + rf"\{PROJECT_CLASS}\shell\open\command") as key:
        winreg.SetValueEx(key, None, 0, winreg.REG_SZ, command)
    return True
