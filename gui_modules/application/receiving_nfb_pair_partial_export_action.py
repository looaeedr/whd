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


@dataclass(frozen=True)
class NfbCsvPairedPartOnlyDxf:
    """Two validated sheets, NOT a full enclosure or welded EAR release."""
    inner_door_path: str
    base_plate_path: str
    source_hole_ids: tuple[str, ...]
    check_q_key: str
    scope: str = "CSV_PAIR_PART_ONLY_NOT_WHOLE_CABINET"


def export_current_csv_nfb_door_base_pair(
    snapshot: Mapping[str, object], *,
    assembly_parts,
    base_spec: BasePlatePartSpec,
    output_directory: str | Path,
) -> NfbCsvPairedPartOnlyDxf:
    """Use the ALREADY-RESOLVED normal WHD FinalScene for CSV machining.

    Existing GUI export uses this when the current committed Bay's sole
    source is numeric CSV. Recreate source proof and compare both real sheets
    against the exact physical 2D/3D assembly before writing any DXF.
    Native EAR slots and other Hole Editor features are not replaced.
    Never use old DXF handles, manufacture a readiness boolean, or grant
    second-tier/full-cabinet/PAD/welded-EAR manufacturing.
    """
    from ae_engine.manufacturing_api import build_part_render_data
    from ae_engine.manufacturing_equivalence import ManufacturingParameters
    from ae_engine.manufacturing_export import (
        _atomic_commit_staged_dxfs, resolved_physical_dxf_filename,
        receiving_instance_namespace,
    )
    from ae_engine.manufacturing_verification import verify_saved_part_render_data_dxf
    from ae_engine.dxf_serialization import save_scene_dxf
    from ae_engine.receiving_nfb_committed_final_scene import (
        _submitted_csv_holes, _existing_source_specs,
        _without_derived_csv_door_features,
    )
    from ae_engine.receiving_nfb_v5_configured_inner_door import (
        trial_configured_nfb_v5_inner_door_render_data,
    )
    from ae_engine.receiving_nfb_v5_live_base_preview import (
        preview_v5_on_existing_receiving_base,
    )
    from ae_engine.receiving_nfb_v5_check_q_preview import (
        CsvV5BaseCheckDemand, check_csv_v5_base_part_only_groups,
    )
    from pathlib import Path
    from tempfile import TemporaryDirectory

    proof_source = _submitted_csv_holes(snapshot)
    if not proof_source:
        raise ValueError("CSV_PAIR_CURRENT_SUBMITTED_SOURCE_UNAVAILABLE")
    inner_door_id, holes = proof_source
    if holes[0].layer_count == 2 and all(h.layer_count == 2 for h in holes):
        return _export_current_csv_nfb_two_tier_pair(
            snapshot, assembly_parts=assembly_parts,
            output_directory=output_directory,
            source=(inner_door_id, holes),
        )
    if holes[0].layer_count != 1 or any(h.layer_count != 1 for h in holes):
        raise ValueError("CSV_PAIR_UNSUPPORTED_NFB_TIER_COUNT")
    expected_spec = _existing_source_specs(snapshot, holes)[0]
    if base_spec != expected_spec:
        raise ValueError("CSV_PAIR_ACTUAL_BASE_PARTSPEC_CHANGED")
    selection = snapshot.get("_receiving_runtime_selection")
    if not isinstance(selection, Mapping):
        raise ValueError("CSV_PAIR_SELECTED_SET_BAY_REQUIRED")
    namespace = receiving_instance_namespace(
        set_id=selection["set_id"], bay_id=selection["bay_id"],
    )
    source_snapshot = _without_derived_csv_door_features(
        snapshot, inner_door_id,
    )
    door = trial_configured_nfb_v5_inner_door_render_data(
        source_snapshot, inner_door_id, holes=holes,
    )
    base = preview_v5_on_existing_receiving_base(
        snapshot, inner_door_id, door=door, configured_holes=holes,
        base_spec=expected_spec,
        existing_render_data=build_part_render_data(expected_spec),
    )
    if base.hole_ids != door.hole_ids or base.part_id != "base_plate":
        raise ValueError("CSV_PAIR_BASE_AND_DOOR_SOURCE_MISMATCH")

    # A 2D/3D view MAY have been regenerated after a selection change.
    # Neither the newly rebuilt trial nor an old cached render alone can
    # authorize DXF: both must be byte-geometry-equivalent to current scene.
    parts = tuple(assembly_parts or ())
    def exact_scene(identity, expected):
        found = tuple(p for p in parts if getattr(p,"part_key",None)==identity)
        if len(found) != 1 or getattr(found[0], "placement", None) == "standalone":
            raise ValueError("CSV_PAIR_ACTUAL_ASSEMBLY_PART_MISSING")
        existing = found[0].render_data
        if (existing.unfolded_topology != expected.unfolded_topology
                or tuple(existing.fold_guides or ()) != tuple(expected.fold_guides or ())
                or tuple(existing.scene.primitives) != tuple(expected.scene.primitives)
                or existing.material is None or expected.material is None
                or existing.material.symmetric_difference(expected.material).area > 1e-5
                or existing.metadata.get("stable_id") != identity):
            raise ValueError("CSV_PAIR_CURRENT_FINALSCENE_DIFFERS_FROM_CSV")
        return existing
    actual_door = exact_scene(door.part_id, door.render_data)
    actual_base = exact_scene(base.part_id, base.render_data)
    checked = check_csv_v5_base_part_only_groups((
        CsvV5BaseCheckDemand(
            namespace, base, 1,
            ManufacturingParameters("UNSPECIFIED_SHEET",
                                    float(snapshot["t"]), "CUTTING_DXF"),
        ),
    ))
    if (len(checked.groups) != 1 or checked.physical_part_ids != ("base_plate",)
            or checked.groups[0].quantity != 1):
        raise ValueError("CSV_PAIR_CHECK_Q_INVALID")

    root = Path(output_directory)
    if not root.is_dir():
        raise ValueError("CSV_PAIR_OUTPUT_DIRECTORY_MISSING")
    names = {
        door.part_id: resolved_physical_dxf_filename(
            door.part_id, instance_namespace=namespace, box_body_physical_piece_roles=(),
        ),
        "base_plate": resolved_physical_dxf_filename(
            "base_plate", instance_namespace=namespace, box_body_physical_piece_roles=(),
        ),
    }
    if len(set(names.values())) != 2:
        raise ValueError("CSV_PAIR_DUPLICATE_DXF_OUTPUT")
    if any((root / name).exists() for name in names.values()):
        raise FileExistsError("CSV_PAIR_EXISTING_DXF_NOT_OVERWRITTEN")

    with TemporaryDirectory(prefix=".whd-csv-pair-stage-", dir=str(root)) as stage:
        staged = {}
        for identity, render in ((door.part_id, actual_door),
                                 ("base_plate", actual_base)):
            path = Path(stage) / names[identity]
            save_scene_dxf(path, render.scene)
            receipt = verify_saved_part_render_data_dxf(render, path)
            if not receipt.ok:
                raise ValueError("CSV_PAIR_SAVED_DXF_ROUNDTRIP_FAILED:" + identity)
            staged[identity] = path
        written = _atomic_commit_staged_dxfs(
            staged, root, overwrite=False,
        )
    return NfbCsvPairedPartOnlyDxf(
        inner_door_path=written[door.part_id],
        base_plate_path=written["base_plate"],
        source_hole_ids=door.hole_ids,
        check_q_key=checked.groups[0].key,
    )


