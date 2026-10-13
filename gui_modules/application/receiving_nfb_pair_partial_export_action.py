# -*- coding: utf-8 -*-
"""#1502: one verified NFBConfig -> atomic inner-door + base PART_ONLY DXFs.

Use the existing original-source/actual-part validators and canonical
manufacturing writer. Never make a whole-cabinet release, invent ears/PAD,
or add shop-inapplicable bend compensation.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Mapping

from ae_engine.contracts import BasePlatePartSpec
from ae_engine.manufacturing_render_data import PartRenderData
from ae_engine.manufacturing_api import save_resolved_manufacturing_geometry_dxf
from ae_engine.manufacturing_export import receiving_instance_namespace
from ae_engine.receiving_nfb_manufacturing_release import (
    NfbConfiguredInnerDoorHole, configured_nfb_inner_door_render_data,
)
from ae_engine.receiving_nfb_pair_acceptance import (
    NfbDoorBasePairReceipt, validate_nfb_door_base_pair,
)
from ae_engine.receiving_nfb_transactions import _verify_hole_locations
from ae_engine.receiving_switch_model_catalog import INDEX_PATH
from ae_engine.receiving_nfb_ui1b_bridge import NfbVerifiedDraftSubmission

from .receiving_nfb_base_partial_export_action import (
    prepare_verified_receiving_nfb_base_plate,
)


@dataclass(frozen=True)
class NfbPairedPartOnlyDxf:
    inner_door_path: str
    base_plate_path: str
    receipt: NfbDoorBasePairReceipt
    inner_door_render_data: PartRenderData
    base_plate_render_data: PartRenderData
    source_path: str
    set_id: str
    bay_id: str
    version_id: str
    scope: str = "PAIR_PART_ONLY_NOT_WHOLE_CABINET"


def export_verified_receiving_nfb_door_base_pair(
    bundle: NfbVerifiedDraftSubmission, *,
    layout: Mapping[str, object],
    current_snapshot: Mapping[str, object],
    base_spec: BasePlatePartSpec,
    output_directory: str | Path,
    index_path: str | Path = INDEX_PATH,
    profile_path: str | Path | None = None,
) -> NfbPairedPartOnlyDxf:
    """Regenerate both physical FinalScenes before ONE atomic DXF commit.

    The two parts share current model, source, submitted physical hole IDs,
    world X, Y and rotations. The EAR mount and NFB screws stay independent.
    Check/Q for the whole batch must be separately approved; do not infer it
    from the number of source circles.
    """
    composed, original_pair, panel, profile = prepare_verified_receiving_nfb_base_plate(
        bundle, layout=layout, current_snapshot=current_snapshot,
        base_spec=base_spec, index_path=index_path, profile_path=profile_path,
    )
    try:
        bay = layout["sets"][bundle.set_index]["bays"][bundle.bay_index]
        holes = tuple(NfbConfiguredInnerDoorHole(
            physical_hole_id=item["physical_hole_id"],
            world_x_mm=item["manual_x_mm"],
            layer_count=item["layer_count"],
            slot_index=item["slot_index"],
            rotation_deg=item["rotation_deg"],
        ) for item in bay["nfb_config"]["holes"])
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ValueError("NFB_PAIR_SAVED_CURRENT_HOLES_REQUIRED") from exc
    if not holes:
        raise ValueError("NFB_PAIR_SAVED_CURRENT_HOLES_REQUIRED")
    door = configured_nfb_inner_door_render_data(
        current_snapshot, panel.inner_door_id, holes=holes,
        index_path=index_path, source_path=bundle.source_path, profile=profile,
    )
    _verify_hole_locations(bay["nfb_config"], door)
    # The independently regenerated MFG-1 FinalScene MUST be the exact proof
    # that the real Base Plate consumed. No cached READY indicator can replace it.
    if (door.part_id != original_pair.inner_door_part_id
            or door.indexed_model_key != bundle.verified_door.indexed_model_key
            or door.source_sha256 != original_pair.source_sha256
            or door.physical_hole_ids != original_pair.nfb_owner_ids
            or door.verified_hole_locations != bundle.verified_door.verified_hole_locations):
        raise ValueError("NFB_PAIR_REBUILT_DOOR_DIFFERS_FROM_BASE_SOURCE")
    receipt = validate_nfb_door_base_pair(
        snapshot=current_snapshot, inner_door_id=panel.inner_door_id,
        verified_door=door, composed_base=composed,
    )
    if receipt != original_pair or receipt.approval_scope != (
        "PAIR_PART_ONLY_EVIDENCE_NOT_WHOLE_MFG2"
    ):
        raise ValueError("NFB_PAIR_REBUILT_RECEIPT_MISMATCH")
    root = Path(output_directory)
    if not root.is_dir():
        raise ValueError("NFB pair destination must already be a directory")
    # Pair-only marker requests a real staged reopen of the door, in addition
    # to the writer's existing mandatory Base Plate staged DXF roundtrip.
    door_render = replace(
        door.render_data,
        metadata={
            **dict(door.render_data.metadata),
            "nfb_pair_roundtrip_required": True,
        },
    )
    resolved = SimpleNamespace(parts=(
        SimpleNamespace(part_key=door.part_id, render_data=door_render),
        SimpleNamespace(part_key=receipt.base_plate_part_id,
                        render_data=composed.render_data),
    ))
    paths = save_resolved_manufacturing_geometry_dxf(
        resolved, root, overwrite=False, part_only=True,
        instance_namespace=receiving_instance_namespace(
            set_id=bundle.scope.set_id, bay_id=bundle.scope.bay_id,
        ),
    )
    if set(paths) != {receipt.inner_door_part_id, receipt.base_plate_part_id}:
        raise ValueError("NFB_PAIR_ATOMIC_WRITER_PART_INVENTORY_MISMATCH")
    return NfbPairedPartOnlyDxf(
        inner_door_path=paths[receipt.inner_door_part_id],
        base_plate_path=paths[receipt.base_plate_part_id],
        receipt=receipt,
        inner_door_render_data=door_render,
        base_plate_render_data=composed.render_data,
        source_path=str(bundle.source_path),
        set_id=bundle.scope.set_id,
        bay_id=bundle.scope.bay_id,
        version_id=bundle.scope.version_id,
    )
