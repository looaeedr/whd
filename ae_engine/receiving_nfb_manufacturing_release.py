# -*- coding: utf-8 -*-
"""#1497 operator-configured, source-verified NFB inner-door manufacturing.

No extra owner-signoff registry. The source model is the original CSV
brand+filename; each model adds a fingerprinted DXF Color150 profile record,
not another geometry algorithm. X is an EXPLICIT configured box-world
coordinate, Y is the canonical 1100-upper-cell projection. The actual
inner-door panel and source contour supply manufacturing geometry.

The output is legal only for that fully resolved physical part and configured
set of holes. Missing source/coordinates or intersecting holes fail closed;
other independent models and parts are not blocked.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite
from pathlib import Path
import re
from typing import Mapping, Sequence

from .assembly_placement import resolve_inner_door_panel_placement
from .cabinet_types import policy as cabinet_family_policy
from .inner_door_panels import InnerDoorPanelPart
from .manufacturing_api import build_inner_door_panel_render_data, save_part_render_data_dxf
from .manufacturing_render_data import PartRenderData
from .receiving_nfb_legacy_feature_bridge import existing_inner_door_feature_finalscene
from .receiving_nfb_cutting_manufacturing import (
    NfbUpperSourceProfile, trial_nfb_upper_cutting_on_inner_door,
)
from .receiving_nfb_cutting_preflight import (
    NfbExistingCuttingClaim, NfbUpperOpeningRequest,
)
from .receiving_nfb_dxf_source import (
    inspect_nfb_dxf_source, resolve_upper_color150_reference,
)
from .receiving_nfb_index_sources import unique_nfb_dxfs_from_switch_index
from .receiving_nfb_y_projection import project_nfb_inner_door_nominal_y

X_REVISION = "WHD-RECEIVING-NFB-CONFIGURED-WORLD-X-V1"
VALIDATED = "CONFIGURED_NFB_INNER_DOOR_CUTTING_SOURCE_VERIFIED"


@dataclass(frozen=True)
class NfbConfiguredInnerDoorHole:
    """One operator-set hole: X is box WORLD X, not a guessed W/2."""
    physical_hole_id: str
    world_x_mm: float
    layer_count: int
    slot_index: int
    rotation_deg: int = 0


@dataclass(frozen=True)
class NfbValidatedInnerDoorRender:
    render_data: object
    part_id: str
    indexed_model_key: tuple[str, str]
    source_sha256: str
    physical_hole_ids: tuple[str, ...]
    manufacturing_ready: bool = True
    # Binds the actual measured/verified machining result to operator X/Y,
    # not just an easily reused stable-hole label.
    verified_hole_locations: tuple[tuple[str, float, int, int, int], ...] = ()


def _validate_source_path(source_path: str | Path, profile: NfbUpperSourceProfile) -> Path:
    """(1) download suffix is innocuous ONLY with the exact known byte SHA.

    The operator CSV filename is never changed to match attachment filenames.
    Arbitrarily named or differently fingerprinted sources cannot be aliased.
    """
    source = Path(source_path)
    if not source.is_file():
        raise ValueError("NFB indexed DXF source missing")
    indexed = profile.indexed_filename
    if not indexed.lower().endswith(".dxf"):
        raise ValueError("NFB indexed model must be a DXF filename")
    escaped = re.escape(Path(indexed).stem)
    equivalent_download_name = re.fullmatch(
        escaped + r"\([1-9][0-9]*\)\.dxf", source.name, re.IGNORECASE,
    )
    if source.name.casefold() != indexed.casefold() and not equivalent_download_name:
        raise ValueError("NFB source filename does not match indexed model")
    return source


def _resolve_physical_panel(snapshot: Mapping[str, object], inner_door_id: str):
    state = dict(snapshot or {})
    if state.get("model") != "受電箱" or not state.get("multi_door_enabled"):
        raise ValueError("NFB manufacturing requires configured Receiving inner door")
    parts = [p for p in cabinet_family_policy.derive_inner_door_panels(state)
             if p.inner_door_id == inner_door_id]
    if len(parts) != 1:
        raise ValueError("NFB manufacturing needs one unambiguous inner-door part")
    panel = parts[0]
    placement = resolve_inner_door_panel_placement(state, inner_door_id)
    if (placement.stable_id != panel.stable_id
            or placement.anchor != f"inner_door_frame_opening:{inner_door_id}"
            or tuple(placement.rotation) != (0.0, 0.0, 0.0)):
        raise ValueError("NFB physical part/placement mapping mismatch")
    built = build_inner_door_panel_render_data(panel)
    if built.unfolded_topology is None or built.unfolded_topology.piece_id != panel.stable_id:
        raise ValueError("NFB physical inner-door topology unresolved")
    return panel, placement


def configured_nfb_inner_door_render_data(
    snapshot: Mapping[str, object],
    inner_door_id: str,
    *,
    holes: Sequence[NfbConfiguredInnerDoorHole],
    index_path: str | Path,
    source_path: str | Path,
    profile: NfbUpperSourceProfile,
    existing_claims: Sequence[NfbExistingCuttingClaim] = (),
    existing_render_data: PartRenderData | None = None,
) -> NfbValidatedInnerDoorRender:
    """Materialize source-verified Color150 into that configured door FinalScene.

    This function never invents an unprovided absolute X: callers must save
    the operator's box-world X as part of their NFB configuration. Original
    source SHA, upper handle, part/core, Y topology, Q16 atomic collisions and
    existing CUTTING ownership are checked before any production file write.
    """
    entries = tuple(holes)
    if not entries:
        raise ValueError("NFB configured manufacturing requires at least one hole")
    catalog = unique_nfb_dxfs_from_switch_index(index_path)
    if catalog.diagnostics:
        raise ValueError("NFB switch index has invalid source mappings")
    models = [v for v in catalog.sources if
              v.brand == profile.brand and
              v.filename.casefold() == profile.indexed_filename.casefold()]
    if len(models) != 1:
        raise ValueError("NFB model absent or ambiguous in operator switch index")

    source = _validate_source_path(source_path, profile)
    inventory = inspect_nfb_dxf_source(source)
    if inventory.source_sha256 != profile.source_sha256:
        raise ValueError("NFB original DXF SHA differs from indexed source profile")
    ref = resolve_upper_color150_reference(
        inventory,
        upper_source_entity_ids=(f"{inventory.source_sha256}:{profile.upper_handle}",),
    )
    if (abs(ref.size_mm[0] - profile.upper_size_mm[0]) > 1e-5
            or abs(ref.size_mm[1] - profile.upper_size_mm[1]) > 1e-5):
        raise ValueError("NFB upper source Color150 size mismatch")

    panel, placement = _resolve_physical_panel(snapshot, inner_door_id)
    # Consume the ACTUAL same-panel Hole Editor Feature store. Never silently
    # regenerate an empty inner door when already-authored legacy holes exist.
    existing_render_data = existing_inner_door_feature_finalscene(
        snapshot, panel, existing_render_data=existing_render_data,
    )
    core_width = panel.unfolded_width - panel.fold_left - panel.fold_right
    if core_width <= 0:
        raise ValueError("NFB inner-door has invalid fold/core X topology")
    requests = []
    for hole in entries:
        if not isinstance(hole, NfbConfiguredInnerDoorHole):
            raise TypeError("NFB configured hole must use the typed physical model")
        if (type(hole.world_x_mm) not in (int, float)
                or not isfinite(float(hole.world_x_mm))):
            raise ValueError("NFB configured box-world X is missing/invalid")
        world_x = float(hole.world_x_mm)
        relative_x = world_x - float(placement.world_offset[0])
        uv_x = panel.fold_left + core_width / 2.0 + relative_x
        recovered_world = float(placement.world_offset[0]) + (
            uv_x - panel.fold_left - core_width / 2.0
        )
        if abs(recovered_world - world_x) > 1e-7:
            raise ValueError("NFB box-world-to-inner-door-X round-trip mismatch")
        projected_y = project_nfb_inner_door_nominal_y(
            snapshot, inner_door_id,
            layer_count=hole.layer_count, slot_index=hole.slot_index,
        )
        if projected_y.part_id != panel.stable_id or projected_y.cell_key != panel.cell_key:
            raise ValueError("NFB nominal Y projected to wrong physical inner-door part")
        requests.append(NfbUpperOpeningRequest(
            physical_hole_id=hole.physical_hole_id,
            target_part_id=panel.stable_id,
            source_sha256=ref.source_sha256,
            source_handle=profile.upper_handle,
            source_region="UPPER",
            source_aci=150,
            source_outline_xy=ref.source_outline_vertices_xy,
            source_center_xy=ref.center_xy,
            source_profile_closed=True,
            source_bulges=(0.0,) * len(ref.source_outline_vertices_xy),
            rotation_deg=hole.rotation_deg,
            uv_center_x=uv_x,
            uv_center_y=projected_y.unfolded_uv_y_mm,
            x_rule_revision=X_REVISION,
            y_rule_revision=projected_y.revision,
            model_filename=profile.indexed_filename,
        ))
    trial = trial_nfb_upper_cutting_on_inner_door(
        panel, tuple(requests), catalog=catalog, inventory=inventory,
        profile=profile, existing_claims=existing_claims,
        existing_render_data=existing_render_data,
    )
    if trial.manufacturing_ready:
        raise ValueError("NFB manufacturing path improperly bypassed trial contract")
    ready = replace(
        trial.render_data,
        metadata={
            **dict(trial.render_data.metadata),
            "nfb_trial_status": VALIDATED,
            "nfb_trial_export_approved": True,
            "nfb_indexed_source_path": str(source),
            "nfb_index_sha256": catalog.index_sha256,
            "nfb_source_handle": ref.source_entity_id,
            "nfb_physical_hole_ids": tuple(h.physical_hole_id for h in entries),
            "nfb_x_rule_revision": X_REVISION,
            "nfb_y_rule_revision": requests[0].y_rule_revision,
        },
    )
    return NfbValidatedInnerDoorRender(
        render_data=ready, part_id=panel.stable_id,
        indexed_model_key=(profile.brand, profile.indexed_filename),
        source_sha256=inventory.source_sha256,
        physical_hole_ids=tuple(h.physical_hole_id for h in entries),
        verified_hole_locations=tuple(
            (h.physical_hole_id, float(h.world_x_mm),
             h.layer_count, h.slot_index, h.rotation_deg) for h in entries
        ),
    )


def save_configured_nfb_inner_door_dxf(
    snapshot: Mapping[str, object],
    inner_door_id: str,
    output_path: str | Path,
    *,
    holes: Sequence[NfbConfiguredInnerDoorHole],
    index_path: str | Path,
    source_path: str | Path,
    profile: NfbUpperSourceProfile,
    existing_claims: Sequence[NfbExistingCuttingClaim] = (),
    existing_render_data: PartRenderData | None = None,
    overwrite: bool = False,
) -> str:
    """Canonical export, only after the actual source and all holes validate."""
    ready = configured_nfb_inner_door_render_data(
        snapshot, inner_door_id, holes=holes, index_path=index_path,
        source_path=source_path, profile=profile, existing_claims=existing_claims,
        existing_render_data=existing_render_data,
    )
    return save_part_render_data_dxf(
        ready.render_data, output_path, overwrite=overwrite,
    )
