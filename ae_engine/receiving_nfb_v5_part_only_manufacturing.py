# -*- coding: utf-8 -*-
"""#1502: narrowly verified CSV V5 *one physical Base Plate* production DXF.

The source of switch holes is current committed NFBConfig + per-brand numeric
CSV, NEVER a legacy NFB DXF/Handle. An independently verified plate blank may
be written without granting full-cabinet, welded fixing-plate or PAD release.
Generic/direct trial DXF paths remain blocked; this entry reconstructs and
checks the actual scene before serializing it atomically.
"""
from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Mapping

from .contracts import BasePlatePartSpec
from .dxf_serialization import save_scene_dxf
from .manufacturing_api import build_part_render_data
from .manufacturing_equivalence import ManufacturingParameters
from .manufacturing_export import (
    _atomic_commit_staged_dxfs, resolved_physical_dxf_filename,
)
from .manufacturing_verification import verify_saved_part_render_data_dxf
from .receiving_base_plate_config import receiving_base_plate_values
from .receiving_nfb_base_assembly_xy import receiving_nfb_layer_centers
from .receiving_nfb_model_identity import parse_numeric_model_ref
from .receiving_nfb_v5_check_q_preview import (
    CsvV5BaseCheckDemand, check_csv_v5_base_part_only_groups,
)
from .receiving_nfb_v5_configured_inner_door import (
    NfbV5ConfiguredInnerDoorHole, trial_configured_nfb_v5_inner_door_render_data,
)
from .receiving_nfb_v5_live_base_preview import (
    preview_v5_on_existing_receiving_base,
)


@dataclass(frozen=True)
class VerifiedCsvBasePartOnlyOutput:
    part_id: str
    path: str
    source_hole_ids: tuple[str, ...]
    quantity: int
    check_q_key: str


def _current_single_tier_csv_holes(snapshot, inner_door_id):
    """Read actual submitted Set/Bay; horizontal slot != vertical tier."""
    if (not isinstance(snapshot, Mapping)
            or snapshot.get("nfb_config_submitted") is not True):
        raise ValueError("CSV_BASE_EXPORT_REQUIRES_SUBMITTED_NFB_CONFIG")
    centers = receiving_nfb_layer_centers(snapshot, inner_door_id)
    if len(centers) != 1 or centers[0].layer_index != 0:
        raise ValueError("CSV_BASE_EXPORT_ONLY_ONE_ACTUAL_TIER")
    if centers[0].verified_world_x_mm is None:
        raise ValueError("CSV_BASE_EXPORT_NFB_WORLD_X_NOT_CONFIRMED")
    layout = snapshot.get("receiving_layout")
    selected = snapshot.get("_receiving_runtime_selection")
    if not isinstance(layout, Mapping) or not isinstance(selected, Mapping):
        raise ValueError("CSV_BASE_EXPORT_ACTIVE_SET_BAY_REQUIRED")
    sets = layout.get("sets")
    si, bi = selected.get("set_index"), selected.get("bay_index")
    if (not isinstance(sets, (tuple, list))
            or type(si) is not int or not 0 <= si < len(sets)
            or not isinstance(sets[si], Mapping)
            or sets[si].get("stable_id") != selected.get("set_id")):
        raise ValueError("CSV_BASE_EXPORT_SET_IDENTITY_DRIFT")
    bays = sets[si].get("bays")
    if (not isinstance(bays, (tuple, list))
            or type(bi) is not int or not 0 <= bi < len(bays)
            or not isinstance(bays[bi], Mapping)
            or bays[bi].get("stable_id") != selected.get("bay_id")):
        raise ValueError("CSV_BASE_EXPORT_BAY_IDENTITY_DRIFT")
    bay = bays[bi]
    config = bay.get("nfb_config")
    if (bay.get("nfb_config_submitted") is not True
            or config != snapshot.get("nfb_config")
            or not isinstance(config, Mapping)
            or config.get("layer_count") != 1):
        raise ValueError("CSV_BASE_EXPORT_COMMITTED_OWNER_CHANGED")
    rows = config.get("holes")
    if not isinstance(rows, (tuple, list)) or not rows:
        raise ValueError("CSV_BASE_EXPORT_NO_COMMITTED_HOLES")
    entries = []
    seen = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("CSV_BASE_EXPORT_INVALID_HOLE")
        model = row.get("model_filename")
        brand = row.get("source_brand")
        parsed = parse_numeric_model_ref(model)
        x = row.get("manual_x_mm")
        hole_id = row.get("physical_hole_id")
        layer = row.get("layer_index", 0)
        if (parsed is None or parsed[0] != brand
                or not isinstance(hole_id, str) or not hole_id
                or hole_id in seen
                or row.get("manual_x_state") != "CONFIRMED"
                or type(x) not in (float, int) or not isfinite(float(x))
                or layer != 0 or row.get("layer_count", 1) != 1
                or not isinstance(row.get("datum_revision"), str)
                or not row["datum_revision"].strip()
                or not isinstance(row.get("datum_snapshot"), Mapping)
                or not row["datum_snapshot"]
                or type(row.get("rotation_deg", 0)) is not int
                or row.get("rotation_deg", 0) not in (0, 90, 180, 270)):
            raise ValueError("CSV_BASE_EXPORT_COMMITTED_NFB_SOURCE_OR_X_INVALID")
        seen.add(hole_id)
        entries.append(NfbV5ConfiguredInnerDoorHole(
            physical_hole_id=hole_id, brand=brand, model_ref=model,
            world_x_mm=float(x), layer_count=1, slot_index=0,
            rotation_deg=row.get("rotation_deg", 0),
        ))
    return tuple(entries), str(selected["set_id"]), str(selected["bay_id"])


