# -*- coding: utf-8 -*-
"""Canonical input part inventory for GUI/headless ManufacturingResolveRequest.

Only the Engine can decide source-proven Receiving Base Plate or fixing-ear
part ownership. Returned IDs are RAW request inputs, never a manufacture
release or duplicate derived/tier/PAD manufacturing part.
"""
from __future__ import annotations

from collections.abc import Mapping

from .physical_part_identity import is_box_body_physical_piece_key
from .receiving_base_plate_config import receiving_base_plate_values
from .receiving_base_fixing_plate import receiving_base_fixing_plate_previews


def canonical_manufacturing_request_part_keys(snapshot, available_parts):
    """Resolve source-backed RAW canonical inputs, preserving legacy order."""
    values = tuple(available_parts or ())
    if (isinstance(snapshot, Mapping)
            and snapshot.get("model") in ("受電箱", "RECEIVING")
            and snapshot.get("nfb_config_submitted") is True
            and "base_plate" not in values):
        try:
            source = receiving_base_plate_values(snapshot)
        except (ValueError, TypeError, KeyError):
            source = None
        if source is not None:
            values = values + ("base_plate",)

    if (isinstance(snapshot, Mapping)
            and snapshot.get("model") in ("受電箱", "RECEIVING")
            and snapshot.get("nfb_config_submitted") is True
            and isinstance(snapshot.get("nfb_config"), Mapping)
            and snapshot["nfb_config"].get("layer_count") == 2):
        try:
            verified = tuple(receiving_base_fixing_plate_previews(
                snapshot, available_parts=("base_plate",),
            ))
        except ValueError as exc:
            if str(exc) != "EAR_Z_NFB_SOURCE_IDENTITY_DRIFT":
                raise
            verified = ()
        if len(verified) == 4 and len({item.part_id for item in verified}) == 4:
            values = tuple(
                item for item in values
                if not str(item).startswith("base_plate:fixing_plate:")
            ) + tuple(item.part_id for item in verified)

    return tuple(
        str(key) for key in values
        if str(key or "")
        and not is_box_body_physical_piece_key(key)
        and not str(key).startswith("base_plate:nfb_layer:")
        and not str(key).startswith("nfb_pad:")
    )
