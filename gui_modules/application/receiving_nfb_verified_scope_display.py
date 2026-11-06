# -*- coding: utf-8 -*-
"""WHD Receiving NFB pair exported-scope DISPLAY adapter, no business authority.

Only the real typed part-only exporter receipt may be handed to the Engine.
The immutable proof is historical output disclosure, never manufacturing gate.
"""
from __future__ import annotations

from typing import Mapping

from ae_engine import manufacturing_api
from ae_engine.manufacturing_api import NfbCsvVerifiedSelectorProof
from .receiving_nfb_pair_partial_export_action import (
    NfbCsvPairedPartOnlyDxf, NfbCsvTwoTierPartOnlyDxf,
)


def capture_verified_v5_pair_display(snapshot, receipt):
    """Retain only a real typed successful pair receipt, ask Engine to recheck."""
    if not isinstance(snapshot, Mapping) or type(receipt) not in (
        NfbCsvPairedPartOnlyDxf, NfbCsvTwoTierPartOnlyDxf,
    ):
        return None
    if type(receipt.verified_v5_scope) is not manufacturing_api.NfbCsvVerifiedExportScope:
        return None
    paths = (
        (receipt.inner_door_path, receipt.base_plate_path)
        if type(receipt) is NfbCsvPairedPartOnlyDxf
        else (receipt.inner_door_path, *receipt.base_plate_paths)
    )
    return manufacturing_api.capture_verified_csv_v5_pair_display_proof(
        snapshot, receipt.verified_v5_scope, paths, receipt.source_hole_ids,
    )


def verified_v5_model_operator_label(proof, snapshot, brand, model_ref):
    """Renderer-only: Engine may revoke the historical proof on ANY drift."""
    return manufacturing_api.verified_csv_v5_operator_label(
        proof, snapshot, brand, model_ref,
    )
