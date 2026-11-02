# -*- coding: utf-8 -*-
"""Headless cabinet-model catalog shared by the WHD entry points (#2517).

The model selector must not duplicate family identity and baseline availability
rules in Tk callers. Listing a model is not permission to manufacture/export it.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from . import ae
from .cabinet_types import registered_cabinet_types
from .corner_type_ui import (
    is_unknown_model,
    normalize_custom_model_name,
    with_unknown_model,
)
from .sheetmetal_geometry import EDITABLE_CORNER_TYPE_IDS, CORNER_TYPE_LABELS


def list_cabinet_model_choices(
    available_baselines: Iterable[object] | None = None,
) -> list[str]:
    """Return the same visible model choices for main GUI and Fold Designer.

    Physical baseline folders are authoritative for resource-backed models,
    while implemented formula-only families need no baseline directory.
    Unknown/legacy custom aliases collapse into one final 自訂 option.
    An optional baseline input permits headless deterministic contract tests.
    """
    sources = ae.get_baseline_list() if available_baselines is None else available_baselines
    choices: list[str] = []
    seen: set[str] = set()
    for raw in sources:
        name = normalize_custom_model_name(raw)
        if name and name not in seen and not is_unknown_model(name):
            choices.append(name)
            seen.add(name)

    for registration in registered_cabinet_types():
        if not registration.implemented:
            continue
        name = str(registration.canonical_name or "").strip()
        # Vault cannot be offered as an empty formula fallback. Receiving can.
        if name == "金庫型" and name not in seen:
            continue
        if name and name not in seen:
            choices.append(name)
            seen.add(name)

    return with_unknown_model(choices)



@dataclass(frozen=True)
class OperatorCornerSelectionCatalog:
    """Immutable Engine source for the Fold Designer's model/corner controls."""

    editable: bool
    labels: tuple[tuple[str, str], ...]
    custom_model_name: str


def project_operator_corner_selection_catalog(
    model: object, baseline_models: Iterable[object],
) -> OperatorCornerSelectionCatalog:
    """Project the existing custom-model and corner-type policy without Tk.

    An old saved custom model label remains displayable even when it is the
    legacy alias; the caller may not infer a new manufacturing Family from it.
    """
    models = tuple(baseline_models or ())
    return OperatorCornerSelectionCatalog(
        editable=is_unknown_model(model),
        labels=tuple(
            (type_id.value, CORNER_TYPE_LABELS[type_id])
            for type_id in EDITABLE_CORNER_TYPE_IDS
        ),
        custom_model_name=next(
            (name for name in models if is_unknown_model(name)), "自訂"
        ),
    )
