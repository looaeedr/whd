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

PROJECT_SCHEMA_V1 = "phase6-fold-project-v1"
PROJECT_SCHEMA_V2 = "phase6-fold-project-v2"
PROJECT_SCHEMA_V3 = "phase6-fold-project-v3"
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
    if not isinstance(payload, dict):
        raise ValueError("Phase6 專案必須是 JSON 物件")
    schema = payload.get("schema")
    if schema not in {PROJECT_SCHEMA_V1, PROJECT_SCHEMA_V2, PROJECT_SCHEMA_V3}:
        raise ValueError(f"不支援的 Phase6 專案格式：{schema!r}")
    if not isinstance(payload.get("snapshot"), dict):
        raise ValueError("Phase6 專案缺少 snapshot")
    if schema in {PROJECT_SCHEMA_V2, PROJECT_SCHEMA_V3}:
        from ae_engine.cabinet_types.receiving import is_receiving_snapshot
        if not is_receiving_snapshot(payload["snapshot"]):
            raise ValueError("Receiving project v2/v3 requires Receiving family")
    if for_read:
        from ae_engine.receiving_nfb_persistence import contains_submitted_nfb
        submitted = contains_submitted_nfb(payload["snapshot"])
        if submitted and schema != PROJECT_SCHEMA_V3:
            raise ValueError("submitted NFB project cannot be loaded through an old schema")
        if schema == PROJECT_SCHEMA_V3 and not submitted:
            raise ValueError("NFB project v3 has no committed NFBConfig")
    return payload


def _materialize_project_snapshot(snapshot):
    """Engine owns source normalization for both Save and Reload."""
    return manufacturing_api.normalize_project_snapshot_authority(snapshot)


def write_project(path, payload):
    validate_project(payload)
    from ae_engine.cabinet_types.receiving import is_receiving_snapshot
    from ae_engine.receiving_layout import strip_legacy_receiving_aliases

    materialized = dict(payload)
    snapshot = _materialize_project_snapshot(payload.get("snapshot") or {})
    if is_receiving_snapshot(snapshot):
        from ae_engine.receiving_nfb_persistence import contains_submitted_nfb
        materialized["schema"] = (PROJECT_SCHEMA_V3 if contains_submitted_nfb(snapshot)
                                  else PROJECT_SCHEMA_V2)
        snapshot = strip_legacy_receiving_aliases(snapshot)
    elif materialized.get("schema") in {PROJECT_SCHEMA_V2, PROJECT_SCHEMA_V3}:
        raise ValueError("Receiving project v2/v3 requires Receiving family")
    else:
        materialized["schema"] = PROJECT_SCHEMA_V1
    materialized["snapshot"] = manufacturing_api.normalize_quantity_snapshot(snapshot, for_save=True)
    # Final geometry is a derived diagnostic/render cache, never project truth.
    # Persist only authoritative state; Reload must deterministically re-solve it.
    materialized["final_geometry"] = {}
    target = Path(path)
    if target.suffix.lower() != PROJECT_EXTENSION:
        target = target.with_suffix(PROJECT_EXTENSION)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(_encode(materialized), ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def read_project(path):
    source = Path(path)
    raw = json.loads(source.read_text(encoding="utf-8"))
    decoded = _decode(raw)
    validate_project(decoded, for_read=True)
    from ae_engine.cabinet_types.receiving import is_receiving_snapshot
    from ae_engine.receiving_layout import project_primary_bay_legacy_aliases

    decoded["snapshot"] = _materialize_project_snapshot(decoded["snapshot"])
    if is_receiving_snapshot(decoded["snapshot"]):
        # In-memory compatibility projection only.  Re-saving strips aliases
        # again, so v2 never gains a second persisted W/H/D or panel-mode owner.
        from ae_engine.receiving_nfb_persistence import contains_submitted_nfb
        decoded["schema"] = (PROJECT_SCHEMA_V3 if contains_submitted_nfb(decoded["snapshot"])
                             else PROJECT_SCHEMA_V2)
        decoded["snapshot"] = project_primary_bay_legacy_aliases(decoded["snapshot"])
    # Ignore legacy files that persisted derived geometry/probe evidence.
    decoded["final_geometry"] = {}
    return decoded


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
