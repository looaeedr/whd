# -*- coding: utf-8 -*-
"""Immutable manufacturing cache-source plan owned by the headless Engine.

Receiving undo receipts may be kept only while the physical baseline source
and the active multipart BoxBody structure have unambiguous provenance.
No GUI/phase6 or Tk imports. This is a cache policy, not MFG release.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from .box_body_structure_state import (
    BoxBodyStructureType, normalize_box_body_structure_state,
)
from .cabinet_types.policy import canonical_family_name
from .contracts import BoxBodyPartSpec, EndCapPartSpec
from .manufacturing_baseline_policy import receiving_baseline_source_stamp


@dataclass(frozen=True)
class ManufacturingCacheSourcePlan:
    history_capacity: int
    witness_required: bool
    include_physical_panels: bool


def plan_manufacturing_cache_source(snapshot, workspace_structure=None):
    """Resolve exact old Receiving undo eligibility and physical DXF coverage.

    Unknown structure must NOT certify cached material; the GUI clears old
    receipts instead of silently retaining a prior 3-piece sheet.
    """
    eligible = (
        isinstance(snapshot, Mapping)
        and canonical_family_name(snapshot) == "受電箱"
        and snapshot.get("active_mode") == "set_bay"
    )
    if not eligible:
        return ManufacturingCacheSourcePlan(1, False, False)
    structure = workspace_structure
    if not structure and isinstance(snapshot.get("box_body_structure"), Mapping):
        structure = snapshot["box_body_structure"]
    active = (
        getattr(structure.get("active_type"), "value", structure.get("active_type"))
        if isinstance(structure, Mapping) else None
    )
    recognized = {kind.value for kind in BoxBodyStructureType}
    if active not in recognized:
        return ManufacturingCacheSourcePlan(2, False, False)
    return ManufacturingCacheSourcePlan(
        2, True,
        active == BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value,
    )


@dataclass(frozen=True)
class OperatorRawMaterialReusePlan:
    """Source-only eligibility for GUI bounded raw PartRenderData history."""

    eligible: bool
    source_stamp: tuple | None


def plan_operator_raw_material_reuse(spec, snapshot, *, context=None):
    """Decide physical Receiving source provenance without any GUI policy.

    Exact legacy BoxBody/EndCap raw eligibility is retained. The same three
    baseline sources used by canonical manufacturing must be witnessed. A
    dedicated side/back BoxBody additionally requires physical panel sources;
    EndCap must witness the actual original head/tail DXF. This plan never
    certifies a complete FinalScene, Joint/collision solution or external DXF.
    """
    raw_endcap = (
        isinstance(spec, EndCapPartSpec)
        and not spec.resolved_assembly_relief_cuts
        and spec.assembly_relief is None
    )
    eligible = (
        (isinstance(spec, BoxBodyPartSpec) or raw_endcap)
        and isinstance(snapshot, Mapping)
        and snapshot.get("model") == "受電箱"
        and snapshot.get("active_mode") == "set_bay"
        and str(spec.model_name) == "受電箱"
    )
    if not eligible:
        return OperatorRawMaterialReusePlan(False, None)

    structure = (
        spec.structure_state if isinstance(spec, BoxBodyPartSpec)
        else spec.box_body_structure_state
    )
    dedicated_three_piece = (
        normalize_box_body_structure_state(structure).get("active_type")
        == BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT.value
    )
    stamp = receiving_baseline_source_stamp(
        str(spec.model_name), context=context,
        include_physical_panels=dedicated_three_piece,
    )
    if raw_endcap and stamp is not None and not any(
        len(row) >= 2 and row[0] == "封頭尾.dxf" and row[1] is not None
        for row in stamp
    ):
        stamp = None
    return OperatorRawMaterialReusePlan(True, stamp)
