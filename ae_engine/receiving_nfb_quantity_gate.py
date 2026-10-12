# -*- coding: utf-8 -*-
"""#1501 CHECK physical eligibility before the existing geometry grouping.

Not a second grouping or exporter. Exact quantity-version/physical-part
rows in CURRENT source-verified NFB manifests are the only eligible demands.
Caller must freshly derive those manifests from source bytes, saved Bay and
physical geometry. Do not deserialize a manufactured READY project flag.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .manufacturing_equivalence import group_quantity_physical_demands
from .manufacturing_quantity import PhysicalPartDemand
from .receiving_nfb_export_manifest import NfbPartialExportManifest
from .receiving_nfb_part_readiness import BLOCKED, LEGACY, READY, UNAFFECTED


@dataclass(frozen=True)
class NfbQuantityPartGate:
    permitted: tuple[PhysicalPartDemand,...]
    held: tuple[PhysicalPartDemand,...]
    partial_only: bool

    @property
    def permitted_total_pieces(self) -> int:
        return sum(d.quantity for d in self.permitted)

    @property
    def held_total_pieces(self) -> int:
        return sum(d.quantity for d in self.held)

    def group_checked(self, parameters_by_source: Mapping):
        """Canonical geometry equivalence plus CHECK/Q quantity aggregation."""
        result=group_quantity_physical_demands(
            self.permitted,parameters_by_source,
        )
        if sum(g.quantity for g in result)!=self.permitted_total_pieces:
            raise ValueError("NFB CHECK group quantity not conserved")
        return result


def gate_nfb_quantity_physical_demands(
    demands: Sequence[PhysicalPartDemand],
    *,manifests:Sequence[NfbPartialExportManifest],
    partial:bool,
)->NfbQuantityPartGate:
    """No blocked/unknown/cross-Bay part enters CHECK/Q.

    Quantity demand lacks Set/Bay dimensions, so same physical ID in two
    different Bays of the same version is ambiguous: reject instead of
    choosing arbitrary ownership or falsely multiplying CHECK Q.
    """
    if type(partial) is not bool:
        raise TypeError("NFB partial export decision must be boolean")
    manifests=tuple(manifests)
    if not manifests:
        raise ValueError("NFB CHECK requires current physical scope manifest")
    owners={}
    observed_scopes=set()
    for manifest in manifests:
        if not isinstance(manifest,NfbPartialExportManifest):
            raise TypeError("NFB CHECK requires typed live scope manifest")
        scope=manifest.scope
        if (type(manifest.nfb_config_submitted) is not bool
                or scope.submitted is not manifest.nfb_config_submitted):
            raise ValueError("NFB CHECK manifest submitted fact mismatch")
        if scope.identity in observed_scopes:
            raise ValueError("NFB CHECK duplicate Set/Bay/version scope")
        observed_scopes.add(scope.identity)
        if not manifest.rows:
            raise ValueError("NFB CHECK manifest missing actual physical rows")
        if manifest.whole_ready and manifest.unresolved_dependencies:
            raise ValueError("NFB CHECK whole readiness conflicts with unresolved dependencies")
        if manifest.nfb_config_submitted and not partial and not manifest.whole_ready:
            raise ValueError("NFB whole CHECK not ready; partial only")
        for item in manifest.rows:
            if (item.set_id,item.bay_id,item.version_id)!=scope.identity:
                raise ValueError("NFB CHECK row Set/Bay/version identity mismatch")
            if type(item.actual_count) is not int or item.actual_count<=0:
                raise ValueError("NFB CHECK row actual physical count invalid")
            if type(item.may_export) is not bool:
                raise ValueError("NFB CHECK row export decision must be boolean")
            allowed_states=({READY,UNAFFECTED,BLOCKED}
                            if manifest.nfb_config_submitted else {LEGACY})
            if item.status not in allowed_states:
                raise ValueError("NFB CHECK row status conflicts with saved submission")
            if item.may_export is not (item.status in {READY,UNAFFECTED,LEGACY}):
                raise ValueError("NFB CHECK row export decision conflicts with status")
            if item.status==BLOCKED and not item.reasons:
                raise ValueError("NFB CHECK blocked row missing diagnostic reason")
            if manifest.whole_ready and not item.may_export:
                raise ValueError("NFB CHECK whole readiness contains held physical part")
            key=(scope.version_id,item.part_id)
            if key in owners:
                raise ValueError("NFB CHECK part ID ambiguous across Set/Bay")
            owners[key]=(manifest,item)
    seen=set()
    permitted=[]
    held=[]
    for demand in tuple(demands):
        if not isinstance(demand,PhysicalPartDemand):
            raise TypeError("NFB CHECK requires actual PhysicalPartDemand")
        key=(demand.version_id,demand.physical_id)
        if key in seen:
            raise ValueError("NFB CHECK duplicate physical part demand")
        seen.add(key)
        if key not in owners:
            raise ValueError("NFB CHECK demand missing scoped physical manifest")
        _,part=owners[key]
        if (type(demand.per_box_count) is not int
                or demand.per_box_count!=part.actual_count):
            raise ValueError("NFB CHECK physical count mismatch")
        if part.may_export:
            permitted.append(demand)
        else:
            held.append(demand)
    if held and not partial:
        raise ValueError("NFB full CHECK contains held pieces")
    if not permitted:
        raise ValueError("NFB CHECK has no authorized physical pieces")
    return NfbQuantityPartGate(
        permitted=tuple(permitted),held=tuple(held),
        partial_only=any(m.partial_only for m in manifests) or bool(held),
    )
