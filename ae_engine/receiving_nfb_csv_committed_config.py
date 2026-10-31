# -*- coding: utf-8 -*-
"""Convert confirmed native NFB CSV CUTTING edits to the existing NFBConfig.

A user pressing the original Hole Editor's Confirm All submits selected CSV
rows for the *current* real quantity-version/Bay. This saves SOURCE identity,
not geometry/manufacturing approval. In particular an initial editor X is
UNVERIFIED_BASIS, never fabricated as CONFIRMED shop datum.
"""
from __future__ import annotations

from hashlib import sha256
from copy import deepcopy

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


def preview_quantity_nfb_submission(snapshot, quantity_model, config):
    """Validate all quantity NFB source/projection BEFORE mutating live owner.

    Confirm All is one logical commit: an invalid Family/door/quantity box
    must not leave the version marked submitted while the physical sheet
    remains unchanged. Re-run the same canonical validators on a detached
    model and return only a candidate projection; caller commits later.
    """
    from phase6_quantity_model import QuantityModel
    from .receiving_quantity_box import project_common_box

    if not isinstance(quantity_model, QuantityModel):
        raise ValueError("單只 NFB 需要目前的數量模式版本")
    candidate = QuantityModel.from_payload(quantity_model.snapshot())
    candidate.set_version_nfb_config(
        candidate.selected_version_id, submitted=True, config=config,
    )
    projected = deepcopy(dict(snapshot))
    projected["quantity"] = candidate.snapshot()
    return project_common_box(projected)

def candidate_committed_csv_nfb_config(source):
    """Select the sole verified physical NFB CSV source; reject mixed CUTTING."""
    feature_map = dict(source.get("features") or {})
    imported = [
        (part_id, features)
        for part_id, features in feature_map.items()
        if any(getattr(feat, "source_type", None) == "NFB_CSV_SOURCE"
               for feat in features)
    ]
    if not imported:
        return None
    if len(imported) != 1:
        raise ValueError("每個候選 NFB 必須對應唯一實體內門板件")
    if any(
        str(getattr(feat, "layer", "")).upper() == "CUTTING"
        and getattr(feat, "source_type", None) != "NFB_CSV_SOURCE"
        for features in feature_map.values() for feat in features
    ):
        raise ValueError("候選存在非 NFB CUTTING；不得與已提交 NFB 形成雙重開孔")
    part_id, features = imported[0]
    return committed_csv_nfb_config(part_id, features, source)


def validate_candidate_nfb_replacement(
    layout, selected_bays, source, csv_config, *,
    rejection_message="已提交 NFB 與非 CSV 候選不得形成雙重 CUTTING owner",
):
    """Reject a non-CSV candidate overwriting any submitted physical NFB."""
    if csv_config is not None or not source.get("features"):
        return
    if any(
        layout["sets"][si]["bays"][bi].get("nfb_config_submitted") is True
        for si, bi in selected_bays
    ):
        raise ValueError(rejection_message)


def replace_candidate_bay_nfb(layout, set_index, bay_index, csv_config):
    """Commit verified source once with canonical Bay-qualified physical IDs."""
    from .receiving_layout import update_receiving_bay
    if csv_config is None:
        return layout
    bay_id = str(layout["sets"][set_index]["bays"][bay_index]["stable_id"])
    selected = deepcopy(csv_config)
    for hole in selected["holes"]:
        hole["physical_hole_id"] = f"{bay_id}:{hole['physical_hole_id']}"
    return update_receiving_bay(
        layout, set_index=set_index, bay_index=bay_index,
        nfb_config_submitted=True, nfb_config=selected,
    )
