# -*- coding: utf-8 -*-
"""#1500: UI-1A transient slot draft -> source-verified #1497/#1498 MFG-1.

Never reinterpret UI-1A's tentative X OFFSET as manufacturing WORLD X.
The caller supplies explicit world X coordinates + physical datum evidence,
original indexed DXF path, source profile and actual panel scope. Missing or
unsupported source/model/part/scope fails before an NFBConfig submission fact
is created. Only #1500's canonical atomic transaction can save the result.
"""
from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
from typing import Mapping

from .receiving_nfb_ui1a import effective_nfb_slot_brand
from .receiving_nfb_ui1a_edits import editable_nfb_draft, effective_nfb_rotation
from .receiving_nfb_dxf_source import inspect_nfb_dxf_source, NfbSourceInventory
from .receiving_nfb_cutting_manufacturing import NfbUpperSourceProfile
from .receiving_nfb_manufacturing_release import (
    NfbConfiguredInnerDoorHole, NfbValidatedInnerDoorRender,
    configured_nfb_inner_door_render_data,
)
from .receiving_nfb_part_readiness import NfbPhysicalScope, NfbScopeReadiness, derive_nfb_part_readiness
from .receiving_nfb_persistence import normalize_nfb_config


@dataclass(frozen=True)
class NfbVerifiedDraftSubmission:
    set_index: int
    bay_index: int
    version_id: str
    config: dict
    scope: NfbPhysicalScope
    source_inventory: NfbSourceInventory
    verified_door: NfbValidatedInnerDoorRender
    readiness: NfbScopeReadiness
    source_path: str
    snapshot_at_verification: dict
    bay_at_verification: dict
    config_sha256_at_verification: str | None = None  # old read-only export receipts only

    @property
    def can_submit(self):
        return self.readiness.can_submit

    @property
    def reasons(self):
        blocked = [p for p in self.readiness.decisions
                   if p.part_id == self.scope.inner_door_part_id and not p.can_export]
        return tuple(self.readiness.scope_reasons) + tuple(
            reason for part in blocked for reason in part.reasons
        )

    @property
    def held_parts(self):
        return tuple(p.part_id for p in self.readiness.decisions
                     if p.part_id != self.scope.inner_door_part_id and not p.can_export)


def _nfb_config_proof_sha256(config: Mapping[str, object]) -> str:
    """Canonical digest of ALL saved NFBConfig values, not just physical X.

    A frozen dataclass can still contain mutable dicts: changing offsets,
    follow/overwrite settings or source model after stage must invalidate
    that transient proof before the canonical #1500 transaction.
    """
    value = normalize_nfb_config(config)
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def _world_coordinate(value, unit_id):
    if type(value) not in (int, float) or not isfinite(float(value)):
        raise ValueError(f"NFB {unit_id} requires an explicit finite WORLD X; not a draft X offset")
    return float(value)


def _active_slots(draft, *, profile):
    layers = draft["layers"][:draft["layer_count"]]
    result = []
    for layer_index, layer in enumerate(layers):
        for unit in layer["slots"]:
            if unit["filename"] is None:
                continue  # an empty physical slot is not a hole
            brand = effective_nfb_slot_brand(draft, layer_index,
                                              layer["slots"].index(unit))
            if (brand != profile.brand or unit["source_brand"] != brand
                    or unit["filename"].casefold() != profile.indexed_filename.casefold()):
                raise ValueError("NFB draft model/brand is not supported by the verified source profile")
            result.append((layer_index, unit))
    if not result:
        raise ValueError("NFB cannot commit an empty physical opening selection")
    ids = [unit["unit_id"] for _,unit in result]
    if len(set(ids))!=len(ids):
        raise ValueError("NFB physical unit IDs must be unique")
    return tuple(result)


