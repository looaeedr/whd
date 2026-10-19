# -*- coding: utf-8 -*-
"""Convert confirmed native NFB CSV CUTTING edits to the existing NFBConfig.

A user pressing the original Hole Editor's Confirm All submits selected CSV
rows for the *current* real quantity-version/Bay. This saves SOURCE identity,
not geometry/manufacturing approval. In particular an initial editor X is
UNVERIFIED_BASIS, never fabricated as CONFIRMED shop datum.
"""
from __future__ import annotations

from hashlib import sha256

from .receiving_nfb_model_identity import numeric_model_ref
from .receiving_nfb_numeric_catalog import brand_csv_path, model_spec
from .receiving_nfb_persistence import normalize_nfb_config
from .receiving_shared_settings import switch_filenames_in_layer, validate_setting
from .sheetmetal_feature_core import ProfileFeature


def committed_csv_nfb_config(part_key, features, config):
    """Return an exact source NFBConfig or reject stale/missing/duplicated holes."""
    if not (isinstance(part_key, str)
            and part_key.startswith("inner_door:")
            and part_key.endswith(":panel")):
        raise ValueError("NFB_CSV_COMMIT_PHYSICAL_DOOR_INVALID")
    if not isinstance(config, dict):
        raise ValueError("NFB_CSV_COMMIT_REQUIRES_STAGED_OPERATOR_CONFIG")
    count = validate_setting("inner_door_layers", config.get("layers"))
    models = validate_setting("inner_door_models", config.get("models"))
    expected = {
        (layer, slot): model
        for layer in range(count)
        for slot, model in enumerate(switch_filenames_in_layer(models[layer]))
    }
    if not expected:
        raise ValueError("NFB_CSV_COMMIT_REQUIRES_SELECTED_MODEL")
    seen = {}
    for feature in features:
        if not isinstance(feature, ProfileFeature):
            continue
        if feature.source_type != "NFB_CSV_SOURCE":
            continue
        info = dict(feature.source_params)
        if info.get("part_id") != part_key:
            raise ValueError("NFB_CSV_COMMIT_WRONG_PHYSICAL_DOOR")
        layer, slot = info.get("layer_index"), info.get("slot_index")
        key = (layer, slot)
        if key not in expected or key in seen:
            raise ValueError("NFB_CSV_COMMIT_MISSING_OR_DUPLICATE_SLOT")
        brand, model = info.get("brand"), info.get("model")
        from .receiving_nfb_model_identity import parse_numeric_model_ref
        if parse_numeric_model_ref(expected[key]) != (brand, model):
            raise ValueError("NFB_CSV_COMMIT_MODEL_CHANGED_SINCE_EDIT")
        spec = model_spec(brand, model)
        if (spec is None or not spec.dimensionally_complete
                or not feature.points or len(feature.points) != 4):
            raise ValueError("NFB_CSV_COMMIT_INCOMPLETE_PHYSICAL_SOURCE")
        if sha256(brand_csv_path(brand).read_bytes()).hexdigest() != info.get("csv_sha256"):
            raise ValueError("NFB_CSV_COMMIT_SOURCE_CHANGED")
        if type(feature.rotation_deg) not in (int, float):
            raise ValueError("NFB_CSV_COMMIT_ROTATION_INVALID")
        angle = int(feature.rotation_deg)
        if angle not in (0, 90, 180, 270) or angle != feature.rotation_deg:
            raise ValueError("NFB_CSV_COMMIT_ROTATION_UNSUPPORTED")
        seen[key] = {
            "physical_hole_id": f"{part_key}:nfb:layer:{layer}:slot:{slot}",
            "model_filename": numeric_model_ref(brand, model),
            "source_brand": brand,
            "layer_count": count,
            "layer_index": layer,
            "slot_index": slot,
            "manual_x_state": "UNVERIFIED_BASIS",
            "manual_x_mm": None,
            "rotation_deg": angle,
        }
    if set(seen) != set(expected):
        raise ValueError("NFB_CSV_COMMIT_MISSING_CONFIRMED_HOLE")
    return normalize_nfb_config({
        "layer_count": count,
        "holes": [seen[key] for key in sorted(seen)],
    })
