# -*- coding: utf-8 -*-
"""Narrow cabinet-family capability facade.

Callers ask for domain capabilities; family modules own only their confirmed
mechanical differences.  This facade does not own UI state, project sessions,
rendering, manufacturing geometry, or Certified Registry answers.
"""
from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from typing import Mapping

from .registry import resolve_cabinet_type


def _raw_family_name(source) -> str:
    if isinstance(source, Mapping):
        data = dict(source or {})
        value = data.get("model") or data.get("cabinet_type") or ""
    else:
        value = source or ""
    return str(value).strip()


def canonical_family_name(source) -> str:
    raw = _raw_family_name(source)
    if not raw:
        return ""
    try:
        return resolve_cabinet_type(raw).canonical_name
    except KeyError:
        return raw


def _family_module(source):
    name = canonical_family_name(source)
    if not name:
        return None
    try:
        registration = resolve_cabinet_type(name)
    except KeyError:
        return None
    if not registration.implemented:
        return None
    return import_module(registration.module_name)


def _call(source, name: str, default, *args, **kwargs):
    module = _family_module(source)
    callback = getattr(module, name, None) if module is not None else None
    if not callable(callback):
        return default
    return callback(*args, **kwargs)


def apply_fresh_family_defaults(snapshot, model_name) -> dict:
    source = deepcopy(dict(snapshot or {}))
    canonical = canonical_family_name(model_name) or str(model_name or "").strip()
    module = _family_module(canonical)
    callback = getattr(module, "apply_family_defaults", None) if module is not None else None
    if callable(callback):
        return callback(source)
    source.pop("cabinet_type", None)
    if canonical:
        source["model"] = canonical
    return source


def fresh_assembly_intent(source, default="INSERT_OVERLAY") -> str:
    module = _family_module(source)
    value = getattr(module, "FRESH_ASSEMBLY_INTENT", default) if module is not None else default
    return str(value)


def has_inner_door_frame_derivation(source) -> bool:
    module = _family_module(source)
    return callable(getattr(module, "derive_inner_door_frame_sets", None)) if module is not None else False


def derive_inner_door_frame_sets(snapshot) -> tuple[object, ...]:
    result = _call(snapshot, "derive_inner_door_frame_sets", (), snapshot)
    return tuple(result or ())


def baseline_feature_model_name(model_name: str | None) -> str | None:
    canonical = canonical_family_name(model_name)
    if not canonical:
        return None
    return str(_call(canonical, "shared_baseline_feature_model_name", canonical))


def door_nameplate_center_datum_top(model_name: str | None) -> float | None:
    module = _family_module(model_name)
    if module is None:
        return None
    value = getattr(module, "DOOR_NAMEPLATE_CENTER_DATUM_TOP", None)
    return None if value is None else float(value)


def endcap_depth_comp_t(source) -> float:
    return float(_call(source, "endcap_depth_comp_t", 3.0))


def resolve_box_body_structure_state(source, state=None) -> dict:
    module = _family_module(source)
    callback = getattr(module, "resolve_box_body_structure_state", None) if module is not None else None
    if callable(callback):
        return callback(state)
    from phase6_box_body_structure import normalize_box_body_structure_state
    return normalize_box_body_structure_state(state)


def box_body_structure_is_fixed(source) -> bool:
    try:
        return bool(resolve_box_body_structure_state(source, None).get("locked", False))
    except Exception:
        return False


def family_fixes_box_body_structure(source) -> bool:
    return bool(_call(source, "family_fixes_box_body_structure", False))


def transform_box_body_profile(source, profile):
    module = _family_module(source)
    callback = getattr(module, "transform_box_body_profile", None) if module is not None else None
    if callable(callback):
        return callback(profile)
    return [dict(row) for row in (profile or ())]


def box_body_profile_uses_outside_dimensions(source) -> bool:
    return bool(_call(source, "box_body_profile_uses_outside_dimensions", False))


def endcap_fw_profile_uses_material_dimensions(source) -> bool:
    return bool(_call(source, "endcap_fw_profile_uses_material_dimensions", False))


def supports_bottom_wrap_controls(source) -> bool:
    return bool(_call(source, "supports_bottom_wrap_controls", False))


def default_bottom_wrap_enabled(source) -> bool:
    return bool(_call(source, "default_bottom_wrap_enabled", False))


def set_bottom_relief_reserves(source, state, *, reserve_u=None, reserve_v=None) -> dict:
    module = _family_module(source)
    callback = getattr(module, "set_bottom_relief_reserves", None) if module is not None else None
    if callable(callback):
        return callback(state, reserve_u=reserve_u, reserve_v=reserve_v)
    return resolve_box_body_structure_state(source, state)


def bottom_relief_reserves(source, state=None) -> tuple[float, float]:
    result = _call(source, "bottom_relief_reserves", (0.0, 0.0), state)
    return float(result[0]), float(result[1])


def effective_endcap_bottom_fw(source, state, *, thickness: float, default_fw: float) -> float:
    module = _family_module(source)
    callback = getattr(module, "bottom_effective_fw", None) if module is not None else None
    if not callable(callback):
        return float(default_fw)
    structure = resolve_box_body_structure_state(source, state)
    from phase6_box_body_structure import BoxBodyStructureType
    cfg = structure["configs"].get(BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value, {})
    rear = float(cfg.get("side_rear_bend", 15.0))
    return float(callback(side_rear_bend=rear, thickness=float(thickness)))


def bottom_relief_registry_applicable(source, state=None) -> bool:
    return bool(_call(source, "bottom_relief_registry_applicable", False, state))


def endcap_bottom_selection(source):
    return _call(source, "endcap_bottom_selection", None)


def endcap_corner_policy(source, *, frame_width: float, thickness: float, state=None):
    module = _family_module(source)
    callback = getattr(module, "endcap_corner_policy", None) if module is not None else None
    if not callable(callback):
        return None
    structure = resolve_box_body_structure_state(source, state)
    from phase6_box_body_structure import BoxBodyStructureType
    cfg = structure["configs"].get(BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value, {})
    return callback(
        frame_width=float(frame_width),
        thickness=float(thickness),
        side_rear_bend=float(cfg.get("side_rear_bend", 15.0)),
    )