@dataclass(frozen=True)
class NfbCsvTwoTierPartOnlyDxf:
    """Existing operator output: actual inner door and TWO independently checked bases."""
    inner_door_path: str
    base_plate_paths: tuple[str, str]
    source_hole_ids: tuple[str, ...]
    check_q_keys: tuple[str, ...]
    scope: str = "CSV_TWO_TIER_PART_ONLY_NOT_WHOLE_CABINET"


def _export_current_csv_nfb_two_tier_pair(
    snapshot: Mapping[str, object], *,
    assembly_parts,
    output_directory: str | Path,
    source,
) -> NfbCsvTwoTierPartOnlyDxf:
    """Two actual tiers, one authoritative inner-door CSV; no second UI or DXF source.

    Source specs, depth and installed XY/Z are independently recalculated for
    each physical tier. These three *parts only* may be serialized after
    exact scene, CSV CHECK/Q and actual reopened-DXF proofs. The generic
    all-parts/padded-EAR/cabinet manufacturing gates are NOT disabled.
    """
    from tempfile import TemporaryDirectory
    from ae_engine.manufacturing_api import build_part_render_data
    from ae_engine.manufacturing_equivalence import ManufacturingParameters
    from ae_engine.manufacturing_export import (
        _atomic_commit_staged_dxfs, resolved_physical_dxf_filename,
        receiving_instance_namespace,
    )
    from ae_engine.manufacturing_verification import verify_saved_part_render_data_dxf
    from ae_engine.dxf_serialization import save_scene_dxf
    from ae_engine.receiving_nfb_committed_final_scene import (
        _existing_source_specs, _submitted_csv_holes,
        _without_derived_csv_door_features,
    )
    from ae_engine.receiving_nfb_v5_configured_inner_door import (
        trial_configured_nfb_v5_inner_door_render_data,
    )
    from ae_engine.receiving_nfb_v5_live_base_preview import (
        preview_v5_on_existing_receiving_base,
    )
    from ae_engine.receiving_nfb_v5_check_q_preview import (
        CsvV5BaseCheckDemand, check_csv_v5_base_part_only_groups,
    )
    from ae_engine.receiving_tier_ear_z_targets import (
        resolve_receiving_tier_base_z_targets,
    )

    current = _submitted_csv_holes(snapshot)
    if not current or current != source:
        raise ValueError("CSV_TWO_TIER_COMMITTED_SOURCE_CHANGED")
    inner_door_id, holes = current
    if not holes or any(h.layer_count != 2 for h in holes):
        raise ValueError("CSV_TWO_TIER_REQUIRES_TWO_NFB_TIERS")
    specs = _existing_source_specs(snapshot, holes)
    if set(specs) != {0, 1} or any(
        specs[i].physical_id != f"base_plate:nfb_layer:{i}" for i in (0,1)
    ):
        raise ValueError("CSV_TWO_TIER_INDEPENDENT_BASE_SOURCES_MISSING")
    selection = snapshot.get("_receiving_runtime_selection")
    if not isinstance(selection, Mapping):
        raise ValueError("CSV_TWO_TIER_CURRENT_SET_BAY_MISSING")
    namespace = receiving_instance_namespace(
        set_id=selection["set_id"], bay_id=selection["bay_id"],
    )
    source_snapshot = _without_derived_csv_door_features(snapshot, inner_door_id)
    door = trial_configured_nfb_v5_inner_door_render_data(
        source_snapshot, inner_door_id, holes=holes,
    )
    # All source holes remain on their actual owning tier; never split the
    # one inner-door source proof into unrelated independent switch configurations.
    trials = {
        i: preview_v5_on_existing_receiving_base(
            snapshot, inner_door_id, door=door, configured_holes=holes,
            base_spec=specs[i], tier_slot_index=i,
            existing_render_data=build_part_render_data(specs[i]),
        ) for i in (0, 1)
    }
    if (sum(len(x.hole_ids) for x in trials.values()) != len(door.hole_ids)
            or set(trials[0].hole_ids) & set(trials[1].hole_ids)):
        raise ValueError("CSV_TWO_TIER_SWITCH_SCREW_OWNER_MISMATCH")
    original_parts = tuple(assembly_parts or ())
    by_id = {}
    for part in original_parts:
        key = getattr(part, "part_key", None)
        if key in by_id:
            raise ValueError("CSV_TWO_TIER_DUPLICATED_ASSEMBLY_PART")
        by_id[key] = part
    expected = {
        door.part_id: door.render_data,
        trials[0].part_id: trials[0].render_data,
        trials[1].part_id: trials[1].render_data,
    }
    actual = {}
    for key, proof in expected.items():
        part = by_id.get(key)
        if part is None or getattr(part, "placement", None) == "standalone":
            raise ValueError("CSV_TWO_TIER_MISSING_INSTALLED_PHYSICAL_PART:" + key)
        render = part.render_data
        if (render.unfolded_topology != proof.unfolded_topology
                or tuple(render.fold_guides or ()) != tuple(proof.fold_guides or ())
                or tuple(render.scene.primitives) != tuple(proof.scene.primitives)
                or render.material is None or proof.material is None
                or render.material.symmetric_difference(proof.material).area > 1e-5
                or render.metadata.get("stable_id") != key):
            raise ValueError("CSV_TWO_TIER_FINALSCENE_DIFFERS_FROM_CSV:" + key)
        actual[key] = render
    depths = {row.layer_index: row
              for row in resolve_receiving_tier_base_z_targets(snapshot)}
    if set(depths) != {0, 1}:
        raise ValueError("CSV_TWO_TIER_INCOMPLETE_SOURCE_DEPTH")
    from ae_engine.receiving_nfb_y_projection import project_nfb_inner_door_nominal_y
    for index in (0, 1):
        target = depths[index]
        installed = by_id[trials[index].part_id]
        offset = tuple(installed.offset)
        y = project_nfb_inner_door_nominal_y(
            snapshot, inner_door_id, layer_count=2, slot_index=index,
        )
        if (len(offset) != 3 or not target.physical_skin_z_resolved
                or abs(float(offset[0])) > 1e-6
                or abs(float(offset[1]) - float(y.box_world_y_mm)) > 1e-6
                or abs(float(offset[2]) - float(target.world_offset_z_mm)) > 1e-6):
            raise ValueError("CSV_TWO_TIER_REAL_BASE_INSTALL_XYZ_MISMATCH")

    checks = check_csv_v5_base_part_only_groups(tuple(
        CsvV5BaseCheckDemand(
            namespace, trials[index], 1,
            ManufacturingParameters("UNSPECIFIED_SHEET",
                                    float(snapshot["t"]), "CUTTING_DXF"),
        )
        for index in (0,1)
    ))
    if (set(checks.physical_part_ids) != {trials[0].part_id, trials[1].part_id}
            or not checks.groups
            or sum(group.quantity for group in checks.groups) != 2):
        raise ValueError("CSV_TWO_TIER_CHECK_Q_INCOMPLETE")

    root = Path(output_directory)
    if not root.is_dir():
        raise ValueError("CSV_TWO_TIER_OUTPUT_DIRECTORY_MISSING")
    names = {
        key: resolved_physical_dxf_filename(key, instance_namespace=namespace, box_body_physical_piece_roles=())
        for key in expected
    }
    if len(set(names.values())) != 3:
        raise ValueError("CSV_TWO_TIER_DUPLICATED_OUTPUT_FILENAMES")
    for name in names.values():
        if (root / name).exists():
            raise FileExistsError("CSV_TWO_TIER_EXISTING_DXF_NOT_OVERWRITTEN:" + name)
    # All source checks finish before the first file is committed, and
    # all three staged files must independently pass actual DXF reopen.
    with TemporaryDirectory(prefix=".whd-csv-tiers-", dir=str(root)) as stage:
        staged = {}
        for key, render in actual.items():
            candidate = Path(stage) / names[key]
            save_scene_dxf(candidate, render.scene)
            receipt = verify_saved_part_render_data_dxf(render, candidate)
            if not receipt.ok:
                raise ValueError("CSV_TWO_TIER_DXF_ROUNDTRIP_FAILED:" + key)
            staged[key] = candidate
        saved = _atomic_commit_staged_dxfs(staged, root, overwrite=False)
    return NfbCsvTwoTierPartOnlyDxf(
        inner_door_path=saved[door.part_id],
        base_plate_paths=(saved[trials[0].part_id], saved[trials[1].part_id]),
        source_hole_ids=door.hole_ids,
        check_q_keys=tuple(group.key for group in checks.groups),
    )
