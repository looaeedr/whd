# -*- coding: utf-8 -*-
"""Headless operator-facing BasePlate and IndicatorBox PartSpec builders.

These routines own the physical manufacturing *request* adaptation, including
Receiving committed BasePlate source fields and material Fold DTO conversion.
The GUI selects operator inputs but cannot certify parts or substitute source.
"""
from __future__ import annotations

from .box_body_fold_profile import profile_to_fold_segments
from .contracts import BasePlatePartSpec, IndicatorBoxPartSpec


def build_base_plate_operator_part_spec(
    values, *, features, corner_policy=None,
    box_body_structure_state=None, box_body_fold_profile=None,
) -> BasePlatePartSpec:
    """Build the original structural BasePlate request without GUI policy."""
    model = str(values.get("model", "")).strip()
    # Exact old model keys are retained for saved-project compatibility.
    receiving = model in {"受電箱", "RECEIVING"}
    return BasePlatePartSpec(
        width=float(values["w"]),
        height=float(values["h"]),
        thickness=float(values["t"]),
        shrink_top=float(values["base_plate_shrink_top"]),
        shrink_bottom=float(values["base_plate_shrink_bottom"]),
        shrink_left=float(values["base_plate_shrink_left"]),
        shrink_right=float(values["base_plate_shrink_right"]),
        bend=float(values["base_plate_bend"]),
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


def build_indicator_box_operator_part_spec(
    values, layer_groups, *, features,
) -> IndicatorBoxPartSpec:
    """Normalize the original operator IndicatorBox request in Engine."""
    return IndicatorBoxPartSpec(
        layer_groups=tuple(int(v) for v in layer_groups),
        thickness=float(values["t"]),
        model_name=None,
        features=tuple(features or ()),
        corner_policy=None,
    )
