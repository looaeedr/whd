# -*- coding: utf-8 -*-
"""Resolve independent endcap and inner-door configurations on one actual Bay.

This returns source settings for assembly. It does not certify NFB CUTTING:
the true X/Y/DXF mapping work remains governed by #1494–#1497.
"""
from __future__ import annotations
from copy import deepcopy
from ae_engine.receiving_layout import normalize_receiving_layout
from ae_engine.receiving_shared_settings import setting_value


def paired_bay_parts(layout, *, set_index, bay_index):
    data = normalize_receiving_layout(layout)
    set_row = data["sets"][set_index]
    bay = set_row["bays"][bay_index]
    return {
        "set_id": str(set_row["stable_id"]),
        "bay_id": str(bay["stable_id"]),
        "set_index": set_index,
        "bay_index": bay_index,
        "head_features": setting_value(set_row, bay_index, "head_features"),
        "tail_features": setting_value(set_row, bay_index, "tail_features"),
        "inner_door": {
            "layers": setting_value(set_row, bay_index, "inner_door_layers"),
            "models": setting_value(set_row, bay_index, "inner_door_models"),
            "layer_heights_mm": setting_value(set_row, bay_index, "inner_door_layer_heights_mm"),
        },
    }


def paired_set_parts(layout, *, set_index):
    data = normalize_receiving_layout(layout)
    return tuple(paired_bay_parts(data, set_index=set_index, bay_index=i)
                 for i in range(len(data["sets"][set_index]["bays"])))


def validate_inner_door_allocation(layout, library, quantities, assigned, *,
                                   expected_counts=None):
    from ae_engine.receiving_assignment_core import validate_positions
    from ae_engine.receiving_inner_door_candidates import inner_versions, inner_config
    positions = validate_positions(
        layout, (row["id"] for row in inner_versions(library)), quantities,
        assigned, expected_counts=expected_counts,
    )
    configs = {version_id: inner_config(library, version_id)
               for version_id in quantities}
    return tuple((si, bi, deepcopy(configs[assigned[(si, bi)]]))
                 for si, bi in positions)
