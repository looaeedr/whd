# -*- coding: utf-8 -*-
"""#1498: derive NFB manufacturing dependencies per physical part and Bay/version.

No manual approval registry or UI feature flag can manufacture holes. Only
actual source inventory and the #1497 source-verified inner-door result count.
UNCONFIGURED leaves the legacy exporter untouched. A submitted configuration
blocks ONLY the physically affected pieces, preserving unrelated output.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .receiving_nfb_dxf_source import NfbSourceInventory
from .receiving_nfb_manufacturing_release import (
    NfbValidatedInnerDoorRender, VALIDATED,
)

LEGACY = "UNCONFIGURED_LEGACY"
READY = "READY"
BLOCKED = "BLOCKED"
UNAFFECTED = "UNAFFECTED"


@dataclass(frozen=True)
class NfbPhysicalScope:
    set_id: str
    bay_id: str
    version_id: str
    submitted: bool
    inner_door_part_id: str
    base_plate_part_ids: tuple[str, ...] = ()
    middle_plate_part_ids: tuple[str, ...] = ()

    def __post_init__(self):
        if not all(isinstance(v, str) and v.strip()
                   for v in (self.set_id, self.bay_id, self.version_id,
                             self.inner_door_part_id)):
            raise ValueError("NFB Set/Bay/version/inner-door identifiers required")
        if type(self.submitted) is not bool:
            raise ValueError("NFB submitted must be a recorded boolean")
        ids = (self.inner_door_part_id, *self.base_plate_part_ids,
               *self.middle_plate_part_ids)
        if any(not isinstance(v, str) or not v.strip() for v in ids):
            raise ValueError("NFB physical part IDs cannot be empty")
        if len(ids) != len(set(ids)):
            raise ValueError("NFB physical part role/ID collision")

    @property
    def identity(self) -> tuple[str, str, str]:
        return self.set_id, self.bay_id, self.version_id


@dataclass(frozen=True)
class NfbQuantityPhysicalScope(NfbPhysicalScope):
    """Quantity versions have no Set/Bay owner; do not invent those identities.

    Reuses the physical manifest contract with an explicit absent Set/Bay.
    The actual QuantityModel version and physical part IDs remain authority.
    An unconfigured version without an inner door may have no inner-door ID.
    """
    def __post_init__(self):
        if self.set_id is not None or self.bay_id is not None:
            raise ValueError("NFB quantity scope cannot fabricate Set/Bay identity")
        if not isinstance(self.version_id, str) or not self.version_id.strip():
            raise ValueError("NFB quantity version identity required")
        if type(self.submitted) is not bool:
            raise ValueError("NFB quantity submitted fact must be boolean")
        ids = (*((self.inner_door_part_id,) if self.inner_door_part_id is not None else ()),
               *self.base_plate_part_ids, *self.middle_plate_part_ids)
        if (any(not isinstance(v, str) or not v.strip() for v in ids)
                or len(ids) != len(set(ids))):
            raise ValueError("NFB quantity physical part identities invalid")


@dataclass(frozen=True)
class NfbPartDecision:
    part_id: str
    status: str
    reasons: tuple[str, ...]

    @property
    def can_export(self) -> bool:
        return self.status != BLOCKED


@dataclass(frozen=True)
class NfbScopeReadiness:
    scope: NfbPhysicalScope
    decisions: tuple[NfbPartDecision, ...]
    scope_reasons: tuple[str, ...] = ()

    @property
    def can_submit(self) -> bool:
        # MFG-1 can commit verified INNER-DOOR NFB configuration while MFG-2
        # base/middle plates remain individually BLOCKED from fabrication.
        # Gate the submitted hole owner + resolved part dependencies, rather
        # than making every Color150 model permanently uncommittable.
        # A configured MFG-1 inner door can be submitted once its own real
        # source+part proof is READY. Missing independent MFG-2 base/middle
        # identities remain scope_reasons and continue to block *whole*
        # manufacturing export via filter_export_part_ids; never invent IDs.
        return (bool(self.decisions)
                and self.decisions[0].part_id == self.scope.inner_door_part_id
                and self.decisions[0].status == READY)

    def for_part(self, part_id: str) -> NfbPartDecision:
        matches = [row for row in self.decisions if row.part_id == part_id]
        if not matches:
            return NfbPartDecision(part_id, UNAFFECTED, ())
        if len(matches) != 1:
            raise ValueError("NFB physical part scope has duplicate identity")
        return matches[0]

    def filter_export_part_ids(
        self, part_ids: Sequence[str], *, partial: bool = False,
    ) -> tuple[tuple[str, ...], tuple[NfbPartDecision, ...]]:
        """Gate before any DXF IO; partial manifests never claim whole scope READY."""
        requested = tuple(part_ids)
        if len(requested) != len(set(requested)):
            raise ValueError("duplicate physical part ID in NFB export request")
        blockers = tuple(self.for_part(p) for p in requested
                         if not self.for_part(p).can_export)
        if self.scope.submitted and self.scope_reasons and not partial:
            raise ValueError("NFB scope physical dependencies unresolved: "
                             + ",".join(self.scope_reasons))
        if blockers and not partial:
            raise ValueError("NFB affected part is not manufacturing-ready: "
                             + ",".join(row.part_id for row in blockers))
        allowed = tuple(p for p in requested if self.for_part(p).can_export)
        return allowed, blockers


def _source_colors(inventory: NfbSourceInventory | None):
    """Never interpret missing, unreadable or ambiguous source as zero holes."""
    if inventory is None:
        return None
    if not isinstance(inventory, NfbSourceInventory):
        raise TypeError("NFB source must be an actual DXF source inventory")
    if inventory.diagnostics or inventory.unresolved_color_entities:
        return None
    counts = dict(inventory.process_aci_entity_counts)
    if any(type(counts.get(color)) is not int or counts[color] < 0
           for color in (30, 150, 212)):
        return None
    return counts


def derive_nfb_part_readiness(
    scope: NfbPhysicalScope,
    *,
    source_inventory: NfbSourceInventory | None = None,
    verified_inner_door: NfbValidatedInnerDoorRender | None = None,
) -> NfbScopeReadiness:
    """Build a scope-specific, immutable capability matrix from product evidence.

    MFG-2 plate output has no certified adapter yet: a real Color30/212 base
    dependency or Color150 middle dependency is blocked until that physical
    part has its own verified machining path. This does not disable other
    pieces or duplicate #1497 geometry. No unsupported imaginary part is made.
    """
    if not isinstance(scope, NfbPhysicalScope):
        raise TypeError("NFB physical scope required")
    parts = (scope.inner_door_part_id, *scope.base_plate_part_ids,
             *scope.middle_plate_part_ids)
    if not scope.submitted:
        return NfbScopeReadiness(
            scope=scope, decisions=tuple(NfbPartDecision(p, LEGACY, ())
                                         for p in parts),
        )
    colors = _source_colors(source_inventory)
    reasons: list[str] = []
    inner_valid = (colors is not None and colors[150] > 0
                   and isinstance(verified_inner_door, NfbValidatedInnerDoorRender)
                   and verified_inner_door.manufacturing_ready is True
                   and verified_inner_door.part_id == scope.inner_door_part_id
                   and verified_inner_door.source_sha256
                       == source_inventory.source_sha256
                   and len(verified_inner_door.physical_hole_ids) > 0
                   and bool(verified_inner_door.indexed_model_key[0])
                   and bool(verified_inner_door.indexed_model_key[1])
                   and getattr(verified_inner_door.render_data,
                               "metadata", {}).get("nfb_trial_status") == VALIDATED
                   and getattr(verified_inner_door.render_data,
                               "metadata", {}).get("nfb_trial_export_approved") is True)
    rows = [NfbPartDecision(
        scope.inner_door_part_id, READY if inner_valid else BLOCKED,
        () if inner_valid else ("INNER_DOOR_SOURCE_OR_CUTTING_NOT_VERIFIED",),
    )]
    # Color150 in the verified upper NFB source is the INNER-DOOR opening.
    # It does not prove that an additional physical NFB "middle plate"
    # exists. Preserve the historic guard when the current physical scope
    # explicitly includes a real middle part, but never invent one merely
    # from a source color or an illustrative base-plate drawing.
    if colors is None:
        base_needed = True
        middle_needed = bool(scope.middle_plate_part_ids)
    else:
        base_needed = colors[30] > 0 or colors[212] > 0
        middle_needed = bool(scope.middle_plate_part_ids) and colors[150] > 0
    if base_needed and not scope.base_plate_part_ids:
        reasons.append("BASE_PLATE_PHYSICAL_ID_UNRESOLVED")
    for part in scope.base_plate_part_ids:
        rows.append(NfbPartDecision(
            part, BLOCKED if base_needed else UNAFFECTED,
            ("BASE_PLATE_NFB_PROCESS_UNVERIFIED",) if base_needed else (),
        ))
    for part in scope.middle_plate_part_ids:
        rows.append(NfbPartDecision(
            part, BLOCKED if middle_needed else UNAFFECTED,
            ("MIDDLE_PLATE_NFB_COLOR150_UNVERIFIED",) if middle_needed else (),
        ))
    if colors is None:
        reasons.append("NFB_SOURCE_COLOR_SCOPE_UNKNOWN")
    return NfbScopeReadiness(
        scope=scope, decisions=tuple(rows),
        scope_reasons=tuple(reasons),
    )