def _require_source_derived_real_plate(snapshot, base_spec):
    """Exact source PartSpec, native EAR slots and BEND remain authoritative."""
    if not isinstance(base_spec, BasePlatePartSpec) or base_spec.physical_id != "base_plate":
        raise ValueError("CSV_BASE_EXPORT_REQUIRES_ONE_ORIGINAL_BASE_PLATE")
    values = receiving_base_plate_values(snapshot)
    if values is None:
        raise ValueError("CSV_BASE_EXPORT_PHYSICAL_SOURCE_UNRESOLVED")
    expected = {
        "width": float(snapshot["w"]), "height": values["h"],
        "thickness": float(snapshot["t"]),
        "shrink_top": values["base_plate_shrink_top"],
        "shrink_bottom": values["base_plate_shrink_bottom"],
        "shrink_left": values["base_plate_shrink_left"],
        "shrink_right": values["base_plate_shrink_right"],
        "bend": values["base_plate_bend"],
    }
    if (base_spec.receiving_bend_pattern != values["receiving_bend_pattern"]
            or str(base_spec.model_name or "").strip() not in ("受電箱", "RECEIVING")
            or base_spec.features
            or any(abs(float(getattr(base_spec, key)) - float(v)) > 1e-6
                   for key, v in expected.items())
            or (base_spec.receiving_nfb_depth_pair_mm is not None
                and base_spec.receiving_nfb_depth_pair_mm
                    != values["receiving_nfb_depth_pair_mm"])):
        raise ValueError("CSV_BASE_EXPORT_PARTSPEC_VS_LIVE_SOURCE_MISMATCH")
    baseline = build_part_render_data(base_spec)
    if (baseline.unfolded_topology is None
            or baseline.unfolded_topology.piece_id != "base_plate"
            or not baseline.fold_guides):
        raise ValueError("CSV_BASE_EXPORT_SOURCE_BEND_OR_BLANK_MISSING")
    return baseline


def export_verified_csv_v5_single_base_part_only(
    snapshot, inner_door_id, *, base_spec: BasePlatePartSpec,
    output_directory, version_id: str, quantity: int,
    parameters: ManufacturingParameters, overwrite: bool = False,
) -> VerifiedCsvBasePartOnlyOutput:
    """Current CSV -> same real plate FinalScene -> check/Q -> DXF -> reopen.

    No supplier DXF input. A successful PART_ONLY result is NOT an EAR, side
    MARKING, PAD, second tier, full-set or batch release. The original generic
    V5 trial manufacturing guards are deliberately unchanged.
    """
    holes, set_id, bay_id = _current_single_tier_csv_holes(
        snapshot, inner_door_id,
    )
    _require_source_derived_real_plate(snapshot, base_spec)
    door = trial_configured_nfb_v5_inner_door_render_data(
        snapshot, inner_door_id, holes=holes,
    )
    part = preview_v5_on_existing_receiving_base(
        snapshot, inner_door_id, door=door,
        configured_holes=holes, base_spec=base_spec,
    )
    preview = check_csv_v5_base_part_only_groups((
        CsvV5BaseCheckDemand(version_id, part, quantity, parameters),
    ))
    if (not preview.groups or preview.physical_part_ids != ("base_plate",)
            or len(preview.groups) != 1
            or preview.groups[0].quantity != quantity):
        raise ValueError("CSV_BASE_EXPORT_CHECK_Q_PHYSICAL_DEMAND_INVALID")

    root = Path(output_directory)
    filename = resolved_physical_dxf_filename(
        "base_plate", instance_namespace=f"{set_id}__{bay_id}",
    )
    destination = root / filename
    if destination.exists() and not overwrite:
        raise FileExistsError(str(destination))
    # Serialization is allowed ONLY after recomputing the current source,
    # current configured door and all exact numerical part-only CHECK/Q.
    # The generic trial export path continues to refuse unverified scenes.
    root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".whd-csv-base-", dir=str(root)))
    try:
        stage_path = staging / filename
        save_scene_dxf(stage_path, part.render_data.scene)
        checked = verify_saved_part_render_data_dxf(part.render_data, stage_path)
        if not checked.ok:
            raise ValueError("CSV_BASE_EXPORT_SAVED_DXF_GEOMETRY_VERIFICATION_FAILED")
        result = _atomic_commit_staged_dxfs(
            {"base_plate": stage_path}, root, overwrite=overwrite,
        )
        return VerifiedCsvBasePartOnlyOutput(
            part_id="base_plate", path=result["base_plate"],
            source_hole_ids=part.hole_ids, quantity=quantity,
            check_q_key=preview.groups[0].key,
        )
    finally:
        shutil.rmtree(staging, ignore_errors=True)
