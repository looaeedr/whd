# -*- coding: utf-8 -*-
"""#2517: source-authoritative physical Receiving 2D sheet selection.

GUI supplies an immutable-ish operator snapshot and optional canonical solved
geometry. The real NFB BasePlate, PAD, and EAR sources remain Engine owned:
never manufacture phantom parts from 2D navigation or authorize NFB MFG-2.
"""
from __future__ import annotations

from collections.abc import Mapping
import re

from .cabinet_types.policy import canonical_family_name


def _resolved_physical_sheet(key, geometry, resolve_geometry, unavailable, missing):
    """Read exactly one canonical PartRenderData, lazily resolving if absent."""
    def found_in(source):
        return next(
            (part for part in tuple(getattr(source, "parts", ()) or ())
             if str(part.part_key) == key), None,
        )
    found = found_in(geometry)
    if found is None:
        if not callable(resolve_geometry):
            raise ValueError(unavailable)
        found = found_in(resolve_geometry())
    if found is None or getattr(found.render_data, "unfolded_topology", None) is None:
        raise ValueError(missing)
    return found.render_data


def resolve_operator_receiving_base_2d_source(
    key, payload, current_snapshot, *, cached_geometry=None, resolve_geometry=None,
):
    """Prefer real resolved one-tier/two-tier physical BasePlate or return None.

    None means caller should use its existing generic non-Receiving source.
    An explicitly requested, unsubmitted/invalid physical NFB tier fails shut.
    """
    key = str(key or "")
    if key == "base_plate" and (payload or {}).get("_use_committed_relief") is not False:
        if (isinstance(current_snapshot, Mapping)
                and canonical_family_name(current_snapshot) == "受電箱"
                and current_snapshot.get("nfb_config_submitted") is True
                and isinstance(current_snapshot.get("nfb_config"), Mapping)
                and current_snapshot["nfb_config"].get("layer_count") == 1):
            from .receiving_base_plate_config import receiving_base_plate_values
            try:
                known_base = receiving_base_plate_values(current_snapshot)
            except (ValueError, TypeError, KeyError):
                known_base = None
            if known_base is not None:
                return _resolved_physical_sheet(
                    key, cached_geometry, resolve_geometry,
                    "RECEIVING_ONE_TIER_2D_SOURCE_UNAVAILABLE",
                    "RECEIVING_ONE_TIER_2D_PHYSICAL_PART_MISSING",
                )
    if key.startswith("base_plate:nfb_layer:"):
        if not re.fullmatch(r"base_plate:nfb_layer:[01]", key):
            raise ValueError("RECEIVING_NFB_TIER_2D_PART_ID_INVALID")
        if (not isinstance(current_snapshot, Mapping)
                or canonical_family_name(current_snapshot) != "受電箱"
                or current_snapshot.get("nfb_config_submitted") is not True):
            raise ValueError("RECEIVING_NFB_TIER_2D_NOT_SUBMITTED")
        return _resolved_physical_sheet(
            key, cached_geometry, resolve_geometry,
            "RECEIVING_NFB_TIER_2D_SOURCE_UNAVAILABLE",
            "RECEIVING_NFB_TIER_2D_PHYSICAL_PART_MISSING",
        )
    return None


def resolve_operator_receiving_pad_2d_source(key, snapshot):
    """Resolve only committed physical PAD, never fabricate from a menu key."""
    if not isinstance(snapshot, Mapping):
        raise ValueError("PAD_OPERATOR_2D_SNAPSHOT_UNAVAILABLE")
    from .receiving_nfb_pad_operator_parts import committed_nfb_pad_draft_parts
    parts = tuple(
        part for part in committed_nfb_pad_draft_parts(snapshot)
        if part.part_id == key
    )
    if len(parts) != 1:
        raise ValueError("PAD_OPERATOR_2D_STALE_OR_UNAUTHORIZED_PART")
    part = parts[0]
    if (part.manufacturing_ready
            or part.render_data.metadata.get("manufacturing_ready")
            or part.render_data.metadata.get("nfb_deferred_manufacturing_role") != "PAD"):
        raise ValueError("PAD_OPERATOR_2D_MFG_GATE_INVALID")
    return part.render_data


def resolve_operator_receiving_fixing_2d_source(
    key, payload, *, live_snapshot=None,
):
    """Read one original physical fixing-plate source for exact selected Bay.

    Source from a selected Bay must match its projected W/H/D, Door topology,
    and committed NFB; otherwise refuse instead of mixing another Bay.
    Minimal single-sheet editor may consume live snapshot only when no
    selected Bay ownership exists.
    """
    from .receiving_base_fixing_plate import receiving_base_fixing_plate_previews
    from .receiving_base_fixing_plate_geometry import (
        build_fixing_plate_source_render_data,
    )
    source = dict(payload or {})
    selection = source.get("_receiving_runtime_selection")
    if isinstance(selection, Mapping):
        from .receiving_layout import project_receiving_bay_legacy_aliases
        si, bi = selection.get("set_index"), selection.get("bay_index")
        if type(si) is not int or type(bi) is not int:
            raise ValueError("BASE_FIXING_PLATE_BAY_SELECTOR_INVALID")
        authoritative = project_receiving_bay_legacy_aliases(
            source, set_index=si, bay_index=bi,
        )
        for field in (
            "w", "h", "d", "_receiving_runtime_selection",
            "multi_door_enabled", "door_layout_columns",
            "inner_doors", "nfb_config", "nfb_config_submitted",
        ):
            if source.get(field) != authoritative.get(field):
                raise ValueError(
                    f"BASE_FIXING_PLATE_BAY_SOURCE_DRIFT:{field}:"
                    f" selected={selection!r}"
                )
    elif isinstance(live_snapshot, Mapping):
        for name in ("nfb_config", "nfb_config_submitted"):
            source.pop(name, None)
        for name in (
            "model", "w", "h", "d", "t", "receiving_base_plate",
            "receiving_layout", "_receiving_runtime_selection",
            "nfb_config", "nfb_config_submitted", "inner_doors",
            "receiving_inner_door_layer_heights_mm",
        ):
            if name in live_snapshot:
                source[name] = live_snapshot[name]
    physical = receiving_base_fixing_plate_previews(
        source, available_parts=("base_plate",),
    )
    if key not in {part.part_id for part in physical}:
        raise ValueError(
            "BASE_FIXING_PLATE_NOT_AUTHORIZED_FOR_THIS_CABINET:"
            f" requested={key}; current="
            f"{tuple(part.part_id for part in physical)}"
        )
    return build_fixing_plate_source_render_data(key, snapshot=source)
