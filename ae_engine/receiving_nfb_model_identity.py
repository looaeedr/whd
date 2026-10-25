# -*- coding: utf-8 -*-
"""Stored switch references: legacy DXF basename or V5 brand/model identity.

Identity only. It conveys neither an approved source profile nor manufacturing
readiness. Prefix disambiguates brand/model even if two brands reuse a name.
"""
from __future__ import annotations

from .receiving_nfb_numeric_catalog import BRANDS, model_choices, model_spec

PREFIX = "nfbv5:"


def parse_numeric_model_ref(value: object) -> tuple[str, str] | None:
    if not isinstance(value, str) or not value.startswith(PREFIX):
        return None
    fields = value[len(PREFIX):].split(":", 1)
    if len(fields) != 2:
        return None
    brand, model = fields
    if (brand not in BRANDS or not model or model != model.strip()
            or ":" in model or any(ch in model for ch in ("/", "\\", "\x00"))):
        return None
    return brand, model


def is_numeric_model_ref(value: object) -> bool:
    return parse_numeric_model_ref(value) is not None


def validate_stored_model_ref(value: object) -> str:
    """Permit a stored V5 identity without depending on today's CSV contents.

    Load/save must retain a once-selected model even if an operator later
    removes it from CSV; fresh catalogue validation occurs before selection
    and release, never by silently reassigning a different model.
    """
    if not isinstance(value, str):
        raise ValueError("NFB 型號識別必須為文字")
    if value.startswith(PREFIX):
        if parse_numeric_model_ref(value) is None:
            raise ValueError("NFB V5 廠牌／型號識別不合法")
        return value
    if (value != value.strip() or len(value) <= 4
            or not value.lower().endswith(".dxf")
            or not value[:-4].strip()
            or any(ch in value for ch in (":", "/", "\\", "\x00"))):
        raise ValueError("NFB 舊型號必須為合法 DXF 檔名")
    return value


def numeric_model_ref(brand: str, model: str) -> str:
    """Generate only currently indexed V5 identities for GUI selection."""
    if (brand not in BRANDS or not isinstance(model, str)
            or not model or model != model.strip()
            or any(ch in model for ch in (":", "/", "\\", "\x00"))):
        raise ValueError("NFB V5 型號不合法")
    if model_spec(brand, model) is None:
        raise ValueError("NFB V5 型號不在選定廠牌 CSV")
    return PREFIX + brand + ":" + model


def numeric_model_refs(brand: str) -> tuple[str, ...]:
    if brand not in BRANDS:
        return ()
    return tuple(PREFIX + brand + ":" + model for model in model_choices(brand))


def display_model_ref(value: str) -> str:
    if isinstance(value, str) and value.startswith(PREFIX):
        parsed = parse_numeric_model_ref(value)
        if parsed is None:
            raise ValueError("NFB V5 廠牌／型號識別不合法")
        return parsed[1]
    from .receiving_switch_model_catalog import display_model
    return display_model(value)



def display_unverified_model_choice(value: str) -> str:
    """Mark a selectable identity as preview-only, never a manufacturing grant.

    The model-picker holds only a (brand, model) identity. It has no actual
    Bay width, inner-door physical part, approved X/Y datum, source SHA,
    collision proof or current manufacturer capability. Therefore a complete
    CSV row or indexed filename cannot truthfully show 可製造（內門） here.
    The original model ref remains unchanged and is stored separately.
    """
    return display_model_ref(value) + "｜僅預覽"


def selected_numeric_spec(brand: str, value: str):
    """Return V5 value only for the matching effective brand; no fallback."""
    parsed = parse_numeric_model_ref(value)
    if parsed is None or parsed[0] != brand:
        return None
    return model_spec(*parsed)
