# -*- coding: utf-8 -*-
"""#2517: Engine-owned physical source/navigation projections for Fold Designer.

None of these operator 2D/navigation projections author or certify a DXF.
Existing Receiving NFB/physical-part source owners decide source eligibility;
Tk/workspace adapters only submit snapshot/features and apply the returned rows.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass
from types import MappingProxyType

from .cabinet_types.policy import canonical_family_name
from .sheetmetal_part_adapters import derive_door_layout_cells, door_layout_part_key


@dataclass(frozen=True)
class OperatorBaseNavigationIdentity:
    source_parts: tuple[str, ...]
    receiving_single_base: bool
    receiving_two_tier: bool
    preserve_navigation_root: bool


def project_operator_base_navigation_identity(snapshot, source_parts=()):
    """Preserve original single BasePlate; real submitted NFB tiers replace its 2D root."""
    data = dict(snapshot or {})
    original = tuple(source_parts)
    receiving = canonical_family_name(data) == "受電箱"
    nfb = data.get("nfb_config")
    two_tier = bool(receiving and data.get("nfb_config_submitted") is True
                    and isinstance(nfb, Mapping) and nfb.get("layer_count") == 2)
    if receiving and data.get("nfb_config_submitted") is True and "base_plate" not in original:
        from .receiving_base_plate_config import receiving_base_plate_values
        try:
            physical = receiving_base_plate_values(data)
        except (ValueError, TypeError, KeyError):
            physical = None
        if physical is not None:
            original += ("base_plate",)
    return OperatorBaseNavigationIdentity(
        source_parts=original, receiving_single_base=receiving,
        receiving_two_tier=two_tier, preserve_navigation_root=receiving and not two_tier,
    )


def _display_number(value, default):
    """Original phase6 operator decimal fallback; NOT a manufacturing tolerance."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def project_operator_multidoor_base_plate_dimensions(snapshot):
    """Return per-Vault Door-cell BasePlate dimensions from the existing cell topology.

    Receiving uses one physical source BasePlate (or exactly two qualified
    NFB tiers) and therefore receives no inferred per-Door-cell bottom plate.
    """
    data = dict(snapshot or {})
    if canonical_family_name(data) == "受電箱":
        return MappingProxyType({})
    columns = tuple(
        (float(row[0]), tuple(float(v) for v in row[1]))
        for row in tuple(data.get("door_layout_columns") or ())
    )
    if not columns:
        return MappingProxyType({})
    shrink_left = _display_number(data.get("base_plate_shrink_left", 55), 55)
    shrink_right = _display_number(data.get("base_plate_shrink_right", 55), 55)
    shrink_top = _display_number(data.get("base_plate_shrink_top", 55), 55)
    shrink_bottom = _display_number(data.get("base_plate_shrink_bottom", 55), 55)
    result = {}
    for cell in derive_door_layout_cells(columns):
        base_key = door_layout_part_key(cell).replace("door_", "base_plate_", 1)
        result[base_key] = MappingProxyType({
            "width": max(1.0, float(cell.start_width) - shrink_left - shrink_right),
            "height": max(1.0, float(cell.start_height) - shrink_top - shrink_bottom),
        })
    return MappingProxyType(result)


@dataclass(frozen=True)
class OperatorReceivingAuxiliaryNavigation:
    fixing_plate_profiles: Mapping
    nfb_tier_profiles: Mapping
    pad_profiles: Mapping


def project_operator_receiving_auxiliary_navigation(
    snapshot, *, available_parts=(), source_part_features=None, live_features=None,
):
    """Project actual EAR, tier BasePlate and PAD navigation from committed sources.

    The returned 2D fold profiles are previews only; do not grant new MFG2,
    external manufacturing, NFB/ear weld or unsourced PAD export capabilities.
    """
    data = dict(snapshot or {})
    from .receiving_base_fixing_plate import receiving_base_fixing_plate_previews
    fixing_previews = receiving_base_fixing_plate_previews(
        data, available_parts=available_parts,
    )
    fixing_profiles = {
        part.part_id: {
            "X": [{"len": part.nominal_source_outline_mm[0],
                   "phase6_key": "base_fixing_source_x"}],
            "Y": [{"len": part.nominal_source_outline_mm[1],
                   "phase6_key": "base_fixing_source_y"}],
        }
        for part in fixing_previews
    }

    tier_profiles = {}
    identity = project_operator_base_navigation_identity(
        data, tuple(data.get("existing_parts") or ()),
    )
    if identity.receiving_two_tier:
        from .receiving_nfb_base_assembly_xy import receiving_nfb_layer_centers
        from .receiving_base_plate_3d_profiles import receiving_base_plate_3d_profiles
        upper = tuple(
            row for row in tuple(data.get("inner_doors") or ())
            if isinstance(row, Mapping)
            and str(row.get("cell_key") or "").split(":")[-1] == "0"
            and str(row.get("stable_id") or "").strip()
        )
        if len(upper) == 1:
            try:
                centers = receiving_nfb_layer_centers(data, str(upper[0]["stable_id"]))
            except ValueError as exc:
                if str(exc) not in {
                    "RECEIVING_NFB_LAYER_SET_IDENTITY_DRIFT",
                    "RECEIVING_NFB_LAYER_BAY_IDENTITY_DRIFT",
                    "RECEIVING_NFB_LAYER_CONFIG_IDENTITY_DRIFT",
                }:
                    raise
                centers = ()
            if len(centers) == 2:
                profiles = receiving_base_plate_3d_profiles(data)
                if profiles is not None:
                    tier_profiles = {
                        center.layer_part_id: deepcopy(profiles)
                        for center in centers
                    }

    from .receiving_nfb_pad_operator_parts import committed_nfb_pad_draft_parts
    source_features = dict(source_part_features or {})
    runtime_features = dict(live_features or {})
    pad_source = {
        **data,
        "part_features": {
            **source_features,
            **{
                str(key): value for key, value in runtime_features.items()
                if isinstance(key, str) and isinstance(value, (tuple, list))
            },
        },
    }
    pad_parts = ()
    # Source snapshot wins over stale workspace on successful saved submission.
    for candidate_source in (data, pad_source):
        try:
            candidates = committed_nfb_pad_draft_parts(candidate_source)
        except (ValueError, TypeError, KeyError, OSError):
            continue
        if candidates:
            pad_parts = candidates
            break
    pad_profiles = {
        part.part_id: {
            "X": tuple(dict(row) for row in part.x_profile),
            "Y": tuple(dict(row) for row in part.y_profile),
        }
        for part in pad_parts
    }
    return OperatorReceivingAuxiliaryNavigation(
        fixing_plate_profiles=MappingProxyType(fixing_profiles),
        nfb_tier_profiles=MappingProxyType(tier_profiles),
        pad_profiles=MappingProxyType(pad_profiles),
    )


