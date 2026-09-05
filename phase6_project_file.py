# -*- coding: utf-8 -*-
"""Phase6 all-in-one fold workspace project file support."""
from __future__ import annotations

from copy import deepcopy
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

PROJECT_SCHEMA = "phase6-fold-project-v1"
PROJECT_EXTENSION = ".p6fold"
PROJECT_CLASS = "Phase6.FoldProject"

_TRANSIENT_DERIVED_SNAPSHOT_KEYS = (
    "divider_parts",
    "inner_door_frame_parts",
)


def _normalize_authoritative_door_state(snapshot):
    """Materialize/repair T10 Door authority without persisting derived geometry.

    Door layout, per-cell handle edge, inner-door config and the optional
    nameplate datum are project authority. Divider/frame geometry remains
    derived state and is intentionally omitted. Shared lower-frame references
    are resolved only *after* divider stable IDs have been regenerated from the
    saved topology, so a stale child reference cannot leak into 3D/DXF.
    """
    result = deepcopy(dict(snapshot or {}))
    for key in _TRANSIENT_DERIVED_SNAPSHOT_KEYS:
        result.pop(key, None)

    model = str(result.get("model") or "").strip()
    if model == "受電箱" and result.get("door_nameplate_center_datum_top") is None:
        from ae_engine.cabinet_types.receiving import DOOR_NAMEPLATE_CENTER_DATUM_TOP
        result["door_nameplate_center_datum_top"] = float(DOOR_NAMEPLATE_CENTER_DATUM_TOP)
    elif result.get("door_nameplate_center_datum_top") is not None:
        result["door_nameplate_center_datum_top"] = float(result["door_nameplate_center_datum_top"])

    raw_columns = list(result.get("door_layout_columns") or ())
    columns = []
    for row in raw_columns:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            raise ValueError(f"invalid door layout column: {row!r}")
        columns.append([float(row[0]), [float(v) for v in row[1]]])
    if "door_layout_columns" in result or columns:
        result["door_layout_columns"] = columns

    handle_aliases = {"左": "LEFT", "右": "RIGHT", "上": "TOP", "下": "BOTTOM"}
    handles = {}
    for raw_key, raw_value in dict(result.get("door_handle_edges") or {}).items():
        value = str(raw_value).strip().upper()
        value = handle_aliases.get(value, value)
        if value not in {"LEFT", "RIGHT", "TOP", "BOTTOM"}:
            raise ValueError(f"unsupported door handle edge: {raw_value!r}")
        handles[str(raw_key)] = value
    if columns:
        from ae_engine.sheetmetal_part_adapters import derive_door_layout_cells
        valid_cells = {
            f"{cell.column_index}:{cell.row_index}"
            for cell in derive_door_layout_cells(tuple((w, tuple(hs)) for w, hs in columns))
        }
        handles = {key: value for key, value in handles.items() if key in valid_cells}
    elif handles:
        handles = {}
    if "door_handle_edges" in result or handles:
        result["door_handle_edges"] = handles

    inner_doors = deepcopy(list(result.get("inner_doors") or ()))
    for item in inner_doors:
        if isinstance(item, dict):
            # Receiving frame spans / finished dimensions are deterministic
            # derivatives of Door topology + family policy, never project truth.
            item.pop("frame_spans", None)
            item.pop("inner_door_finished_size", None)
    if inner_doors:
        if not columns or not bool(result.get("multi_door_enabled", False)):
            for item in inner_doors:
                if isinstance(item, dict):
                    item.pop("lower_frame_role", None)
        else:
            from ae_engine.door_dividers import derive_box_body_dividers, resolve_inner_door_lower_frame_role

            try:
                depth = float(result["d"])
                thickness = float(result["t"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError("inner-door shared role requires saved d/t authority") from exc
            scope = str(result.get("door_layout_scope") or "main").strip() or "main"
            dividers = derive_box_body_dividers(
                tuple((w, tuple(hs)) for w, hs in columns),
                depth=depth,
                thickness=thickness,
                layout_scope=scope,
                handle_edges=handles,
            )
            for item in inner_doors:
                if not isinstance(item, dict):
                    continue
                door_id = str(item.get("stable_id") or "").strip()
                if not door_id:
                    item.pop("lower_frame_role", None)
                    continue
                previous = dict(item.get("lower_frame_role") or {}).get("divider_stable_id")
                role = resolve_inner_door_lower_frame_role(
                    door_id,
                    dividers,
                    previous_divider_stable_id=(str(previous) if previous else None),
                )
                if role is None:
                    item.pop("lower_frame_role", None)
                else:
                    item["lower_frame_role"] = {
                        "role": role.role,
                        "divider_stable_id": role.divider_stable_id,
                    }
        result["inner_doors"] = inner_doors
    return result


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


def validate_project(payload):
    if not isinstance(payload, dict):
        raise ValueError("Phase6 專案必須是 JSON 物件")
    if payload.get("schema") != PROJECT_SCHEMA:
        raise ValueError(f"不支援的 Phase6 專案格式：{payload.get('schema')!r}")
    if not isinstance(payload.get("snapshot"), dict):
        raise ValueError("Phase6 專案缺少 snapshot")
    return payload


def write_project(path, payload):
    validate_project(payload)
    # Persist the versioned AssemblyJoint graph even when an older caller still
    # supplies only assembly_type.  Existing USER_ADDED joints are preserved
    # because migration is idempotent for versioned snapshots.
    from ae_engine.assembly_joint import migrate_legacy_snapshot_joints
    materialized = dict(payload)
    materialized["snapshot"] = _normalize_authoritative_door_state(
        migrate_legacy_snapshot_joints(dict(payload.get("snapshot") or {}))
    )
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
    validate_project(decoded)
    # Legacy .p6fold files only stored one high-level assembly_type.  Migrate
    # that state to a versioned AssemblyJoint graph on read; migration never
    # invents WRAP and is idempotent for already-versioned projects.
    from ae_engine.assembly_joint import migrate_legacy_snapshot_joints
    decoded["snapshot"] = _normalize_authoritative_door_state(
        migrate_legacy_snapshot_joints(decoded["snapshot"])
    )
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
