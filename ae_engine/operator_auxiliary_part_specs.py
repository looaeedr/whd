# -*- coding: utf-8 -*-
"""Headless operator-facing BasePlate and IndicatorBox PartSpec builders.

These routines own the physical manufacturing *request* adaptation, including
Receiving committed BasePlate source fields and material Fold DTO conversion.
The GUI selects operator inputs but cannot certify parts or substitute source.
"""
from __future__ import annotations

from .cabinet_types import policy as cabinet_family_policy
from .box_body_fold_profile import profile_to_fold_segments
from .fold_designer_snapshot_dimensions import normalize_fold_designer_indicator_groups
from .contracts import BasePlatePartSpec, IndicatorBoxPartSpec
from .operator_settings_transactions import (
    normalize_operator_settings_updates,
    normalize_operator_source_dimension,
)


def _finite_auxiliary_setting(values, key: str) -> float:
    """Use the original Engine Settings numeric contract for Fold/shrink input.

    These values are signed legacy settings, not physical W/H/T. An invalid
    present value cannot become a valid manufactured number through float()
    (notably True -> 1 or a NaN/Infinity).
    """
    raw = values[key]  # Keep the public PartSpec's required-key contract.
    clean = normalize_operator_settings_updates({key: 0.0}, {key: raw})
    if key not in clean:
        raise ValueError(f"{key} 製造來源必須是有限非布林數值")
    return clean[key]



def build_base_plate_operator_part_spec(
    values, *, features, corner_policy=None,
    box_body_structure_state=None, box_body_fold_profile=None,
) -> BasePlatePartSpec:
    """Build the original structural BasePlate request without GUI policy."""
    model = str(values.get("model", "")).strip()
    # Preserve the original operator model name; only Registry may decide
    # which physical Receiving source fields belong to this PartSpec.
    receiving = cabinet_family_policy.canonical_family_name(model) == "受電箱"
    return BasePlatePartSpec(
        width=normalize_operator_source_dimension(values["w"], field="w"),
        height=normalize_operator_source_dimension(values["h"], field="h"),
        thickness=normalize_operator_source_dimension(values["t"], field="t"),
        shrink_top=_finite_auxiliary_setting(values, "base_plate_shrink_top"),
        shrink_bottom=_finite_auxiliary_setting(values, "base_plate_shrink_bottom"),
        shrink_left=_finite_auxiliary_setting(values, "base_plate_shrink_left"),
        shrink_right=_finite_auxiliary_setting(values, "base_plate_shrink_right"),
        bend=_finite_auxiliary_setting(values, "base_plate_bend"),
        features=tuple(features or ()),
        corner_policy=corner_policy,
        box_body_structure_state=box_body_structure_state,
        box_body_fold_profile=profile_to_fold_segments(
            box_body_fold_profile or ()
        ),
        model_name=model or None,
        receiving_bend_pattern=(
            values.get("receiving_bend_pattern") if receiving else None
        ),
        physical_id=str(values.get("physical_id") or "base_plate"),
        receiving_nfb_depth_pair_mm=(
            values.get("receiving_nfb_depth_pair_mm") if receiving else None
        ),
    )


def resolve_fold_designer_base_plate_source(
    part_key, input_snapshot, *, width, height, thickness, frame_width,
    model_name, corner_policy=None,
):
    """Preserve the existing Fold Designer physical BasePlate input authority.

    Generic operator fields are only the legacy preview/request fallback.
    A real Receiving source comes exclusively from the existing selected NFB
    CSV/BasePlate resolver and owns the matching structural contour, including
    its own corners.  It is never a certification or a separate second plate.
    """
    from .receiving_base_plate_config import receiving_base_plate_values

    data = dict(input_snapshot or {})
    key = str(part_key)
    model = str(model_name or "")
    values = {
        "w": normalize_operator_source_dimension(width, field="w"),
        "h": normalize_operator_source_dimension(height, field="h"),
        "t": normalize_operator_source_dimension(thickness, field="t"),
        "fw": normalize_operator_source_dimension(frame_width, field="fw"),
        "base_plate_shrink_top": _finite_auxiliary_setting(
            {"base_plate_shrink_top": data.get("base_plate_shrink_top", 0)},
            "base_plate_shrink_top",
        ),
        "base_plate_shrink_bottom": _finite_auxiliary_setting(
            {"base_plate_shrink_bottom": data.get("base_plate_shrink_bottom", 0)},
            "base_plate_shrink_bottom",
        ),
        "base_plate_shrink_left": _finite_auxiliary_setting(
            {"base_plate_shrink_left": data.get("base_plate_shrink_left", 0)},
            "base_plate_shrink_left",
        ),
        "base_plate_shrink_right": _finite_auxiliary_setting(
            {"base_plate_shrink_right": data.get("base_plate_shrink_right", 0)},
            "base_plate_shrink_right",
        ),
        "base_plate_bend": _finite_auxiliary_setting(
            {"base_plate_bend": data.get("base_plate_bend", 20)},
            "base_plate_bend",
        ),
        "receiving_bend_pattern": data.get("receiving_bend_pattern"),
        "physical_id": key, "model": model,
    }
    if cabinet_family_policy.canonical_family_name(model) == "受電箱":
        if key != "base_plate":
            raise ValueError("RECEIVING_BASE_PLATE_LEGACY_CELL_UNSUPPORTED")
        physical = receiving_base_plate_values(data)
        if physical is not None:
            values.update(physical)
            corner_policy = None
    return values, corner_policy


def build_indicator_box_operator_part_spec(
    values, layer_groups, *, features,
) -> IndicatorBoxPartSpec:
    """Normalize the original operator IndicatorBox request in Engine."""
    return IndicatorBoxPartSpec(
        layer_groups=normalize_fold_designer_indicator_groups(layer_groups),
        thickness=normalize_operator_source_dimension(values["t"], field="t"),
        model_name=None,
        features=tuple(features or ()),
        corner_policy=None,
    )
