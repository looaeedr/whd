# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

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
        if type(partial) is not bool:
            raise TypeError("NFB partial export authorization must be explicit boolean")
        requested=tuple(part_ids)
        if len(set(requested))!=len(requested):
            raise ValueError("NFB partial export request repeats physical part")
        if self.nfb_config_submitted and not partial:
            # A typed caller can still supply inconsistent manifest flags.
            # Full export is NEVER authorized from an asserted whole_ready
            # flag while any physical part is held or a dependency unresolved.
            if (self.scope.submitted is not True
                    or self.whole_ready is not True
                    or self.unresolved_dependencies
                    or not self.rows
                    or any(row.may_export is not True
                           or row.status not in (READY, UNAFFECTED)
                           or type(row.actual_count) is not int
                           or row.actual_count < 1
                           for row in self.rows)):
                raise ValueError("NFB whole manufacturing not ready; partial only")
        known={r.part_id:r for r in self.rows}
        if len(known)!=len(self.rows):
            raise ValueError("NFB duplicate physical part BLOCKED in export manifest")
        # A typed manifest from a different Set/Bay/version or a changed
        # submission identity must not authorize DXF after preflight.
        if (self.scope.submitted is not self.nfb_config_submitted
                or any((row.set_id, row.bay_id, row.version_id)
                       != self.scope.identity for row in self.rows)):
            raise ValueError("NFB manifest physical owner BLOCKED: Set/Bay/version")
        for part in requested:
            if part not in known:
                raise ValueError("NFB export part not in current physical scene")
            row=known[part]
            if (part == self.scope.inner_door_part_id
                    and row.role != INNER_DOOR):
                raise ValueError("NFB requested physical part BLOCKED: inner-door role")
            # A forged typed report may carry a truthy integer/string or
            # inconsistent status. Neither is manufacturing authorization.
            # Preserve unconfigured historical LEGACY only for unsubmitted
            # scopes and unrelated proven UNAFFECTED physical parts.
            valid_status=(READY,UNAFFECTED) if self.nfb_config_submitted else (LEGACY,)
            if (row.may_export is not True or row.status not in valid_status
                    or type(row.actual_count) is not int or row.actual_count < 1):
                raise ValueError("NFB requested physical part BLOCKED: "+str(part))
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
    # A hash-current DXF inventory is not proof for a *different saved*
    # NFBConfig.  After model/X/layer/rotation changes or missing slots,
    # earlier Color30/150/212 zeros cannot exempt physical base/middle
    # plates: every dependent part must fail closed until a fresh matched
    # inner-door source and physical owner are proven.
    source_owner_current=source_fresh and config_matching
    readiness=derive_nfb_part_readiness(
        scope,source_inventory=(source_inventory if source_owner_current else None),
        verified_inner_door=(verified_inner_door
                             if source_owner_current else None),
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
