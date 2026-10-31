# -*- coding: utf-8 -*-
"""Engine-only thawing of frozen JSON-safe manufacturing request data."""
from __future__ import annotations
from collections.abc import Mapping
from dataclasses import fields, is_dataclass

def thaw_manufacturing_value(value):
    """Create detached JSON-safe data without reverse Phase6/GUI imports."""
    if isinstance(value, Mapping):
        return {str(k): thaw_manufacturing_value(v) for k, v in value.items()}
    if isinstance(value, tuple):
        return [thaw_manufacturing_value(v) for v in value]
    if value is None or isinstance(value, (bool, str, int, float)):
        return value
    if is_dataclass(value):
        return thaw_manufacturing_value({
            "__dataclass_type__": f"{type(value).__module__}.{type(value).__qualname__}",
            **{f.name: getattr(value, f.name) for f in fields(value)},
        })
    raise TypeError("WHD_MANUFACTURING_REQUEST_NOT_JSON_SAFE")
