# -*- coding: utf-8 -*-
"""Receiving inner-door operator inventory projection (never NFB hole geometry).

Read-only representation of the already persisted 1/2-layer model references.
Use the same canonical stored-model validation and V5 identity display owner
as candidate Apply / Save->Reload. No physical X/Y or DXF source is inferred.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .receiving_nfb_model_identity import display_model_ref
from .receiving_shared_settings import switch_filenames_in_layer


@dataclass(frozen=True)
class ReceivingInnerDoorInventoryLayer:
    """Ordered physical occurrences and identity-preserving display counts."""

    model_refs: tuple[str, ...]
    display_counts: tuple[tuple[str, int], ...]


def resolve_receiving_inner_door_preview_inventory(
    config: dict | None,
) -> tuple[ReceivingInnerDoorInventoryLayer, ...]:
    """Project a candidate/Set/Bay snapshot for a display-only inner-door tile.

    Duplicate switch occurrences are not discarded. Group by *stored identity*
    before obtaining a label: distinct V5 brands cannot be falsely combined
    just because their models share a human-readable name.
    """
    if config is None:
        return ()
    if not isinstance(config, dict) or config.get("layers") not in (1, 2):
        raise ValueError("無效的內門預覽層數")
    models = config.get("models")
    if not isinstance(models, (tuple, list)) or len(models) != 2:
        raise ValueError("內門預覽必須有兩層開關欄位")
    layers = []
    for index in range(config["layers"]):
        model_refs = tuple(switch_filenames_in_layer(models[index]))
        counts = Counter(model_refs)
        labels = tuple(
            (display_model_ref(model_ref), quantity)
            for model_ref, quantity in counts.items()
        )
        layers.append(ReceivingInnerDoorInventoryLayer(model_refs, labels))
    return tuple(layers)
