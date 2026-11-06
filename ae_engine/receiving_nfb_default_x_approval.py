# -*- coding: utf-8 -*-
"""Accept WHD's CURRENT native NFB default X as one explicit physical action.

This is the original Hole Editor's confirmed-source path expressed as an
immutable Engine transaction for source-confirmed fresh Receiving Bays.
No CADSplit-authored hole geometry, extra DXF or guessed X is introduced.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import replace

from .receiving_nfb_csv_committed_config import (
    apply_receiving_nfb_csv_candidate,
    candidate_committed_csv_nfb_config,
)
from .receiving_nfb_csv_editor_features import (
    candidate_receiving_nfb_csv_for_fresh_bay,
)
from .receiving_layout import (
    normalize_receiving_layout, project_receiving_bay_legacy_aliases,
    update_receiving_bay,
)
from .receiving_mode_session import fresh_receiving_mode


def approve_receiving_nfb_csv_default_x(
    layout: Mapping[str, object], *, set_index: int, bay_index: int,
    thickness_mm: object, source: Mapping[str, object],
    confirmation: str,
) -> tuple[dict[str, object], dict[str, object]]:
    """Confirm one Bay's unmodified Engine defaults, without per-hole typing.

    The operator must deliberately accept the CURRENT default positions for
    the whole Bay.  Re-generate the native source from that exact physical Bay
    and current CSV: any changed CSV, dimensions, door, model, slot or opening
    makes the previous draft invalid. Apply stays an atomic detached Engine
    transaction. The returned typed feature is a confirmed physical source,
    not a generic nominal-pitch or whole-cabinet certificate.
    """
    if confirmation != "ACCEPT_CURRENT_WHD_NFB_DEFAULT_X":
        raise ValueError("NFB_DEFAULT_X_OPERATOR_CONFIRMATION_REQUIRED")
    if not isinstance(source, Mapping):
        raise ValueError("NFB_DEFAULT_X_ORIGINAL_CANDIDATE_REQUIRED")
    if set(source) != {"layers", "models", "layer_heights_mm", "features"}:
        raise ValueError("NFB_DEFAULT_X_ORIGINAL_CANDIDATE_REQUIRED")
    normalized = normalize_receiving_layout(layout)
    # Candidate builder owns validation of exact Set/Bay identity, confirmed
    # brand, door topology, current V5 CSV completeness and collision-free
    # native editor geometry; never duplicate those rules here.
    fresh = candidate_receiving_nfb_csv_for_fresh_bay(
        normalized, set_index=set_index, bay_index=bay_index,
        thickness_mm=thickness_mm,
        layers=source["layers"], models=source["models"],
        layer_heights_mm=source["layer_heights_mm"],
    )
    if dict(source) != fresh:
        raise ValueError("NFB_DEFAULT_X_CURRENT_ENGINE_SOURCE_DRIFT")
    features = {}
    for part, rows in fresh["features"].items():
        features[part] = tuple(
            replace(
                row,
                source_params=tuple(
                    (key, value) for key, value in row.source_params
                    if key != "fresh_bay_auto_unconfirmed"
                ) + (("fresh_bay_default_x_confirmed", True),),
            )
            for row in rows
        )
    accepted = {**fresh, "features": features}
    if candidate_committed_csv_nfb_config(accepted) is None:
        raise ValueError("NFB_DEFAULT_X_SOURCE_PROOF_INVALID")
    # The fresh candidate generator can derive a *transient* true upper
    # inner-door panel without persisting its topology. Manufacturing needs
    # that same Engine-derived physical Door identity to be stored on this
    # selected Bay; otherwise source Apply alone produces a submitted NFB
    # with no real upper Door and would fail FinalScene resolution. Never
    # synthesize a second Door layout or touch the sibling Bays.
    bay = normalized["sets"][set_index]["bays"][bay_index]
    snapshot = fresh_receiving_mode(
        "set_bay",
        {"w": bay["width"], "h": bay["height"], "d": bay["depth"]},
        thickness=thickness_mm,
    )
    door = deepcopy(bay["door_state"])
    if "inner_doors" in door:
        snapshot["inner_doors"] = deepcopy(door["inner_doors"])
    else:
        if door["door_layout_columns"] != snapshot["door_layout_columns"]:
            raise ValueError("NFB_DEFAULT_X_INNER_DOOR_SOURCE_REQUIRED")
        door["inner_doors"] = deepcopy(snapshot["inner_doors"])
    physical = update_receiving_bay(
        normalized, set_index=set_index, bay_index=bay_index,
        door_state=door,
    )
    committed = apply_receiving_nfb_csv_candidate(
        physical, set_index=set_index, bay_indices=(bay_index,),
        source=accepted,
    )

    # Reproject the selected actual Engine sheet, then run the ORIGINAL
    # committed FinalScene source gate before returning the transaction.
    snapshot["door_layout_columns"] = deepcopy(door["door_layout_columns"])
    snapshot["receiving_layout"] = committed
    projected = project_receiving_bay_legacy_aliases(
        snapshot, set_index=set_index, bay_index=bay_index,
        validate_common=False,
    )
    from .receiving_nfb_committed_final_scene import _submitted_csv_holes

    verified = _submitted_csv_holes(projected)
    count = sum(len(rows) for rows in features.values())
    if not verified or len(verified[1]) != count:
        raise ValueError("NFB_DEFAULT_X_PHYSICAL_FINALSCENE_SOURCE_NOT_READY")
    return committed, accepted
