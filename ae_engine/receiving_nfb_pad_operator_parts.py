# -*- coding: utf-8 -*-
"""Source-backed NFB PAD physical 2D preview parts for existing Part selector.

No invented PAD input, manual dimensions or extra release rights. The SAME
selected V5 CSV + common tooling as real Base Plate CUTTING and 3D assembly
owns this unmanufacturable PartRenderData.
"""
from __future__ import annotations

from collections.abc import Mapping

from .receiving_nfb_pad_part import NfbPadDraftPart, build_nfb_pad_draft_part
from .receiving_nfb_pad_generator import (
    generate_nfb_pad_patterns, read_pad_tooling_rule,
)


def committed_nfb_pad_draft_parts(snapshot: Mapping) -> tuple[NfbPadDraftPart, ...]:
    """Derive separate non-MFG 2D PAD parts from exactly the current Bay."""
    if (not isinstance(snapshot, Mapping)
            or snapshot.get("model") not in ("受電箱", "RECEIVING")
            or snapshot.get("nfb_config_submitted") is not True):
        return ()
    from .receiving_base_plate_config import receiving_base_plate_values
    from .sheetmetal_part_adapters import (
        RECEIVING_BASE_PATTERN_LEFT, RECEIVING_BASE_PATTERN_RIGHT,
    )
    physical = receiving_base_plate_values(snapshot)
    if (physical is None or physical["receiving_bend_pattern"]
            not in (RECEIVING_BASE_PATTERN_LEFT, RECEIVING_BASE_PATTERN_RIGHT)):
        return ()  # existing CENTER double-fold owns its own real Z faces.
    from .receiving_nfb_committed_final_scene import _submitted_csv_holes
    from .receiving_nfb_model_identity import parse_numeric_model_ref
    from .receiving_nfb_numeric_catalog import model_spec
    found = _submitted_csv_holes(snapshot)
    if found is None:
        return ()
    _door_id, holes = found
    if not holes:
        return ()
    layers = holes[0].layer_count
    tooling = read_pad_tooling_rule()
    result = []
    for tier in range(layers):
        selected = tuple(row for row in holes if row.slot_index == tier)
        if not selected:
            continue
        specs = []
        for row in selected:
            identity = parse_numeric_model_ref(row.model_ref)
            if identity is None or identity[0] != row.brand:
                raise ValueError("PAD_OPERATOR_2D_SELECTED_CSV_IDENTITY_DRIFT")
            spec = model_spec(*identity)
            if spec is None or not spec.dimensionally_complete:
                raise ValueError("PAD_OPERATOR_2D_MODEL_SOURCE_INCOMPLETE")
            specs.append(spec)
        patterns = generate_nfb_pad_patterns(
            specs, plate_thickness_mm=float(snapshot["t"]), tooling=tooling,
        )
        parent = ("base_plate" if layers == 1
                  else f"base_plate:nfb_layer:{tier}")
        for pattern in patterns:
            row = selected[pattern.switch_index]
            result.append(build_nfb_pad_draft_part(
                pattern, parent_base_id=parent,
                owner_hole_id=row.physical_hole_id,
            ))
    if len({part.part_id for part in result}) != len(result):
        raise ValueError("PAD_OPERATOR_2D_DUPLICATE_PHYSICAL_OWNER")
    return tuple(result)
