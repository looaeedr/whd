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
    if type(set_index) is not int or type(bay_index) is not int:
        raise ValueError("Receiving Set/Bay indices must be integers, not bool")
    data = normalize_receiving_layout(layout)
    if not 0 <= set_index < len(data["sets"]):
        raise IndexError("Receiving set_index out of range")
    set_row = data["sets"][set_index]
    if not 0 <= bay_index < len(set_row["bays"]):
        raise IndexError("Receiving bay_index out of range")
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
    if type(set_index) is not int:
        raise ValueError("Receiving set_index must be integer, not bool")
    data = normalize_receiving_layout(layout)
    if not 0 <= set_index < len(data["sets"]):
        raise IndexError("Receiving set_index out of range")
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

def apply_receiving_inner_door_quantity_configuration(
    layout, library, quantities, assigned, *, expected_counts=None,
):
    """Commit the whole verified Receiving Set/Bay inner-door allocation.

    All candidate source, version, physical NFB and topology checks run before
    applying any Set/Bay. This is the manufacturing-state transaction: GUI
    selection, dirty state and presentation are deliberately excluded.
    Returns (detached_layout, changed_physical_bay_ids).
    """
    from .receiving_shared_settings import (
        validate_setting, unlink_setting, edit_setting,
    )
    from .receiving_nfb_csv_committed_config import (
        candidate_committed_csv_nfb_config,
        validate_candidate_nfb_replacement,
        replace_candidate_bay_nfb,
    )

    plan = validate_inner_door_allocation(
        layout, library, quantities, assigned, expected_counts=expected_counts,
    )
    replacements = {}
    for si, bi, config in plan:
        validate_setting("inner_door_version_id", assigned[(si, bi)])
        csv = candidate_committed_csv_nfb_config(config)
        validate_candidate_nfb_replacement(layout, ((si, bi),), config, csv)
        replacements[(si, bi)] = csv

    candidate = layout
    for si, bi, config in plan:
        for kind, value in (
            ("inner_door_layers", config["layers"]),
            ("inner_door_models", config["models"]),
            ("inner_door_features", config.get("features", {})),
            ("inner_door_layer_heights_mm", config.get("layer_heights_mm")),
            ("inner_door_version_id", assigned[(si, bi)]),
        ):
            candidate = unlink_setting(
                candidate, set_index=si, bay_index=bi, kind=kind,
            )
            candidate = edit_setting(
                candidate, set_index=si, bay_index=bi, kind=kind, value=value,
            )
        candidate = replace_candidate_bay_nfb(
            candidate, si, bi, replacements[(si, bi)],
        )
    changed_ids = tuple(
        str(candidate["sets"][si]["bays"][bi]["stable_id"])
        for si, bi, _ in plan
    )
    return candidate, changed_ids
