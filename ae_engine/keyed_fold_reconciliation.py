# -*- coding: utf-8 -*-
"""Engine-owned keyed Fold profile reconciliation for Settings updates.

Only the immutable source outside dimensions and current canonical Fold topology
may supply fresh material lengths, outside compensation and core metadata.
Operator-inserted unrelated folds retain their original order and attributes.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Mapping


def _clone_profile(profile):
    """Return a fully detached legacy Fold row list (including nested metadata)."""
    return deepcopy(list(profile))


def merge_keyed_fold_profiles(existing_profiles, default_profiles):
    """Refresh keyed segments while preserving arbitrary operator-added folds."""
    result = {}
    for axis in ("X", "Y"):
        existing = _clone_profile((existing_profiles or {}).get(axis, ()))
        defaults = _clone_profile((default_profiles or {}).get(axis, ()))
        if not existing:
            result[axis] = defaults
            continue
        default_by_key = {
            seg.get("phase6_key"): seg
            for seg in defaults
            if seg.get("phase6_key")
        }
        existing_keys = {
            seg.get("phase6_key")
            for seg in existing
            if seg.get("phase6_key")
        }
        if not set(default_by_key).issubset(existing_keys):
            result[axis] = defaults
            continue
        for seg in existing:
            key = seg.get("phase6_key")
            source = default_by_key.get(key)
            if source is None:
                continue
            for name in ("len", "ui_len_add", "core"):
                if name in source:
                    seg[name] = source[name]
                else:
                    seg.pop(name, None)
        result[axis] = existing
    return result


