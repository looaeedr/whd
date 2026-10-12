# -*- coding: utf-8 -*-
"""#1498 versioned physical NFB manufacturing capability: W800x3 only.

This is a MACHINE-DERIVED witness, never a stored manual 'approved' flag.
A real saved Set/Bay/version and NFB exact-source/physical-part witness must
match the WHD 723-mm CUTTING, live W800 inner-door X, and actual 1100-mm top
cell Y rule. Other W/N combinations are BLOCKED, not guessed as W/2.
Existing #1498 individual part decisions remain authoritative for downstream
MFG-2 base/middle-plate holds and unrelated export paths.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .receiving_nfb_dxf_source import NfbSourceInventory
from .receiving_nfb_manufacturing_release import (
    NfbValidatedInnerDoorRender, X_REVISION,
)
from .receiving_nfb_part_readiness import (
    BLOCKED, LEGACY, READY, NfbPhysicalScope, derive_nfb_part_readiness,
)
from .receiving_nfb_x_projection import (
    W800_THREE_DATUM_REVISION, resolve_w800_three_whd_x,
)
from .receiving_nfb_y_projection import project_nfb_inner_door_nominal_y

CAPABILITY_SCHEMA = "WHD_NFB_W800_THREE_MANUFACTURING_CAPABILITY_V1"
CAPABILITY_RULE_REVISION = "WHD-NFB-CAPABILITY-W800X3-20261012-V1"


@dataclass(frozen=True)
class NfbManufacturingCapability:
    schema: str
    revision: str
    status: str
    scope_identity: tuple[str, str, str]
    physical_part_id: str
    bay_cell_width_mm: float | None
    blank_cutting_width_mm: float | None
    units_per_layer: int
    layer_count: int
    x_datum_revision: str | None
    y_datum_revision: str | None
    model_identity: tuple[str, str] | None
    source_sha256: str | None
    reasons: tuple[str, ...]

    @property
    def can_manufacture_nfb_inner_door(self) -> bool:
        return self.status == READY

    def report(self) -> dict[str, object]:
        """Stable, JSON-friendly machine acceptance for #1504 traceability."""
        return {
            "schema": self.schema,
            "revision": self.revision,
            "status": self.status,
            "scope": {
                "set_id": self.scope_identity[0],
                "bay_id": self.scope_identity[1],
                "version_id": self.scope_identity[2],
            },
            "physical_part_id": self.physical_part_id,
            "bay_cell_width_mm": self.bay_cell_width_mm,
            "blank_cutting_width_mm": self.blank_cutting_width_mm,
            "units_per_layer": self.units_per_layer,
            "layer_count": self.layer_count,
            "x_datum_revision": self.x_datum_revision,
            "y_datum_revision": self.y_datum_revision,
            "model_identity": (
                list(self.model_identity) if self.model_identity is not None else None
            ),
            "source_sha256": self.source_sha256,
            "reasons": list(self.reasons),
            "can_manufacture_nfb_inner_door": self.can_manufacture_nfb_inner_door,
        }


