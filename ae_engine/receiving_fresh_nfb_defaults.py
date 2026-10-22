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


def seed_fresh_receiving_nfb_source(snapshot):
    """Initialize ONE genuine current-CSV NFB on a *fresh* Set1/Bay1.

    The caller must own a newly created Receiving Family/mode; this is NOT a
    load-time migration. The Bay's committed NFBConfig is the only persistence
    owner. Main inner-door CUTTING comes from the same native Hole Editor
    feature generator used for subsequent edits, while BasePlate/EAR/MARKING
    remain derived by the existing manufacturing resolver.

    Never manufacture a source if CSV is missing/incomplete or a Bay is
    already configured. Do not invent an X certification or MFG readiness.
    """
    from copy import deepcopy
    from .cabinet_types import policy as cabinet_policy
    from .receiving_layout import (
        ensure_receiving_layout, project_receiving_bay_legacy_aliases,
        update_receiving_bay,
    )
    from .receiving_shared_settings import SETTING_DEFAULTS, edit_setting
    from .receiving_nfb_csv_editor_features import editor_nfb_features_from_csv
    from .receiving_nfb_csv_committed_config import committed_csv_nfb_config

    value = deepcopy(dict(snapshot or {}))
    if value.get("model") not in ("受電箱", "RECEIVING"):
        return value
    if value.get("active_mode", "set_bay") != "set_bay":
        raise ValueError("RECEIVING_FRESH_NFB_EXPECTS_SET_BAY")
    value = ensure_receiving_layout(value)
    layout = value["receiving_layout"]
    if len(layout["sets"]) != 1 or len(layout["sets"][0]["bays"]) != 1:
        return value
    set_row, bay = layout["sets"][0], layout["sets"][0]["bays"][0]
    if bay.get("nfb_config_submitted") is True:
        # Never reseed an operator-edited Bay. Refresh runtime aliases from
        # its real saved owner instead of returning a stale root projection.
        return project_receiving_bay_legacy_aliases(
            value, set_index=0, bay_index=0, validate_common=False,
        )
    # This is an explicit first-switch initializer, not an automatic repair
    # for an intentionally unconfigured or saved project.
    brand = str(set_row.get("switch_brand") or DEFAULT_BRAND)
    if brand != DEFAULT_BRAND:
        return value
    spec = model_spec(DEFAULT_BRAND, DEFAULT_MODEL)
    if spec is None or not spec.dimensionally_complete:
        raise ValueError("RECEIVING_DEFAULT_NFB_CURRENT_CSV_INCOMPLETE")
    model = numeric_model_ref(DEFAULT_BRAND, DEFAULT_MODEL)
    heights = list(SETTING_DEFAULTS["inner_door_layer_heights_mm"])
    config = {"layers": 1, "models": [model, ""],
              "layer_heights_mm": heights}
    layout = edit_setting(layout, set_index=0, bay_index=0,
                          kind="inner_door_layers", value=1)
    layout = edit_setting(layout, set_index=0, bay_index=0,
                          kind="inner_door_models", value=[model, ""])
    layout = edit_setting(layout, set_index=0, bay_index=0,
                          kind="inner_door_layer_heights_mm", value=heights)
    value["receiving_layout"] = layout
    candidate = project_receiving_bay_legacy_aliases(
        value, set_index=0, bay_index=0, validate_common=False,
    )
    panels = [p for p in cabinet_policy.derive_inner_door_panels(candidate)
              if str(p.cell_key) == "0:0"]
    if len(panels) != 1:
        raise ValueError("RECEIVING_DEFAULT_NFB_UPPER_PANEL_NOT_UNIQUE")
    panel = panels[0]
    features = editor_nfb_features_from_csv(candidate, config)
    if len(features) != 1:
        raise ValueError("RECEIVING_DEFAULT_NFB_CSV_OPENING_NOT_UNIQUE")
    saved = committed_csv_nfb_config(panel.stable_id, features, config)
    layout = edit_setting(layout, set_index=0, bay_index=0,
                          kind="inner_door_features",
                          value={panel.stable_id: list(features)})
    layout = update_receiving_bay(
        layout, set_index=0, bay_index=0,
        nfb_config_submitted=True, nfb_config=saved,
    )
    value["receiving_layout"] = layout
    # Keep the source-owned Bay and its UI aliases consistent. The opening is
    # already in inner_door_features; the base and both EARs are NOT stored.
    return project_receiving_bay_legacy_aliases(
        value, set_index=0, bay_index=0, validate_common=True,
    )


def seed_fresh_receiving_quantity_nfb_source(snapshot):
    """Source-owned first NFB for a newly initialized Quantity version.

    QuantityModel owns submission, the common box owns model/height, and
    part_features owns real native inner-door CUTTING. The synthetic one-Bay
    is NEVER written independently as another NFB authority.
    """
    from copy import deepcopy
    from .cabinet_types import policy as cabinet_policy
    from .receiving_nfb_csv_editor_features import editor_nfb_features_from_csv
    from .receiving_nfb_csv_committed_config import committed_csv_nfb_config
    from .receiving_quantity_box import BOX_KEY, project_common_box
    from .receiving_shared_settings import SETTING_DEFAULTS
    from phase6_quantity_model import QuantityModel

    value = deepcopy(dict(snapshot or {}))
    if (value.get("model") not in ("受電箱", "RECEIVING")
            or value.get("active_mode") != "quantity"):
        return value
    box = dict(value.get(BOX_KEY) or {})
    if box.get("switch_brand", DEFAULT_BRAND) != DEFAULT_BRAND:
        return value
    model = QuantityModel.from_payload(value["quantity"])
    if model.nfb_config_for_version(model.selected_version_id):
        return value
    spec = model_spec(DEFAULT_BRAND, DEFAULT_MODEL)
    if spec is None or not spec.dimensionally_complete:
        raise ValueError("RECEIVING_DEFAULT_NFB_CURRENT_CSV_INCOMPLETE")
    selected = numeric_model_ref(DEFAULT_BRAND, DEFAULT_MODEL)
    heights = list(SETTING_DEFAULTS["inner_door_layer_heights_mm"])
    config = {"layers": 1, "models": [selected, ""],
              "layer_heights_mm": heights}
    box["inner_door_layers"] = 1
    box["inner_door_models"] = [selected, ""]
    box["inner_door_layer_heights_mm"] = heights
    value[BOX_KEY] = box
    value = project_common_box(value)
    panels = [p for p in cabinet_policy.derive_inner_door_panels(value)
              if str(p.cell_key) == "0:0"]
    if len(panels) != 1:
        raise ValueError("RECEIVING_DEFAULT_NFB_UPPER_PANEL_NOT_UNIQUE")
    part_id = panels[0].stable_id
    features = editor_nfb_features_from_csv(value, config)
    if len(features) != 1:
        raise ValueError("RECEIVING_DEFAULT_NFB_CSV_OPENING_NOT_UNIQUE")
    committed = committed_csv_nfb_config(part_id, features, config)
    model.set_version_nfb_config(
        model.selected_version_id, submitted=True, config=committed,
    )
    value["quantity"] = model.snapshot()
    part_features = deepcopy(dict(value.get("part_features") or {}))
    part_features[part_id] = list(features)
    value["part_features"] = part_features
    return project_common_box(value)
