# -*- coding: utf-8 -*-
"""#1503: source-formed fixed plates -> independent physical production DXFs.

The user already supplied authentic T2 CUTTING/BEND23, signed fold direction
follows the agreed assembly, and the WHD world-skin engine proves both the
mother-side weld-footprint contact and each installed Base Plate back skin.
This adapter CONSUMES those existing proofs; it never invents a new flat,
second coordinate source, bend compensation, welded joint or PAD.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from math import isclose
from pathlib import Path
from tempfile import TemporaryDirectory

from .manufacturing_api import (
    _resolved_physical_dxf_filename, save_part_render_data_dxf,
    verify_saved_part_render_data_dxf,
)
from .manufacturing_export import (
    _atomic_commit_staged_dxfs, resolved_physical_render_parts,
)
from .manufacturing_scene_access import owner_render_data
from .receiving_base_fixing_plate_geometry import (
    LARGE_PATTERN, SOURCE_DXF_SHA256, build_fixing_plate_source_render_data,
)
from .receiving_fixed_plate_formed_skins import (
    build_receiving_formed_fixing_plate_skins,
)
from .receiving_fixed_plate_side_check_dxf import (
    _readback_marking_lines, _verified_pair,
)
from .receiving_tier_fixing_contact_receipt import (
    validate_receiving_tier_fixing_contact_receipts,
)
from .sheetmetal_drawing import PolylinePrimitive


@dataclass(frozen=True)
class FormedFixingPlateManufacturingReceipt:
    output_paths: tuple[tuple[str, str], ...]
    formed_part_ids: tuple[str, ...]
    side_marked_piece_ids: tuple[str, ...]
    source_sha256: str
    physical_contact_area_mm2: float
    scope: str = "FORMED_FIXING_PARTS_AND_SIDE_SHEETS_NOT_WELD_WORKMANSHIP"


def _verified_formed_ear_parts(snapshot, original_geometry, *, dimensions, sheet_thickness):
    """Derive actual +90° T2 physical sheets from TWO independent witnesses.

    Authentic world-side skins/proven UV marks and the assembled parent BASE
    are independently checked; an off-centre base or missing second tier
    cannot borrow the earlier geometry receipt.
    """
    if snapshot.get("active_mode") == "quantity":
        # Quantity requests are authorized per CURRENT, selected, persisted
        # NFB version; never carry the previously selected Bay's source.
        from ae_engine.receiving_quantity_box import project_common_box
        from ae_engine.receiving_layout import project_receiving_bay_legacy_aliases
        from phase6_quantity_model import QuantityModel
        raw_quantity = snapshot.get("quantity")
        model = QuantityModel.from_payload(raw_quantity)
        current = model.nfb_config_for_version(model.selected_version_id)
        reprojection = project_receiving_bay_legacy_aliases(
            project_common_box(snapshot), set_index=0, bay_index=0,
        )
        # Quantity's Bay projection deliberately clears the transient
        # Set/Bay selector: it cannot be compared with a manufacturing
        # invocation's derived selector. Reconstruct expected identity from
        # the actual selected single-Bay graph and verify it explicitly.
        layout = reprojection.get("receiving_layout")
        sets = layout.get("sets") if isinstance(layout, dict) else None
        singleton = (
            isinstance(sets, (list, tuple)) and len(sets) == 1
            and isinstance(sets[0].get("bays"), (list, tuple))
            and len(sets[0]["bays"]) == 1
        )
        expected_selection = ({
            "set_index": 0, "bay_index": 0,
            "set_id": sets[0]["stable_id"],
            "bay_id": sets[0]["bays"][0]["stable_id"],
        } if singleton else None)
        if (not current or current.get("nfb_config_submitted") is not True
                or current.get("nfb_config") != snapshot.get("nfb_config")
                or reprojection.get("nfb_config") != snapshot.get("nfb_config")
                or reprojection.get("nfb_config_submitted") is not True
                or expected_selection is None
                or snapshot.get("_receiving_runtime_selection")
                   != expected_selection
                or reprojection.get("receiving_layout")
                   != snapshot.get("receiving_layout")):
            raise ValueError("EAR_FORM_MFG_QUANTITY_CURRENT_VERSION_SOURCE_DRIFT")
    uv, side_contact, side_parts, side_scenes = _verified_pair(
        snapshot, original_geometry, dimensions=dimensions,
        sheet_thickness=sheet_thickness,
        permit_independent_source_marking_crossing=True,
    )
    bases = validate_receiving_tier_fixing_contact_receipts(
        snapshot, original_geometry.parts,
    )
    from .receiving_fixed_plate_side_contact import (
        derive_receiving_ear_side_contact_from_formed_skin,
    )
    if (len(bases) not in (2, 4) or len(bases) != len(side_contact)
            or {row.ear_part_id for row in bases}
               != {row.ear_part_id for row in side_contact}
            or {row.ear_part_id for row in uv}
               != {row.ear_part_id for row in bases}):
        raise ValueError("EAR_FORM_MFG_INCOMPLETE_BASE_SIDE_SOURCE_OWNERS")
    base_by_id = {x.ear_part_id: x for x in bases}
    side_by_id = {x.ear_part_id: x for x in side_contact}
    uv_by_id = {x.ear_part_id: x for x in uv}
    formed_parts = {}
    for ear_id, reference in base_by_id.items():
        formed = build_receiving_formed_fixing_plate_skins(snapshot, ear_id)
        contact = derive_receiving_ear_side_contact_from_formed_skin(formed)
        original = build_fixing_plate_source_render_data(ear_id, snapshot=snapshot)
        m = dict(original.metadata or {})
        witness = side_by_id[ear_id]
        flat_side = uv_by_id[ear_id]
        if (reference.base_part_id != formed.base_part_id
                or reference.layer_index != formed.layer_index
                or reference.side != formed.side
                or reference.fixing_hole_world_x_mm != formed.source_to_cabinet_hole_x_mm
                or not isclose(reference.actual_base_back_skin_world_z_mm,
                               formed.parent_base_back_skin_world_z_mm, abs_tol=1e-6)
                or not isclose(reference.side_skin_world_x_mm,
                               formed.side_wall_inside_world_x_mm, abs_tol=1e-6)
                or flat_side.world_boundary != contact.world_surface_boundary
                or witness.side_piece_id != contact.side_piece_id
                or witness.nfb_layer_index != formed.layer_index
                or not witness.flange_skin_normal_opposed
                or not witness.full_contact_material_coverage_verified
                or not witness.no_through_side_skin_penetration_verified
                or witness.manufacturing_ready
                or witness.welding_workmanship_certified
                or not formed.actual_signed_forming_constructed
                or not formed.side_wall_skin_contact_x_verified
                or not isclose(formed.signed_source_fold_degrees, 90., abs_tol=1e-6)
                or not isclose(formed.source_bend_y_mm, 23., abs_tol=1e-6)
                or not isclose(formed.actual_mid_surface_hinge_y_mm, 22., abs_tol=1e-6)
                or m.get("source_dxf_sha256") != SOURCE_DXF_SHA256
                or m.get("source_cutting_verified") is not True
                or m.get("source_bend_verified") is not True
                or m.get("source_flat_dimensions") != (256., 105.)
                or m.get("thickness") != 2.
                or m.get("source_derived_formed_hole_center_mm") != 63.
                or original.material is None or original.material.is_empty
                or len(original.fold_guides) != 1
                or len([p for p in original.scene.primitives
                        if isinstance(p, PolylinePrimitive)
                        and p.closed and p.layer == "CUTTING"]) != 5
                or not formed.mapped_world_middle or not formed.mapped_world_skins):
            raise ValueError("EAR_FORM_MFG_REAL_SOURCE_SKIN_Z_OR_BEND_MISMATCH:" + ear_id)
        if not isclose(witness.physical_contact_area_mm2, 5632., abs_tol=1.):
            raise ValueError("EAR_FORM_MFG_PHYSICAL_CONTACT_AREA_MISMATCH")
        # These three outcomes are TRUE only in THIS recalculated, bounded
        # machining copy. The project/GUI source preview stays unapproved;
        # welding-workmanship and whole-cabinet releases stay separate.
        production = replace(
            original,
            metadata={
                **m,
                "formed_direction_verified": True,
                "formed_geometry_verified": True,
                "weld_z_verified": True,
                "formed_source_fold_degrees": 90.,
                "formed_world_side_contact_area_mm2": witness.physical_contact_area_mm2,
                "fixed_plate_manufacturing_scope": "SOURCE_FORMED_CUTTING_BEND_PART_ONLY",
                "welding_workmanship_certified": False,
                "whole_cabinet_manufacturing_ready": False,
                "manufacturing_ready": False,
            },
        )
        formed_parts[ear_id] = production
    return formed_parts, uv, side_contact



def _verified_current_csv_manufacturing_owners(
    snapshot, original_geometry, selected_geometry,
):
    """Recompute numeric CSV DOOR+ALL tier BASE proofs from original FinalScene.

    Only exact current submitted Set/Bay CSV scene owners get scoped release.
    Original normal assembly remains immutable. This function does NOT grant
    a metadata-ready flag or disable any other generic manufacturing guard.
    """
    from .manufacturing_api import build_part_render_data
    from .manufacturing_equivalence import ManufacturingParameters
    from .receiving_nfb_committed_final_scene import (
        _submitted_csv_holes, _existing_source_specs,
        _without_derived_csv_door_features,
    )
    from .receiving_nfb_v5_configured_inner_door import (
        trial_configured_nfb_v5_inner_door_render_data,
    )
    from .receiving_nfb_v5_live_base_preview import (
        preview_v5_on_existing_receiving_base,
    )
    from .receiving_nfb_v5_check_q_preview import (
        CsvV5BaseCheckDemand, check_csv_v5_base_part_only_groups,
    )
    from .manufacturing_export import receiving_instance_namespace

    sourced = _submitted_csv_holes(snapshot)
    if not sourced:
        raise ValueError("RECEIVING_FULL_NFB_CURRENT_COMMITTED_CSV_REQUIRED")
    inner_id, holes = sourced
    if len(set(h.physical_hole_id for h in holes)) != len(holes):
        raise ValueError("RECEIVING_FULL_NFB_DUPLICATE_SWITCH_IDS")
    source_snapshot = _without_derived_csv_door_features(snapshot, inner_id)
    door = trial_configured_nfb_v5_inner_door_render_data(
        source_snapshot, inner_id, holes=holes,
    )
    specs = _existing_source_specs(snapshot, holes)
    if set(specs) != set(range(holes[0].layer_count)):
        raise ValueError("RECEIVING_FULL_NFB_MISSING_REAL_TIER_BASE_SPEC")
    scene_parts = tuple(original_geometry.parts or ())
    physical = {}
    for part in scene_parts:
        key = str(part.part_key)
        if key in physical:
            raise ValueError("RECEIVING_FULL_NFB_DUPLICATED_ACTUAL_SCENE_OWNER")
        physical[key] = part

    expected = {door.part_id: door.render_data}
    trial_bases = {}
    for tier, spec in sorted(specs.items()):
        identity = "base_plate" if len(specs)==1 else f"base_plate:nfb_layer:{tier}"
        if spec.physical_id != identity:
            raise ValueError("RECEIVING_FULL_NFB_BASE_IDENTITY_DIFFERS_FROM_SOURCE")
        trial = preview_v5_on_existing_receiving_base(
            snapshot, inner_id, door=door, configured_holes=holes,
            base_spec=spec,
            tier_slot_index=(None if len(specs)==1 else tier),
            existing_render_data=build_part_render_data(spec),
        )
        if trial.part_id != identity:
            raise ValueError("RECEIVING_FULL_NFB_BASE_PROOF_OWNER_MISMATCH")
        trial_bases[tier] = trial
        expected[identity] = trial.render_data
    if (len({hole for trial in trial_bases.values() for hole in trial.hole_ids})
            != len(holes)):
        raise ValueError("RECEIVING_FULL_NFB_SCREW_OWNER_COLLISION")
    actual_owners = {}
    for key, reference in expected.items():
        part = physical.get(key)
        if part is None or getattr(part,"placement",None) == "standalone":
            raise ValueError("RECEIVING_FULL_NFB_PHYSICAL_SOURCE_MISSING:" + key)
        scene = part.render_data
        if (scene.unfolded_topology != reference.unfolded_topology
                or tuple(scene.fold_guides or ()) != tuple(reference.fold_guides or ())
                or tuple(scene.scene.primitives) != tuple(reference.scene.primitives)
                or scene.material is None or reference.material is None
                or scene.material.symmetric_difference(reference.material).area > 1e-5
                or scene.metadata.get("stable_id") != key):
            raise ValueError("RECEIVING_FULL_NFB_ACTUAL_FINALSCENE_SOURCE_DRIFT:" + key)
        actual_owners[key] = scene
    from .receiving_tier_ear_z_targets import resolve_receiving_tier_base_z_targets
    from .receiving_nfb_y_projection import project_nfb_inner_door_nominal_y
    from .assembly_placement import resolve_assembly_placement
    depth_rows = {r.layer_index:r for r in resolve_receiving_tier_base_z_targets(snapshot)}
    if set(depth_rows) != set(specs):
        raise ValueError("RECEIVING_FULL_NFB_SOURCE_DEPTH_TIER_MISSING")
    for tier, trial in trial_bases.items():
        parent = physical[trial.part_id]
        source_y = project_nfb_inner_door_nominal_y(
            snapshot, inner_id, layer_count=len(specs), slot_index=tier,
        )
        if len(specs) == 1:
            original_xyz = resolve_assembly_placement(snapshot, "base_plate").world_offset
        else:
            target = depth_rows[tier]
            if not target.physical_skin_z_resolved or target.world_offset_z_mm is None:
                raise ValueError("RECEIVING_FULL_NFB_TIER_REAL_Z_MISSING")
            original_xyz = (0., source_y.box_world_y_mm, target.world_offset_z_mm)
        installed = tuple(getattr(parent,"offset",()) or ())
        if (len(installed) != 3
                or any(abs(float(installed[i])-float(original_xyz[i])) > 1e-6
                       for i in range(3))
                or abs(float(installed[1])-float(source_y.box_world_y_mm)) > 1e-6):
            raise ValueError("RECEIVING_FULL_NFB_BASE_REAL_INSTALL_XYZ_DRIFT")
    selection = snapshot.get("_receiving_runtime_selection")
    namespace = receiving_instance_namespace(
        set_id=selection["set_id"],bay_id=selection["bay_id"],
    )
    check = check_csv_v5_base_part_only_groups(tuple(
        CsvV5BaseCheckDemand(
            namespace, trial, 1,
            ManufacturingParameters(
                "UNSPECIFIED_SHEET",float(snapshot["t"]),"CUTTING_DXF",
            ),
        ) for tier,trial in sorted(trial_bases.items())
    ))
    if (set(check.physical_part_ids) != {trial.part_id for trial in trial_bases.values()}
            or sum(x.quantity for x in check.groups) != len(trial_bases)):
        raise ValueError("RECEIVING_FULL_NFB_CHECK_Q_REAL_PLATE_COUNT_DIFFERS")
    selected = {key for key,_ in resolved_physical_render_parts(selected_geometry)}
    permitted = set(expected).intersection(selected)
    # A two-tier button selection cannot silently export only one of the
    # actual physical bases. A selected inner door similarly cannot be a
    # proof with only one of its CSV tiers materialized in the assembly.
    if ({x.part_id for x in trial_bases.values()} & selected
            and not {x.part_id for x in trial_bases.values()}.issubset(selected)):
        raise ValueError("RECEIVING_FULL_NFB_PARTIAL_TIER_SELECTION")
    return permitted

def save_verified_receiving_formed_fixing_plate_bundle(
    snapshot, original_geometry, selected_marked_geometry,
    output_dir, *, dimensions, sheet_thickness, overwrite=False,
) -> FormedFixingPlateManufacturingReceipt:
    """Atomically write original selected DXF rows plus signed formed fixed plates.

    For the existing normal BoxBody export, retain all selected physical
    sheets/side MARKING. Add exactly 2/4 ORIGINAL source fixing plates;
    independently reopen every production DXF and compare actual SIDE marks.
    No global EAR manufacturing flag or new operator button is introduced.
    """
    if type(overwrite) is not bool:
        raise TypeError("EAR_FORM_MFG_OVERWRITE_MUST_BE_BOOLEAN")
    verified, uv, side_contact = _verified_formed_ear_parts(
        snapshot, original_geometry,
        dimensions=dimensions, sheet_thickness=sheet_thickness,
    )
    rows = tuple(resolved_physical_render_parts(selected_marked_geometry))
    if not rows:
        raise ValueError("EAR_FORM_MFG_NO_SELECTED_NORMAL_SHEETS")
    # The preexisting native DXF sink must still own each ordinary sheet.
    from .manufacturing_export import (
        _reject_unapproved_nfb_pad_ear_manufacturing,
        reject_unverified_receiving_nfb_tier_base,
        _validate_nfb_base_part_scope,
    )
    standard_rows = tuple(
        (key, _resolved_physical_dxf_filename(key), render)
        for key, render in rows
    )
    approved_csv = set()
    if any(
        key == "base_plate" or key.startswith("base_plate:nfb_layer:")
        or key.startswith("inner_door:")
        for key,_,_ in standard_rows
    ):
        approved_csv = _verified_current_csv_manufacturing_owners(
            snapshot, original_geometry, selected_marked_geometry,
        )
        source_selected = {
            key for key,_,render in standard_rows
            if key == "base_plate" or key.startswith("base_plate:nfb_layer:")
            or bool((getattr(render, "metadata", None) or {}).get(
                "nfb_v5_trial_status"
            ))
        }
        if not source_selected.issubset(approved_csv):
            raise ValueError("RECEIVING_FULL_NFB_UNPROVEN_SELECTED_PHYSICAL_SHEET")
    _reject_unapproved_nfb_pad_ear_manufacturing(standard_rows)
    for key, _, render in standard_rows:
        if key not in approved_csv:
            reject_unverified_receiving_nfb_tier_base(render, output_key=key)
        if (getattr(render, "metadata", None) or {}).get(
            "receiving_base_plate_unconfigured"
        ) is True:
            raise ValueError("EAR_FORM_MFG_SELECTED_UNCONFIGURED_BASE")
    _validate_nfb_base_part_scope(
        tuple(row for row in standard_rows if row[0] not in approved_csv),
        part_only=False,
    )
    if not all(
        owner_render_data(selected_marked_geometry, side) is not None
        for side in ("box_body:left_side","box_body:right_side")
    ):
        raise ValueError("EAR_FORM_MFG_BOTH_MARKED_SIDE_SHEETS_REQUIRED")

    filenames = {key: filename for key, filename, _ in standard_rows}
    for ear_id in verified:
        if ear_id in filenames:
            raise ValueError("EAR_FORM_MFG_DUPLICATE_PHYSICAL_OWNER")
        filenames[ear_id] = _resolved_physical_dxf_filename(ear_id)
    if len(set(filenames.values())) != len(filenames):
        raise ValueError("EAR_FORM_MFG_DUPLICATE_DXF_FILENAME")
    root = Path(output_dir)
    if not overwrite and any((root / name).exists() for name in filenames.values()):
        raise FileExistsError("EAR_FORM_MFG_DXF_ALREADY_EXISTS")
    root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".whd-formed-ear-", dir=str(root)) as stage:
        written = {}
        for key, filename, render in standard_rows + tuple(
            (key, filenames[key], verified[key]) for key in verified
        ):
            dest = Path(stage) / filename
            if key in approved_csv or key in verified:
                # Neither a CSV source trial nor a flat fixing-plate preview
                # is generally manufacturable. These rows, however, came
                # from this adapter's fresh, independent source/skin/contact
                # verification above; do not weaken the generic MFG guard.
                # Preserve the existing atomic staging and round-trip checks.
                if key in verified and render is not verified[key]:
                    raise ValueError("EAR_FORM_MFG_VERIFIED_RENDER_IDENTITY_DRIFT")
                from .dxf_serialization import save_scene_dxf
                save_scene_dxf(dest, render.scene)
            else:
                save_part_render_data_dxf(render, dest, overwrite=False)
            receipt = verify_saved_part_render_data_dxf(render, dest)
            if not receipt.ok:
                raise ValueError("EAR_FORM_MFG_DXF_ROUNDTRIP_FAILED:" + key)
            written[key] = dest
        # SIDE weld-position marks are source-UV vertices, not merely an
        # unrelated count of lines on a manufacturing sheet.
        for side in ("box_body:left_side","box_body:right_side"):
            source = owner_render_data(selected_marked_geometry, side)
            matched = tuple(
                key for key, _filename, render in standard_rows
                if render is source
            )
            if len(matched) != 1:
                raise ValueError("EAR_FORM_MFG_SIDE_OUTPUT_OWNER_AMBIGUOUS")
            _readback_marking_lines(
                written[matched[0]],
                (segment for row in uv if row.side_piece_id == side
                 for segment in row.marking_segments),
                # The same current resolved SIDE source generated the DXF.
                # Independently verify all original + EAR MARKING lines.
                check_scene=source.scene,
            )
        result = _atomic_commit_staged_dxfs(
            written, root, overwrite=overwrite,
        )
    return FormedFixingPlateManufacturingReceipt(
        output_paths=tuple((key, result[key]) for key in written),
        formed_part_ids=tuple(verified),
        side_marked_piece_ids=("box_body:left_side", "box_body:right_side"),
        source_sha256=SOURCE_DXF_SHA256,
        physical_contact_area_mm2=sum(x.physical_contact_area_mm2 for x in side_contact),
    )


def save_verified_receiving_csv_selected_sheets(
    snapshot, original_geometry, selected_geometry, output_dir, *,
    overwrite=False,
):
    """Normal DXF when only door/base selected, without forcing SIDE selection.

    Same single source + source-geometry/CHECK-Q/installed-XYZ proof as full
    Receiving output. No fake EAR or unrequested physical SIDE DXFs.
    """
    from .manufacturing_export import (
        _reject_unapproved_nfb_pad_ear_manufacturing,
        reject_unverified_receiving_nfb_tier_base,
        _validate_nfb_base_part_scope,
    )
    approved = _verified_current_csv_manufacturing_owners(
        snapshot, original_geometry, selected_geometry,
    )
    rows = tuple(
        (key, _resolved_physical_dxf_filename(key), render)
        for key,render in resolved_physical_render_parts(selected_geometry)
    )
    if not rows or not approved:
        raise ValueError("RECEIVING_CSV_SELECTED_NO_PHYSICAL_NFB_SHEETS")
    nfb_rows = {
        key for key,_,render in rows
        if (key == "base_plate" or key.startswith("base_plate:nfb_layer:")
            or (getattr(render,"metadata",None) or {}).get("nfb_v5_trial_status"))
    }
    if not nfb_rows.issubset(approved):
        raise ValueError("RECEIVING_CSV_SELECTED_UNVERIFIED_PART")
    _reject_unapproved_nfb_pad_ear_manufacturing(rows)
    for key,_,render in rows:
        if key not in approved:
            reject_unverified_receiving_nfb_tier_base(render,output_key=key)
    _validate_nfb_base_part_scope(
        tuple(row for row in rows if row[0] not in approved),part_only=False,
    )
    if len({key for key,_,_ in rows}) != len(rows):
        raise ValueError("RECEIVING_CSV_SELECTED_DUPLICATED_PHYSICAL_OWNER")
    root=Path(output_dir)
    if not overwrite and any((root/name).exists() for _,name,_ in rows):
        raise FileExistsError("RECEIVING_CSV_SELECTED_EXISTING_DXF")
    root.mkdir(parents=True,exist_ok=True)
    with TemporaryDirectory(prefix=".whd-csv-selected-",dir=str(root)) as stage:
        candidates={}
        for key,name,render in rows:
            target=Path(stage)/name
            if key in approved:
                from .dxf_serialization import save_scene_dxf
                save_scene_dxf(target,render.scene)
            else:
                save_part_render_data_dxf(render,target,overwrite=False)
            receipt=verify_saved_part_render_data_dxf(render,target)
            if not receipt.ok:
                raise ValueError("RECEIVING_CSV_SELECTED_DXF_REOPEN_FAILED:" + key)
            candidates[key]=target
        return _atomic_commit_staged_dxfs(
            candidates,root,overwrite=overwrite,
        )
