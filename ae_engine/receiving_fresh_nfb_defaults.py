# -*- coding: utf-8 -*-
"""One CSV-backed NFB default in a fresh editable Receiving Single draft.

This never writes to project/Quantity/Bay, claims manufacturing approval,
overwrites an existing model, or bypasses the real Hole Editor Confirm All.
"""
from __future__ import annotations

from .receiving_nfb_model_identity import numeric_model_ref
from .receiving_nfb_numeric_catalog import model_spec
from .receiving_shared_settings import switch_filenames_in_layer

DEFAULT_BRAND = "士林"
DEFAULT_MODEL = "2P400"


def initial_fresh_receiving_nfb_models(models, *, layer_count, selected_brand):
    """Return two draft model slots, leaving all existing choices unchanged.

    An explicitly selected non-Shihlin global brand is preserved: don't
    silently insert a Shihlin unit under another brand authority.
    """
    if not isinstance(models, (tuple, list)) or len(models) != 2:
        raise ValueError("RECEIVING_FRESH_NFB_DEFAULT_INVALID_LAYERS")
    if (layer_count != 1 or selected_brand != DEFAULT_BRAND
            or any(switch_filenames_in_layer(item) for item in models)):
        return list(models)
    # Resolve through the CURRENT CSV. Never guess missing catalog geometry.
    spec = model_spec(DEFAULT_BRAND, DEFAULT_MODEL)
    if spec is None or not spec.dimensionally_complete:
        return list(models)
    return [numeric_model_ref(DEFAULT_BRAND, DEFAULT_MODEL), ""]