def verify_nfb_ui1a_for_submit(
    draft: Mapping[str,object],
    *, layout: Mapping[str,object],
    set_index: int,
    bay_index: int,
    version_id: str,
    snapshot: Mapping[str,object],
    inner_door_id: str,
    physical_scope: NfbPhysicalScope,
    world_x_by_unit: Mapping[str,float],
    datum_revision: str,
    datum_snapshot: Mapping[str,object],
    index_path: str | Path,
    source_path: str | Path,
    profile: NfbUpperSourceProfile,
) -> NfbVerifiedDraftSubmission:
    """Return a real backend-verified bundle, or raise (without state write).

    Only one physical model/profile per Bay is supported by MFG-1's source
    verifier today. Multiple NFB models are allowed in the draft UI but cannot
    borrow a single-model source proof for their manufacturing submission.
    """
    state=editable_nfb_draft(draft)
    if (type(set_index) is not int or type(bay_index) is not int
            or not 0<=set_index<len(layout["sets"])
            or not 0<=bay_index<len(layout["sets"][set_index]["bays"])):
        raise ValueError("NFB current Set/Bay selection invalid")
    selected_set=layout["sets"][set_index]
    bay=selected_set["bays"][bay_index]
    if not isinstance(physical_scope,NfbPhysicalScope):
        raise TypeError("NFB physical scope evidence required")
    if (not isinstance(version_id,str) or not version_id.strip()
            or physical_scope.identity!=(selected_set["stable_id"],bay["stable_id"],version_id)
            or physical_scope.submitted is not True):
        raise ValueError("NFB manufacturing Set/Bay/version scope is not current")
    if state["set_brand"]!=selected_set["switch_brand"]:
        raise ValueError("NFB draft brand differs from the actual Receiving Set brand")
    if (not isinstance(datum_revision,str) or not datum_revision.strip()
            or not isinstance(datum_snapshot,Mapping) or not datum_snapshot):
        raise ValueError("NFB world X requires a measured physical datum revision/snapshot")
    if not isinstance(world_x_by_unit,Mapping):
        raise ValueError("NFB world-X coordinates must be explicit for every physical unit")
    entries=_active_slots(state,profile=profile)
    expected={unit["unit_id"] for _,unit in entries}
    if set(world_x_by_unit)!=expected:
        raise ValueError("NFB world-X inputs must match actual physical units exactly")
    holes=[]
    settings=[]
    for layer_index,unit in entries:
        uid=unit["unit_id"]
        world=_world_coordinate(world_x_by_unit[uid],uid)
        stable=f"nfb:{selected_set['stable_id']}:{bay['stable_id']}:{uid}"
        # Nominal center-to-center pitch and draft X offsets must NEVER be
        # passed to NfbConfiguredInnerDoorHole as an absolute WORLD X.
        hole=NfbConfiguredInnerDoorHole(
            physical_hole_id=stable,world_x_mm=world,
            layer_count=state["layer_count"],slot_index=layer_index,
            rotation_deg=effective_nfb_rotation(state,layer_index,
                                                 state["layers"][layer_index]["slots"].index(unit)),
        )
        holes.append(hole)
        settings.append({
            "physical_hole_id":stable,
            "unit_id":uid,
            "model_filename":unit["filename"],
            "slot_index":layer_index,
            "layer_count":state["layer_count"],
            "rotation_deg":hole.rotation_deg,
            "manual_x_state":"CONFIRMED",
            "manual_x_mm":world,
            "datum_revision":datum_revision,
            "datum_snapshot":dict(datum_snapshot),
            "operator_offset_mm":unit.get("manual_x_mm"),
            "brand_mode":unit["brand"]["mode"],
            "source_brand":unit["source_brand"],
        })
    # Genuine MFG-1 checks source index, exact byte SHA, chosen Color150 UPPER
    # geometry, physical inner-door core / fold and actual Y projection.
    verified=configured_nfb_inner_door_render_data(
        snapshot,inner_door_id,holes=tuple(holes),index_path=index_path,
        source_path=source_path,profile=profile,
    )
    if verified.part_id!=physical_scope.inner_door_part_id:
        raise ValueError("NFB actual inner-door ID not the requested physical part")
    source=inspect_nfb_dxf_source(source_path)
    if (source.source_sha256!=profile.source_sha256
            or verified.source_sha256!=source.source_sha256):
        raise ValueError("NFB model source hash not bound to current source proof")
    readiness=derive_nfb_part_readiness(
        physical_scope,source_inventory=source,verified_inner_door=verified,
    )
    if not readiness.can_submit:
        raise ValueError("NFB scope/source/physical part is not ready: "
                         + ",".join(readiness.scope_reasons
                                    or tuple(r for p in readiness.decisions
                                             for r in p.reasons)))
    config=normalize_nfb_config({
        "layer_count":state["layer_count"],
        "holes":settings,
        "source_sha256":source.source_sha256,
        "datum_revision":datum_revision,
    })
    return NfbVerifiedDraftSubmission(
        set_index=set_index,bay_index=bay_index,version_id=version_id,
        config=config,scope=physical_scope,source_inventory=source,
        verified_door=verified,readiness=readiness,
        source_path=str(source_path),
        snapshot_at_verification=deepcopy(dict(snapshot)),
        bay_at_verification=deepcopy(dict(bay)),
        config_sha256_at_verification=_nfb_config_proof_sha256(config),
    )