def derive_w800_three_nfb_capability(
    snapshot: Mapping[str, object],
    inner_door_id: str,
    *,
    scope: NfbPhysicalScope,
    source_inventory: NfbSourceInventory | None = None,
    verified_inner_door: NfbValidatedInnerDoorRender | None = None,
) -> NfbManufacturingCapability:
    """Verify actual 800x3 hole rows against independently derived WHD X/Y.

    This function performs NO DXF writes or project mutation. A typed object
    with 'manufacturing_ready' or a saved UI READY flag cannot substitute
    for source SHA + physical hole records + live 723 CUTTING + Y projection.
    """
    if not isinstance(snapshot, Mapping) or not isinstance(scope, NfbPhysicalScope):
        raise TypeError("NFB physical snapshot and typed manufacturing scope required")
    base = dict(
        schema=CAPABILITY_SCHEMA, revision=CAPABILITY_RULE_REVISION,
        scope_identity=scope.identity, physical_part_id=scope.inner_door_part_id,
        bay_cell_width_mm=None, blank_cutting_width_mm=None,
        units_per_layer=3, layer_count=0,
        x_datum_revision=None, y_datum_revision=None,
        model_identity=None, source_sha256=None,
    )
    if not scope.submitted:
        return NfbManufacturingCapability(
            status=LEGACY, reasons=("UNCONFIGURED_NO_NFB_CUTTING",), **base,
        )
    failed = []
    readiness = derive_nfb_part_readiness(
        scope, source_inventory=source_inventory,
        verified_inner_door=verified_inner_door,
    )
    if not readiness.can_submit:
        failed.append("NFB_SOURCE_OR_REAL_CUTTING_NOT_READY")
    x_sites = ()
    try:
        x_sites = tuple(resolve_w800_three_whd_x(
            snapshot, inner_door_id, slot_index=i,
        ) for i in range(3))
        if (len({x.part_id for x in x_sites}) != 1
                or x_sites[0].part_id != scope.inner_door_part_id
                or any(abs(x.unfolded_blank_width_mm - 723.) > 1e-6
                       or x.revision != W800_THREE_DATUM_REVISION
                       for x in x_sites)):
            raise ValueError("W800 actual CUTTING part/datum inconsistent")
    except (ValueError, TypeError, KeyError, IndexError):
        failed.append("W800_THREE_ACTUAL_723_CUTTING_X_UNVERIFIED")
    hole_locations = (
        verified_inner_door.verified_hole_locations
        if isinstance(verified_inner_door, NfbValidatedInnerDoorRender)
        else ()
    )
    layer_counts = {row[2] for row in hole_locations
                    if isinstance(row, tuple) and len(row) == 5
                    and type(row[2]) is int}
    layers = next(iter(layer_counts)) if len(layer_counts) == 1 else 0
    if layers not in (1, 2) or len(hole_locations) != 3 * layers:
        failed.append("W800_THREE_FULL_ROWS_NOT_VERIFIED")
    y_sites = ()
    if layers in (1, 2) and x_sites:
        try:
            y_sites = tuple(project_nfb_inner_door_nominal_y(
                snapshot, inner_door_id, layer_count=layers, slot_index=i,
            ) for i in range(layers))
            if (any(site.part_id != scope.inner_door_part_id for site in y_sites)
                    or len({site.revision for site in y_sites}) != 1):
                raise ValueError("NFB real Y physical part mismatch")
        except (ValueError, TypeError, KeyError, IndexError):
            failed.append("W800_THREE_UPPER_1100_Y_UNVERIFIED")
    if layers in (1, 2) and x_sites and y_sites:
        actual_x = sorted(x.box_world_x_mm for x in x_sites)
        for layer in range(layers):
            observed_x = sorted(float(r[1]) for r in hole_locations
                                if r[3] == layer)
            if (len(observed_x) != 3 or
                    any(abs(u - v) > 1e-6
                        for u, v in zip(observed_x, actual_x))):
                failed.append("W800_THREE_X_LOCATION_NOT_ON_ACTUAL_PART")
                break

    metadata = (
        getattr(verified_inner_door.render_data, "metadata", {})
        if isinstance(verified_inner_door, NfbValidatedInnerDoorRender)
        else {}
    )
    if (not isinstance(metadata, Mapping)
            or metadata.get("nfb_x_rule_revision") != X_REVISION
            or (y_sites and metadata.get("nfb_y_rule_revision")
                != y_sites[0].revision)):
        failed.append("NFB_MANUFACTURED_X_Y_RULE_VERSION_MISMATCH")
    if (not isinstance(verified_inner_door, NfbValidatedInnerDoorRender)
            or not isinstance(source_inventory, NfbSourceInventory)
            or verified_inner_door.source_sha256 != source_inventory.source_sha256):
        failed.append("NFB_EXACT_SOURCE_IDENTITY_UNVERIFIED")
    return NfbManufacturingCapability(
        status=BLOCKED if failed else READY,
        reasons=tuple(dict.fromkeys(failed)),
        **{
            **base,
            "bay_cell_width_mm": 800. if x_sites else None,
            "blank_cutting_width_mm": (
                x_sites[0].unfolded_blank_width_mm if x_sites else None
            ),
            "layer_count": layers,
            "x_datum_revision": W800_THREE_DATUM_REVISION if x_sites else None,
            "y_datum_revision": y_sites[0].revision if y_sites else None,
            "model_identity": (
                verified_inner_door.indexed_model_key
                if isinstance(verified_inner_door, NfbValidatedInnerDoorRender)
                else None
            ),
            "source_sha256": (
                verified_inner_door.source_sha256
                if isinstance(verified_inner_door, NfbValidatedInnerDoorRender)
                else None
            ),
        },
    )
