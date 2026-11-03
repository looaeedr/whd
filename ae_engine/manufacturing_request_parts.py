# -*- coding: utf-8 -*-
"""Canonical input part inventory for GUI/headless ManufacturingResolveRequest.

Only the Engine can decide source-proven Receiving Base Plate or fixing-ear
part ownership. Returned IDs are RAW request inputs, never a manufacture
release or duplicate derived/tier/PAD manufacturing part.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .physical_part_identity import is_box_body_physical_piece_key
from .custom_part_catalog import is_custom_part
from .receiving_base_plate_config import receiving_base_plate_values
from .receiving_base_fixing_plate import receiving_base_fixing_plate_previews


@dataclass(frozen=True)
class OperatorManufacturingPartSourcePlan:
    """Canonical physical-part identity route, not manufacturing authorization.

    A GUI can acquire operator values, call selected public Engine factories,
    and retain display caches; it cannot infer physical identity from part IDs.
    """
    requires_custom_default_profile: bool
    requires_direct_part_spec: bool
    needs_committed_relief: bool
    input_adapter: str
    render_source: str


def plan_operator_manufacturing_part_source(part_key, *, has_saved_profiles=True):
    """Share one physical part source classifier across GUI and headless clients.

    Routing is intentionally compatible with the existing operator endpoints.
    Source validation (Family, baseline SHA, Spec/Part identity, 2D/3D/DXF)
    still belongs to each called Engine factory; a recognized ID is no permit.
    """
    key = str(part_key or "")
    is_custom = is_custom_part(key)
    endcap = key in ("head", "tail")
    if key.startswith("nfb_pad:"):
        render_source = "nfb_pad"
    elif key.startswith("base_plate:fixing_plate:"):
        render_source = "fixing_plate"
    elif key.startswith("box_body:divider:"):
        render_source = "divider"
    elif key.startswith("inner_door:") and key.endswith(":panel"):
        render_source = "inner_panel"
    elif key.startswith("inner_door:") and key.endswith("_frame"):
        render_source = "inner_frame"
    else:
        render_source = "part_spec"
    if key.startswith("indicator"):
        input_adapter = "indicator"
    elif key.startswith("box_body:part:"):
        input_adapter = "multipart"
    elif key.startswith("door:"):
        input_adapter = "door"
    else:
        input_adapter = "raw"
    return OperatorManufacturingPartSourcePlan(
        requires_custom_default_profile=bool(is_custom and not has_saved_profiles),
        requires_direct_part_spec=bool(endcap or is_custom),
        needs_committed_relief=endcap,
        input_adapter=input_adapter,
        render_source=render_source,
    )


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