def assert_live_verified_nfb(adapter, bundle: NfbVerifiedDraftSubmission,
                             *, current_snapshot):
    """Verify the staged proof still matches source bytes, panel and Bay."""
    if not isinstance(bundle,NfbVerifiedDraftSubmission):
        raise TypeError("NFB submit needs the real source-verified UI-1A bundle")
    if _nfb_config_proof_sha256(bundle.config) != bundle.config_sha256_at_verification:
        raise ValueError("NFB staged config changed since physical verification; reverify")
    layout=adapter.layout
    try:
        row=layout["sets"][bundle.set_index]
        bay=row["bays"][bundle.bay_index]
    except (KeyError,IndexError,TypeError) as exc:
        raise ValueError("NFB submit Set/Bay no longer exists") from exc
    if (row["stable_id"]!=bundle.scope.set_id or
            bay["stable_id"]!=bundle.scope.bay_id or
            bay!=bundle.bay_at_verification):
        raise ValueError("NFB submit Bay has changed since actual source verification")
    if dict(current_snapshot)!=bundle.snapshot_at_verification:
        raise ValueError("NFB submit real inner-door geometry has changed; reverify")
    try:
        source_sha=sha256(Path(bundle.source_path).read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError("NFB source DXF missing since verification") from exc
    if source_sha!=bundle.source_inventory.source_sha256:
        raise ValueError("NFB original source DXF changed since verification")
    if not bundle.can_submit:
        raise ValueError("NFB physical scope is not manufacturing-ready")
    return True


def submit_live_verified_nfb(adapter, bundle: NfbVerifiedDraftSubmission,
                             *, current_snapshot, confirm):
    """Atomically save via existing #1500 Receiving transaction; no bypass."""
    assert_live_verified_nfb(adapter,bundle,current_snapshot=current_snapshot)
    return adapter.submit_nfb_to_bays(
        set_index=bundle.set_index,bay_indices=(bundle.bay_index,),
        version_id=bundle.version_id,configs={bundle.bay_index:bundle.config},
        evidence={bundle.bay_index:(
            bundle.scope,bundle.source_inventory,bundle.verified_door,
        )},confirm=confirm,
    )


def copy_live_verified_nfb(adapter, *, source_bay_index: int,
                           target_bundle: NfbVerifiedDraftSubmission,
                           current_snapshot, confirm):
    """Copy a submitted NFB Bay to a separately verified physical target.

    Only the source's model/layout/rotation and its chosen offsets are
    eligible for deep copy. The destination's independent world-X, physical
    IDs and datum are taken from a real MFG-1 source+part verification,
    never reused from the source. All changes remain atomic/cancellable.
    """
    assert_live_verified_nfb(
        adapter,target_bundle,current_snapshot=current_snapshot,
    )
    layout=adapter.layout
    row=layout["sets"][target_bundle.set_index]
    if (type(source_bay_index) is not int
            or not 0<=source_bay_index<len(row["bays"])
            or source_bay_index==target_bundle.bay_index):
        raise ValueError("NFB copy requires distinct source and target real Bays")
    source=row["bays"][source_bay_index]
    if source.get("nfb_config_submitted") is not True:
        raise ValueError("NFB copy source is UNCONFIGURED")
    # The canonical transaction verifies deep-copy identity and target's
    # live physical evidence again; never synthesize an approved target.
    return adapter.copy_submitted_nfb_to_bay(
        set_index=target_bundle.set_index,
        source_bay_index=source_bay_index,
        target_bay_index=target_bundle.bay_index,
        version_id=target_bundle.version_id,
        target_config=target_bundle.config,
        evidence=(target_bundle.scope,target_bundle.source_inventory,
                  target_bundle.verified_door),
        confirm=confirm,
    )
