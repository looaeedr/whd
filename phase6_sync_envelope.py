"""Neutral live-sync envelope helpers for Main GUI <-> Fold Designer.

This module owns transport metadata only.  It does not own mechanical state,
geometry, persistence, or manufacturing rules.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy


def _json_default(value):
    enum_value = getattr(value, "value", None)
    if enum_value is not None:
        return enum_value
    if isinstance(value, set):
        return sorted(value, key=repr)
    return repr(value)


def stable_fingerprint(value) -> str:
    text = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def actual_delta(before, after):
    """Return only semantically changed mapping leaves; lists are atomic."""
    if isinstance(before, Mapping) and isinstance(after, Mapping):
        out = {}
        for key in after:
            if key not in before:
                out[key] = deepcopy(after[key])
                continue
            child = actual_delta(before[key], after[key])
            if child is not _UNCHANGED:
                out[key] = child
        return out if out else _UNCHANGED
    if before == after:
        return _UNCHANGED
    return deepcopy(after)


class _Unchanged:
    pass


_UNCHANGED = _Unchanged()


def mapping_delta(before, after) -> dict:
    delta = actual_delta(before or {}, after or {})
    return {} if delta is _UNCHANGED else dict(delta)
