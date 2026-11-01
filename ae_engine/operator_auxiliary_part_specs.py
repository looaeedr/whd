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
        "w": float(width), "h": float(height),
        "t": float(thickness), "fw": float(frame_width),
        "base_plate_shrink_top": float(data.get("base_plate_shrink_top", 0)),
        "base_plate_shrink_bottom": float(data.get("base_plate_shrink_bottom", 0)),
        "base_plate_shrink_left": float(data.get("base_plate_shrink_left", 0)),
        "base_plate_shrink_right": float(data.get("base_plate_shrink_right", 0)),
        "base_plate_bend": float(data.get("base_plate_bend", 20)),
        "receiving_bend_pattern": data.get("receiving_bend_pattern"),
        "physical_id": key, "model": model,
    }
    if model in {"受電箱", "RECEIVING"}:
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
        layer_groups=tuple(int(v) for v in layer_groups),
        thickness=float(values["t"]),
        model_name=None,
        features=tuple(features or ()),
        corner_policy=None,
    )
