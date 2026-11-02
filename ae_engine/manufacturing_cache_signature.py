# -*- coding: utf-8 -*-
"""Canonical manufacturing pre-scan signature rules owned by Engine.

A GUI may supply operator state, but it must not decide which fields are
manufacturing inputs or which persisted/UI mirrors can be excluded. The
fingerprint algorithm preserves the historic exact cache key contract.
"""
from __future__ import annotations

from collections.abc import Mapping
from .cabinet_types.policy import canonical_family_name
import hashlib
import json


def canonical_manufacturing_signature_value(value):
    """Preserve legacy cache value equivalence without GUI reverse dependencies."""
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        from math import isfinite

        # An invalid manufacturing dimension may NEVER share a cache key
        # with a literal marker such as "__NaN__", or another invalid value.
        try:
            number = float(value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("nonfinite manufacturing signature value") from exc
        if not isfinite(number):
            raise ValueError("nonfinite manufacturing signature value")
        return round(number, 12)
    if isinstance(value, Mapping):
        return {str(key): canonical_manufacturing_signature_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return tuple(canonical_manufacturing_signature_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        normalized = [canonical_manufacturing_signature_value(item) for item in value]
        return tuple(sorted(normalized, key=repr))
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return canonical_manufacturing_signature_value(enum_value)
    return repr(value)


def manufacturing_state_fingerprint(
    *,
    input_snapshot,
    settings_values,
    working_box,
    corner_state,
    endcap_fw_state,
    endcap_bottom_wrap_state,
    available_parts,
    part_profiles,
    assembly_intent,
    ignore_fixed_corner,
    relief_clearance,
) -> str:
    """Fingerprint effective manufacturing input state, independent of Tk.

    The Receiving live working Bay/Quantity W/H/D overrides Settings defaults.
    Persistence mirrors and UI typography cannot alter authoritative geometry
    cache identity; edits to physical dimensions, Fold, Joint or intent must.
    """
    snapshot = dict(input_snapshot or {})
    settings = dict(settings_values or {})
    working_box = dict(working_box or {})
    settings.pop("ui_text_size", None)
    if canonical_family_name(snapshot) == "受電箱":
        settings.update({
            axis: working_box[axis] for axis in ("w", "h", "d")
            if axis in working_box
        })
    mirror_keys = set(settings) | {
        "settings", "endcap_fw", "endcap_bottom_wrap", "assembly_type",
        "corner_state", "corner_pair_same", "active_part", "part_dimensions",
    }
    snapshot = {key: value for key, value in snapshot.items() if key not in mirror_keys}
    state = (
        snapshot,
        settings,
        working_box,
        dict(corner_state or {}),
        dict(endcap_fw_state or {}),
        dict(endcap_bottom_wrap_state or {}),
        tuple(available_parts or ()),
        dict(part_profiles or {}),
        assembly_intent,
        bool(ignore_fixed_corner),
        relief_clearance,
    )
    normalized = canonical_manufacturing_signature_value(state)
    payload = json.dumps(
        normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
