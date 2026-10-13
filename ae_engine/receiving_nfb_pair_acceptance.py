# -*- coding: utf-8 -*-
"""#1502: independently check one REAL inner-door/base NFB machining pair.

A pairing receipt is a PART_ONLY machining consistency check, not a signed
factory weld/ear-Z, PAD, whole-cabinet MFG-2 or CHECK/Q release. Both parts
must already have been constructed from the same source-verified NFBConfig.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from .receiving_nfb_base_process_projection import (
    NfbComposedActualBase, validate_nfb_base_part_cutting,
)
from .receiving_nfb_manufacturing_release import (
    NfbValidatedInnerDoorRender, VALIDATED,
)
from .receiving_nfb_y_projection import project_nfb_inner_door_nominal_y
from .sheetmetal_drawing import CirclePrimitive


_TOL = 1e-6


@dataclass(frozen=True)
class NfbDoorBasePairReceipt:
    inner_door_part_id: str
    base_plate_part_id: str
    source_sha256: str
    source_model: str
    nfb_owner_ids: tuple[str, ...]
    physical_part_count: int
    nfb_instance_count: int
    native_screw_cut_count: int
    approval_scope: str = "PAIR_PART_ONLY_EVIDENCE_NOT_WHOLE_MFG2"


def validate_nfb_door_base_pair(
    *, snapshot: Mapping[str, object],
    inner_door_id: str,
    verified_door: NfbValidatedInnerDoorRender,
    composed_base: NfbComposedActualBase,
) -> NfbDoorBasePairReceipt:
    """Cross-check the two independently built parts without authorizing assembly.

    Same SHA/model, exact hole owner set, actual inner-door manufacturing status,
    actual base FinalScene, row datum and native lower four screws per NFB are
    mandatory. A report cannot infer an ear weld Z or legitimate batch quantity.
    """
    if not isinstance(snapshot, Mapping) or not isinstance(inner_door_id, str):
        raise ValueError("NFB_PAIR_CURRENT_PHYSICAL_SNAPSHOT_REQUIRED")
    if not isinstance(verified_door, NfbValidatedInnerDoorRender):
        raise ValueError("NFB_PAIR_VERIFIED_INNER_DOOR_REQUIRED")
    if not isinstance(composed_base, NfbComposedActualBase):
        raise ValueError("NFB_PAIR_ACTUAL_BASE_REQUIRED")
    door_meta = getattr(verified_door.render_data, "metadata", {})
    if (verified_door.manufacturing_ready is not True
            or door_meta.get("nfb_trial_status") != VALIDATED
            or door_meta.get("nfb_trial_export_approved") is not True
            or not str(verified_door.part_id or "").strip()):
        raise ValueError("NFB_PAIR_INNER_DOOR_MFG1_NOT_VERIFIED")
    base = composed_base.render_data
    projected = composed_base.projection
    base_meta = getattr(base, "metadata", {})
    base_id = str(base_meta.get("stable_id") or "").strip()
    validate_nfb_base_part_cutting(base, physical_part_id=base_id)
    ids = tuple(verified_door.physical_hole_ids)
    observations = tuple(verified_door.verified_hole_locations)
    if (not ids or len(ids) != len(set(ids))
            or len(observations) != len(ids)
            or {row[0] for row in observations} != set(ids)
            or projected.owner_hole_ids != ids
            or tuple(base_meta.get("nfb_physical_hole_ids", ())) != ids
            or projected.physical_part_id != base_id
            or not base_id or base_id == verified_door.part_id):
        raise ValueError("NFB_PAIR_PHYSICAL_OWNER_OR_COUNT_MISMATCH")
    if (projected.source_sha256 != verified_door.source_sha256
            or base_meta.get("nfb_source_sha256") != verified_door.source_sha256
            or projected.source_model != verified_door.indexed_model_key[1]
            or base_meta.get("nfb_source_model") != projected.source_model
            or not str(door_meta.get("nfb_source_handle") or "").startswith(
                verified_door.source_sha256 + ":"
            )):
        raise ValueError("NFB_PAIR_ORIGINAL_SOURCE_MISMATCH")

    from .assembly_placement import resolve_inner_door_panel_placement
    actual_door = resolve_inner_door_panel_placement(snapshot, inner_door_id)
    if verified_door.part_id != actual_door.stable_id:
        raise ValueError("NFB_PAIR_REAL_INNER_DOOR_ID_MISMATCH")
    world_centers = []
    for row in observations:
        if (len(row) != 5 or type(row[1]) not in (int, float)
                or not isfinite(row[1]) or type(row[2]) is not int
                or type(row[3]) is not int or type(row[4]) is not int
                or row[4] not in (0, 90, 180, 270)):
            raise ValueError("NFB_PAIR_VERIFIED_HOLE_TRANSFORM_INVALID")
        ident, x, count, slot, _rotation = row
        projected_y = project_nfb_inner_door_nominal_y(
            snapshot, inner_door_id, layer_count=count, slot_index=slot,
        )
        if projected_y.part_id != verified_door.part_id:
            raise ValueError("NFB_PAIR_Y_OWNER_MISMATCH")
        world_centers.append((float(x), float(projected_y.box_world_y_mm)))
    expected_world = (
        (min(x for x, _ in world_centers)
         + max(x for x, _ in world_centers)) / 2.0,
        world_centers[0][1],
    )
    if any(abs(y - expected_world[1]) > _TOL for _, y in world_centers):
        raise ValueError("NFB_PAIR_MULTIPLE_INSTALLATION_ROWS_NOT_ONE_PLATE")
    try:
        observed_world = tuple(
            float(x) for x in base_meta["receiving_base_nfb_row_center_world_xy_mm"]
        )
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError("NFB_PAIR_ACTUAL_BASE_DATUM_MISSING") from exc
    if (len(observed_world) != 2
            or not all(isfinite(x) for x in observed_world)
            or any(abs(a-b) > _TOL for a, b in zip(expected_world, observed_world))):
        raise ValueError("NFB_PAIR_SOURCE_INSTALLATION_DATUM_MISMATCH")
    screws = tuple(p for p in base.scene.primitives
                   if isinstance(p, CirclePrimitive)
                   and p.layer == "CUTTING"
                   and p.source_type == "NFB_LOWER_NATIVE_FIXING_CIRCLE")
    if any(
        sum(str(p.source_id or "").startswith(owner + ":") for p in screws) != 4
        for owner in ids
    ) or len(screws) != 4 * len(ids):
        raise ValueError("NFB_PAIR_NATIVE_SCREW_Q_MISMATCH")
    # These are only the two explicitly evidenced physical pieces, not a
    # manufacturing equivalence group or an invented box-wide CHECK quantity.
    return NfbDoorBasePairReceipt(
        inner_door_part_id=verified_door.part_id,
        base_plate_part_id=base_id,
        source_sha256=verified_door.source_sha256,
        source_model=projected.source_model,
        nfb_owner_ids=ids,
        physical_part_count=2,
        nfb_instance_count=len(ids),
        native_screw_cut_count=len(screws),
    )