@dataclass(frozen=True)
class OperatorDerivedDividerInnerProfiles:
    """Resolved physical source for the part selector, without GUI ownership.

    Profile maps are fresh for each request; immutable top-level mappings
    prevent accidental replacement of physical parts by the workspace caller.
    """
    divider_profiles: Mapping[str, object]
    inner_profiles: Mapping[str, object]
    divider_part_ids: tuple[str, ...]
    inner_part_ids: tuple[str, ...]


def project_operator_derived_divider_inner_profiles(snapshot):
    """Derive Divider, InnerDoor frame and panel once from canonical Family.

    Preserve the historical order: frame IDs first, then panel IDs for the
    legacy sync return; the workspace profile map always adds panel first.
    Physical sizes, material lengths and topology remain in their original
    ae_engine family/part owners. No DXF or manufacturing release here.
    """
    from .cabinet_types import policy as family
    from .door_dividers import derive_box_body_dividers, divider_part_profiles
    from .inner_door_frames import (
        InnerDoorFrameSet, derive_all_inner_door_frames, inner_door_frame_part_profiles,
    )
    from .inner_door_panels import inner_door_panel_part_profiles

    data = dict(snapshot or {})
    divider_profiles = {}
    columns = list(data.get("door_layout_columns") or ())
    if bool(data.get("multi_door_enabled", False)) and columns:
        normalized_columns = tuple(
            (float(row[0]), tuple(float(value) for value in row[1]))
            for row in columns
        )
        dividers = derive_box_body_dividers(
            normalized_columns,
            depth=float(data.get("d", 0.0)),
            thickness=float(data.get("t", 0.0)),
            layout_scope=(str(data.get("door_layout_scope") or "main").strip() or "main"),
            handle_edges=dict(data.get("door_handle_edges") or {}),
            model_name=str(data.get("model") or "").strip() or None,
            frame_width=float(data.get("fw", 0.0)),
        )
        divider_profiles = divider_part_profiles(dividers)

    frame_sets = []
    if family.has_inner_door_frame_derivation(data):
        frame_sets.extend(family.derive_inner_door_frame_sets(data))
    else:
        # Legacy custom/Vault snapshots may persist explicit frame spans.
        thickness = float(data.get("t", 0.0))
        for item in list(data.get("inner_doors") or ()):
            if not isinstance(item, Mapping):
                continue
            spans = item.get("frame_spans")
            if not isinstance(spans, Mapping) or not spans:
                continue
            stable_id = str(item.get("stable_id") or "").strip()
            if not stable_id:
                continue
            included = tuple(
                str(side).strip().lower()
                for side in (item.get("included_frame_sides")
                             or ("top", "bottom", "left", "right"))
            )
            frame_sets.append(InnerDoorFrameSet(
                inner_door_id=stable_id, spans=dict(spans),
                thickness=thickness, included_sides=included,
            ))
    frames = derive_all_inner_door_frames(tuple(frame_sets))
    panels = family.derive_inner_door_panels(data)
    inner_profiles = inner_door_panel_part_profiles(panels)
    inner_profiles.update(inner_door_frame_part_profiles(frames))
    return OperatorDerivedDividerInnerProfiles(
        divider_profiles=MappingProxyType(divider_profiles),
        inner_profiles=MappingProxyType(inner_profiles),
        divider_part_ids=tuple(divider_profiles),
        inner_part_ids=tuple(
            [*(frame.stable_id for frame in frames),
             *(panel.stable_id for panel in panels)]
        ),
    )
