# -*- coding: utf-8 -*-
"""Headless operator Family identity resolution shared by GUI and manufacturing."""
from __future__ import annotations

from collections.abc import Mapping

from .cabinet_types.registry import resolve_cabinet_type


def resolve_operator_manufacturing_family_source(
    input_snapshot, *, live_model=None, initial_model=None,
) -> str:
    """Select the original raw operator Family before canonical manufacturing.

    Live nonblank selection wins; otherwise the saved project's model or
    cabinet_type wins; only a source-free new project uses initial_model.
    Alias normalization and manufacturing eligibility remain the responsibility
    of resolve_live_cabinet_family and the canonical Family registry.
    """
    snapshot = dict(input_snapshot or {})
    live = str(live_model or "").strip()
    if live:
        return live
    return str(
        snapshot.get("model") or snapshot.get("cabinet_type")
        or initial_model or ""
    ).strip()


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


def operator_resolve_legacy_baseline_manufacturing_family(source_model) -> str:
    """Project the existing legacy GUI baseline onto a registered Engine Family.

    This preserves the historical main-GUI fallback to the Vault family for
    unregistered baseline folders/Custom; it does not certify an unknown
    model or bypass manufacturing Family eligibility checks.
    """
    from .corner_type_ui import normalize_custom_model_name

    value = normalize_custom_model_name(source_model)
    try:
        return resolve_cabinet_type(value).canonical_name
    except (KeyError, ValueError):
        return "金庫型"


def require_selected_export_matching_operator_family(snapshot, operator_source):
    """Qualify the captured live Family against authoritative project input.

    A successful check asserts only initial Family consistency, not selection
    of topology, eligibility, or freshness after the operator opens a dialog.
    """
    if not isinstance(snapshot, Mapping) or not isinstance(operator_source, Mapping):
        return
    model_selection = operator_source.get("model_selection")
    if (not isinstance(model_selection, Mapping)
            or model_selection.get("reader_present") is not True):
        return  # Legacy/headless callers have no live model selector.
    saved_model = resolve_operator_manufacturing_family_source(snapshot)
    if not saved_model:
        return  # A source-free legacy project still uses the existing Engine gate.
    live_model = model_selection.get("value")
    if (not isinstance(live_model, str) or not live_model.strip()
            or operator_resolve_legacy_baseline_manufacturing_family(
                live_model
            ) != operator_resolve_legacy_baseline_manufacturing_family(
                saved_model
            )):
        raise ValueError("DXF 即時箱型與製造快照不一致，請先同步並重新確認箱型")
