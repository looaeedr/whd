# -*- coding: utf-8 -*-
"""Headless operator Family identity resolution shared by GUI and manufacturing."""
from __future__ import annotations

from .cabinet_types.registry import resolve_cabinet_type


def resolve_live_cabinet_family(input_snapshot, live_model=None) -> str:
    """Preserve live selector precedence and legacy Family=ANY/empty fallback.

    This only resolves operator identity. It never creates geometry, decides
    physical part topology, or grants manufacturing/Registry certification.
    """
    snapshot = dict(input_snapshot or {})
    model = str(snapshot.get("model") or snapshot.get("cabinet_type") or "").strip()
    current = str(live_model or "").strip()
    if current:
        model = current
    try:
        return resolve_cabinet_type(model).canonical_name
    except Exception:
        # Keep the established unknown/custom Family=ANY and blank Vault route.
        return model or "金庫型"
