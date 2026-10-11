# -*- coding: utf-8 -*-
"""#1501 independent physical-part readiness and partial-export manifest.

Only #1498's live source/part evidence authorizes NFB manufacturing.
A catalog, saved NFBConfig or preview alone never certifies CUTTING.
Parts are supplied by the physical scene with stable IDs and actual counts.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Mapping, Sequence

from .receiving_nfb_part_readiness import (
    BLOCKED, READY, LEGACY, UNAFFECTED, NfbPhysicalScope,
    derive_nfb_part_readiness,
)
from .receiving_nfb_dxf_source import NfbSourceInventory
from .receiving_nfb_manufacturing_release import NfbValidatedInnerDoorRender
from .receiving_nfb_persistence import normalize_nfb_saved_fields
from .receiving_nfb_transactions import _verify_hole_locations

INNER_DOOR="INNER_DOOR"
BASE_PLATE="BASE_PLATE"
MIDDLE_PLATE="MIDDLE_PLATE"
OTHER="OTHER"
ROLES=frozenset({INNER_DOOR,BASE_PLATE,MIDDLE_PLATE,OTHER})


@dataclass(frozen=True)
class NfbActualPart:
    """One actual physical part, never a virtual count or guessed identity."""
    part_id: str
    role: str
    count: int = 1

    def __post_init__(self):
        if not isinstance(self.part_id,str) or not self.part_id.strip():
            raise ValueError("NFB manifest requires a real physical stable ID")
        if self.role not in ROLES:
            raise ValueError("NFB manifest role must come from a physical part")
        if type(self.count) is not int or self.count<=0:
            raise ValueError("NFB physical count must be a positive integer")


@dataclass(frozen=True)
class NfbManifestRow:
    set_id: str
    bay_id: str
    version_id: str
    part_id: str
    role: str
    status: str
    reasons: tuple[str,...]
    actual_count: int
    may_export: bool


@dataclass(frozen=True)
class NfbPartialExportManifest:
    scope: NfbPhysicalScope
    rows: tuple[NfbManifestRow,...]
    unresolved_dependencies: tuple[str,...]
    nfb_config_submitted: bool
    whole_ready: bool

    @property
    def authorized_part_ids(self):
        return tuple(row.part_id for row in self.rows if row.may_export)

    @property
    def held_rows(self):
        return tuple(row for row in self.rows if not row.may_export)

    @property
    def actual_export_count(self):
        return sum(row.actual_count for row in self.rows if row.may_export)

    @property
    def held_actual_count(self):
        return sum(row.actual_count for row in self.rows if not row.may_export)

    @property
    def partial_only(self):
        return self.nfb_config_submitted and not self.whole_ready

    def require_export(self,part_ids:Sequence[str],*,partial=False):
        """Gate before any DXF IO; never skip blocked pieces in full export."""
        requested=tuple(part_ids)
        if len(set(requested))!=len(requested):
            raise ValueError("NFB partial export request repeats physical part")
        if self.nfb_config_submitted and not partial and not self.whole_ready:
            raise ValueError("NFB whole manufacturing not ready; partial only")
        known={r.part_id:r for r in self.rows}
        for part in requested:
            if part not in known:
                raise ValueError("NFB export part not in current physical scene")
            if not known[part].may_export:
                raise ValueError("NFB requested physical part BLOCKED: "+part)
        return requested

    def report(self):
        """Report only; never serialize an approved manufacturing flag."""
        return {
            "set_id":self.scope.set_id,
            "bay_id":self.scope.bay_id,
            "version_id":self.scope.version_id,
            "nfb_config_submitted":self.nfb_config_submitted,
            "whole_ready":self.whole_ready,
            "partial_only":self.partial_only,
            "authorized_part_ids":list(self.authorized_part_ids),
            "actual_export_count":self.actual_export_count,
            "held_actual_count":self.held_actual_count,
            "unresolved_dependencies":list(self.unresolved_dependencies),
            "assembly_status":"NOT_VALIDATED_AS_COMPLETE_NFB_ASSEMBLY",
            "deferred_assembly":["PAD","EAR_ATTACHMENT"] if self.nfb_config_submitted else [],
            "rows":[{
                "part_id":r.part_id,"role":r.role,"status":r.status,
                "actual_count":r.actual_count,"may_export":r.may_export,
                "reasons":list(r.reasons),
            } for r in self.rows],
        }


def derive_nfb_partial_export_manifest(
    *,scope:NfbPhysicalScope,actual_parts:Sequence[NfbActualPart],
    saved_bay:Mapping[str,object],
    set_brand:str|None=None,
    source_inventory:NfbSourceInventory|None=None,
    verified_inner_door:NfbValidatedInnerDoorRender|None=None,
    source_path:str|Path|None=None,
    proven_unaffected_part_ids:Sequence[str]=(),
)->NfbPartialExportManifest:
    """Live scoped readiness; unresolved physical role is never guessed."""
    if not isinstance(scope,NfbPhysicalScope):
        raise TypeError("NFB actual physical scope required")
    if not isinstance(saved_bay,Mapping):
        raise TypeError("NFB actual saved Bay record required")
    raw=saved_bay.get("nfb_config_submitted",False)
    if type(raw) is not bool:
        raise ValueError("NFB submission fact must be a real boolean")
    submitted=raw is True
    if submitted:
        normalize_nfb_saved_fields(saved_bay)
        if not isinstance(set_brand,str) or not set_brand.strip():
            raise ValueError("NFB manifest needs the current Receiving Set brand")
    if saved_bay.get("stable_id")!=scope.bay_id:
        raise ValueError("NFB manifest Bay stable ID mismatch")
    if scope.submitted is not submitted:
        raise ValueError("NFB saved Bay and physical submitted fact disagree")
    observed=tuple(actual_parts)
    if any(not isinstance(p,NfbActualPart) for p in observed):
        raise TypeError("NFB manifest requires typed physical scene parts")
    ids=[p.part_id for p in observed]
    if len(ids)!=len(set(ids)):
        raise ValueError("NFB manifest has duplicate physical part identities")
    proven=tuple(proven_unaffected_part_ids)
    if len(proven)!=len(set(proven)) or any(p not in ids for p in proven):
        raise ValueError("NFB unrelated part proof must match the real scene")
    if any(next(x for x in observed if x.part_id==p).role!=OTHER for p in proven):
        raise ValueError("NFB unrelated proof may only cover OTHER parts")
    if not submitted:
        return NfbPartialExportManifest(
            scope,tuple(NfbManifestRow(
                *scope.identity,p.part_id,p.role,LEGACY,(),p.count,True
            ) for p in observed),(),False,True,
        )
    source_fresh=False
    if (source_path is not None and
            isinstance(source_inventory,NfbSourceInventory)):
        try:
            source_fresh=(sha256(Path(source_path).read_bytes()).hexdigest()
                          ==source_inventory.source_sha256)
        except (OSError,ValueError):
            source_fresh=False
    # Reconcile the *CURRENT SAVED* NFBConfig with the original manufactured
    # world-X, Y/layer, rotation, ID and model. A previously valid render
    # cannot approve a later edited config with identical DXF bytes.
    config_matching=False
    if source_fresh and isinstance(verified_inner_door,NfbValidatedInnerDoorRender):
        try:
            holes=saved_bay["nfb_config"]["holes"]
            profile_key=verified_inner_door.indexed_model_key
            if (profile_key[0]!=set_brand or
                    {h["model_filename"] for h in holes}!={profile_key[1]}):
                raise ValueError("NFB submitted brand/model differs from source")
            _verify_hole_locations(saved_bay["nfb_config"],verified_inner_door)
            config_matching=True
        except (ValueError,KeyError,TypeError,IndexError):
            config_matching=False
    readiness=derive_nfb_part_readiness(
        scope,source_inventory=source_inventory if source_fresh else None,
        verified_inner_door=(verified_inner_door
                             if source_fresh and config_matching else None),
    )
    declared={
        INNER_DOOR:{scope.inner_door_part_id},
        BASE_PLATE:set(scope.base_plate_part_ids),
        MIDDLE_PLATE:set(scope.middle_plate_part_ids),
    }
    rows=[]
    for part in observed:
        if part.role==OTHER:
            ok=part.part_id in proven
            status=UNAFFECTED if ok else BLOCKED
            reasons=() if ok else ("OTHER_PART_UNAFFECTED_OWNER_NOT_VERIFIED",)
        elif part.part_id not in declared[part.role]:
            status=BLOCKED
            reasons=(part.role+"_PHYSICAL_ROLE_OR_ID_UNRESOLVED",)
        else:
            decision=readiness.for_part(part.part_id)
            status=decision.status
            reasons=decision.reasons
        rows.append(NfbManifestRow(
            *scope.identity,part.part_id,part.role,status,reasons,
            part.count,status in (READY,UNAFFECTED),
        ))
    observed_ids=set(ids)
    missing=tuple(pid for values in declared.values()
                  for pid in values if pid not in observed_ids)
    unresolved=tuple(dict.fromkeys((
        *((("ORIGINAL_NFB_DXF_MISSING_OR_SHA_CHANGED",) if not source_fresh else ())),
        *((("SAVED_NFBCONFIG_DIFFERS_FROM_VERIFIED_CUTTING",)
           if source_fresh and not config_matching else ())),
        *readiness.scope_reasons,
        *(("REQUIRED_PART_NOT_IN_SCENE:"+pid) for pid in missing),
    )))
    whole=not unresolved and all(row.may_export for row in rows)
    return NfbPartialExportManifest(scope,tuple(rows),unresolved,True,whole)
