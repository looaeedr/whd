# -*- coding: utf-8 -*-
"""#1502: real paired PART_ONLY DXFs -> existing CHECK/Q grouping, no new math.

A caller supplies the actual QuantityModel piece count for each exported
Set/Bay/version. This gate reopens both REAL DXFs and validates their source
and typed paired receipt before calling existing quantity/geometry grouping.
It never authorizes EAR/PAD, whole MFG-2 or fabricated panel counts.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Mapping

from ae_engine.manufacturing_equivalence import ManufacturingParameters
from ae_engine.manufacturing_quantity import PhysicalPartDemand
from ae_engine.manufacturing_verification import verify_saved_part_render_data_dxf
from ae_engine.receiving_nfb_export_manifest import (
    BASE_PLATE, INNER_DOOR, NfbManifestRow, NfbPartialExportManifest,
)
from ae_engine.receiving_nfb_part_readiness import NfbPhysicalScope, READY
from ae_engine.receiving_nfb_quantity_gate import (
    NfbQuantityPartGate, gate_nfb_quantity_physical_demands,
)
from .receiving_nfb_pair_partial_export_action import NfbPairedPartOnlyDxf


@dataclass(frozen=True)
class NfbPairedQuantityInput:
    pair: NfbPairedPartOnlyDxf
    piece_count: int
    inner_door_parameters: ManufacturingParameters
    base_plate_parameters: ManufacturingParameters


@dataclass(frozen=True)
class NfbPairedQuantityCheck:
    gate: NfbQuantityPartGate
    groups: tuple
    scope: str = "PAIR_PART_ONLY_CHECK_Q_NOT_WHOLE_MFG2"

    @property
    def actual_piece_count(self) -> int:
        return self.gate.permitted_total_pieces


def group_reopened_nfb_pair_check_q(
    inputs: tuple[NfbPairedQuantityInput, ...],
) -> NfbPairedQuantityCheck:
    """Count only source-current, DXF-reopened inner-door/base pair parts.

    Physical identity is the real Set/Bay/version triple. Group keys are
    delegated to manufacturing_equivalence, which compares actual CUTTING,
    MARKING, BEND, material and parameters rather than filename/source SHA.
    """
    inputs = tuple(inputs)
    if not inputs:
        raise ValueError("NFB_CHECK_Q_NO_VERIFIED_PHYSICAL_PAIR")
    seen_scopes = set()
    seen_files = set()
    demands = []
    manifests = []
    parameters = {}
    for row in inputs:
        if not isinstance(row, NfbPairedQuantityInput):
            raise TypeError("NFB_CHECK_Q_TYPED_PAIRED_INPUT_REQUIRED")
        pair = row.pair
        if not isinstance(pair, NfbPairedPartOnlyDxf):
            raise TypeError("NFB_CHECK_Q_REAL_PAIRED_EXPORT_REQUIRED")
        if (type(row.piece_count) is not int or row.piece_count < 1):
            raise ValueError("NFB_CHECK_Q_QUANTITY_MUST_BE_POSITIVE")
        if (not isinstance(row.inner_door_parameters, ManufacturingParameters)
                or not isinstance(row.base_plate_parameters, ManufacturingParameters)):
            raise TypeError("NFB_CHECK_Q_EXPLICIT_MATERIAL_PROCESS_REQUIRED")
        if pair.scope != "PAIR_PART_ONLY_NOT_WHOLE_CABINET":
            raise ValueError("NFB_CHECK_Q_NOT_PART_ONLY")
        receipt = pair.receipt
        if (receipt.approval_scope != "PAIR_PART_ONLY_EVIDENCE_NOT_WHOLE_MFG2"
                or receipt.physical_part_count != 2
                or not receipt.nfb_owner_ids
                or receipt.nfb_instance_count != len(receipt.nfb_owner_ids)
                or receipt.native_screw_cut_count != 4 * receipt.nfb_instance_count
                or receipt.inner_door_part_id == receipt.base_plate_part_id):
            raise ValueError("NFB_CHECK_Q_INVALID_PHYSICAL_PAIR_RECEIPT")
        original_scope = (pair.set_id, pair.bay_id, pair.version_id)
        if (any(not isinstance(x,str) or not x.strip() for x in original_scope)
                or original_scope in seen_scopes):
            raise ValueError("NFB_CHECK_Q_DUPLICATE_OR_INVALID_SET_BAY_VERSION")
        seen_scopes.add(original_scope)
        # Encode the full real identity rather than flattening same-named
        # 'base_plate' from two different Bays into one demand owner.
        scoped_version = json.dumps(original_scope, ensure_ascii=False, separators=(",", ":"))
        if (not Path(pair.source_path).is_file()
                or sha256(Path(pair.source_path).read_bytes()).hexdigest()
                != receipt.source_sha256):
            raise ValueError("NFB_CHECK_Q_ORIGINAL_SOURCE_EDITED_REVERIFY_PAIR")
        door_meta = pair.inner_door_render_data.metadata if isinstance(pair.inner_door_render_data.metadata, Mapping) else {}
        base_meta = pair.base_plate_render_data.metadata if isinstance(pair.base_plate_render_data.metadata, Mapping) else {}
        if (door_meta.get("nfb_source_sha256") != receipt.source_sha256
                or base_meta.get("nfb_source_sha256") != receipt.source_sha256
                or door_meta.get("nfb_indexed_model") != receipt.source_model
                or base_meta.get("nfb_source_model") != receipt.source_model
                or tuple(door_meta.get("nfb_physical_hole_ids", ())) != receipt.nfb_owner_ids
                or tuple(base_meta.get("nfb_physical_hole_ids", ())) != receipt.nfb_owner_ids):
            raise ValueError("NFB_CHECK_Q_PAIR_OWNER_SOURCE_MISMATCH")
        scope = NfbPhysicalScope(
            pair.set_id, pair.bay_id, scoped_version, True,
            receipt.inner_door_part_id,
            base_plate_part_ids=(receipt.base_plate_part_id,),
        )
        rows = []
        for part_id, role, path, render, param in (
            (receipt.inner_door_part_id, INNER_DOOR, pair.inner_door_path,
             pair.inner_door_render_data, row.inner_door_parameters),
            (receipt.base_plate_part_id, BASE_PLATE, pair.base_plate_path,
             pair.base_plate_render_data, row.base_plate_parameters),
        ):
            filename = os.path.normcase(str(Path(path).resolve()))
            if filename in seen_files:
                raise ValueError("NFB_CHECK_Q_REPEATED_DXF_PHYSICAL_PART")
            seen_files.add(filename)
            if not Path(path).is_file():
                raise ValueError("NFB_CHECK_Q_PAIRED_DXF_MISSING")
            reopened = verify_saved_part_render_data_dxf(render, path)
            if not reopened.ok:
                raise ValueError("NFB_CHECK_Q_PAIRED_DXF_CHANGED_SINCE_ACCEPTANCE")
            rows.append(NfbManifestRow(
                pair.set_id, pair.bay_id, scoped_version, part_id,
                role, READY, (), 1, True,
            ))
            demands.append(PhysicalPartDemand(
                scoped_version, part_id, part_id,
                row.piece_count, 1, render,
            ))
            parameters[(scoped_version, part_id)] = param
        # Both actual sheets are valid PART_ONLY; whole cabinet remains
        # unresolved and cannot be inferred from this signed pair receipt.
        manifests.append(NfbPartialExportManifest(
            scope, tuple(rows), ("EAR_PAD_ASSEMBLY_NOT_RELEASED",), True, False,
        ))
    gate = gate_nfb_quantity_physical_demands(
        tuple(demands), manifests=tuple(manifests), partial=True,
    )
    if len(gate.permitted) != 2 * len(inputs) or gate.held:
        raise ValueError("NFB_CHECK_Q_PAIRED_PHYSICAL_COUNT_NOT_CONSERVED")
    groups = gate.group_checked(parameters)
    if sum(g.quantity for g in groups) != 2 * sum(x.piece_count for x in inputs):
        raise ValueError("NFB_CHECK_Q_GROUP_QUANTITY_NOT_CONSERVED")
    return NfbPairedQuantityCheck(gate=gate, groups=groups)


def save_checked_reopened_nfb_pair_q_dxf(
    checked: NfbPairedQuantityCheck, output_directory,
):
    """Write Q DXF for this already verified paired PART_ONLY selection.

    Opt in to PART_ONLY only after the genuine current DXF reopen + quantity
    gate has completed. Do not change the existing full CHECK default.
    """
    if (not isinstance(checked, NfbPairedQuantityCheck)
            or checked.scope != "PAIR_PART_ONLY_CHECK_Q_NOT_WHOLE_MFG2"
            or not checked.gate.partial_only or checked.gate.held
            or checked.actual_piece_count < 2):
        raise ValueError("NFB_CHECK_Q_NOT_VERIFIED_PAIRED_PART_ONLY")
    if sum(g.quantity for g in checked.groups) != checked.actual_piece_count:
        raise ValueError("NFB_CHECK_Q_GROUP_COUNT_CHANGED")
    from ae_engine.manufacturing_api import save_quantity_manufacturing_groups_dxf
    return save_quantity_manufacturing_groups_dxf(
        checked.groups, output_directory, part_only=True, overwrite=False,
    )
