"""Canonical physical DXF export and Receiving EAR / NFB manufacturing proof.

No GUI imports or UI state. The caller supplies authoritative resolved source
geometry and operator part-selection intent; WHD Engine owns actual sheets,
manufacturing eligibility, atomic export, and physical DXF re-open checks.
"""
from .manufacturing_export_selection import select_resolved_export_geometry


def selected_export_manufacturing_policy(receiving_snapshot, flags):
    """Engine-owned classification of Receiving NFB and side manufacturing."""
    auto_side = (
        bool(flags.get("box_body"))
        and receiving_snapshot.get("model") == "受電箱"
        and receiving_snapshot.get("nfb_config_submitted") is True
    )
    committed_csv = ()
    if (receiving_snapshot.get("model") == "受電箱"
            and receiving_snapshot.get("nfb_config_submitted") is True):
        from .receiving_nfb_committed_final_scene import _submitted_csv_holes
        committed_csv = _submitted_csv_holes(receiving_snapshot)
    return auto_side, committed_csv


def save_selected_resolved_manufacturing_dxf(
    receiving_snapshot, resolved, flags, folder,
):
    """Return verified physical output paths; derive all decisions from source."""
    from . import manufacturing_api
    auto_side, committed_csv = selected_export_manufacturing_policy(
        receiving_snapshot, flags,
    )

    if auto_side:
        from ae_engine.receiving_ear_side_manufacturing_marking import (
            with_verified_receiving_ear_side_markings,
        )
        dimensions = tuple(
            float(receiving_snapshot[key]) for key in ("w", "h", "d")
        )
        sheet_thickness = float(receiving_snapshot["t"])
        unmarked = resolved
        resolved = with_verified_receiving_ear_side_markings(
            receiving_snapshot, unmarked,
            dimensions=dimensions, sheet_thickness=sheet_thickness,
        )
    selected = select_resolved_export_geometry(resolved, flags)
    if not tuple(getattr(selected, "parts", ()) or ()):
        return {}

    # Current submitted Receiving Base Plates own physical fixing sheets.
    # Validate real signed folds / side weld contact before committing those
    # source CUTTING/BEND sheets WITH the ordinary SIDE MARKING in one batch.
    # Historical side-only scenes without an installed base stay compatible.
    physical_base_present = auto_side and any(
        str(getattr(part, "part_key", "")) == "base_plate"
        or str(getattr(part, "part_key", "")).startswith("base_plate:nfb_layer:")
        for part in tuple(getattr(unmarked, "parts", ()) or ())
    )
    if physical_base_present:
        from ae_engine.receiving_fixed_plate_formed_manufacturing import (
            save_verified_receiving_formed_fixing_plate_bundle,
        )
        # Exactly the installed original physical inventory, not merely
        # BODY + CSV DOOR + BASE, may earn a whole-cabinet software MFG-2
        # receipt. Partial selected DXF is still a valid independent export.
        from ae_engine.manufacturing_export import resolved_physical_render_parts
        original_sheets = {
            key for key, _ in resolved_physical_render_parts(unmarked)
        }
        selected_sheets = {
            key for key, _ in resolved_physical_render_parts(selected)
        }
        certify_whole_software = (
            bool(committed_csv)
            and original_sheets == selected_sheets
            and bool(original_sheets)
            # First-family-switch scenes legitimately retain standalone
            # preview pieces. Their selected DXF must still work, but they
            # are NOT a certified whole assembled cabinet.
            and all(
                getattr(p, "placement", None) != "standalone"
                for p in tuple(getattr(unmarked, "parts", ()) or ())
            )
            and bool(flags.get("box_body"))
            and bool(flags.get("door"))
            and bool(flags.get("base_plate"))
        )
        bundle = save_verified_receiving_formed_fixing_plate_bundle(
            receiving_snapshot, unmarked, selected, folder,
            dimensions=dimensions, sheet_thickness=sheet_thickness,
            overwrite=True,
            # #1490: source-complete selected BODY/DOOR/BASE brings its
            # physical PAD into the same atomic DXF set. Other selected
            # sheet combinations remain independently legal.
            require_complete_cabinet_inventory=(
                bool(flags.get("box_body")) and bool(flags.get("door"))
                and bool(flags.get("base_plate")) and bool(committed_csv)
            ),
            certify_software_mfg2=certify_whole_software,
        )
        outputs = dict(bundle.output_paths)
        if bundle.software_mfg2_receipt_path:
            outputs["__whd_1490_software_mfg2__"] = (
                bundle.software_mfg2_receipt_path
            )
    elif committed_csv and bool(flags.get("door") or flags.get("base_plate")):
        from ae_engine.receiving_fixed_plate_formed_manufacturing import (
            save_verified_receiving_csv_selected_sheets,
        )
        outputs = save_verified_receiving_csv_selected_sheets(
            receiving_snapshot, resolved, selected, folder,
            overwrite=True,
        )
    else:
        outputs = manufacturing_api.save_resolved_manufacturing_geometry_dxf(
            selected, folder, overwrite=True,
        )
    if auto_side:
        # Independently reopen the actual serialized SIDE drawings and compare
        # every source-world-derived MARKING coordinate before the outer
        # selected-DXF batch can be committed to the operator's folder.
        from ae_engine.receiving_fixed_plate_side_check_dxf import (
            _verified_pair, _readback_marking_lines,
        )
        from ae_engine.manufacturing_scene_access import owner_render_data
        from ae_engine.manufacturing_api import verify_saved_part_render_data_dxf
        receipts, _, _, _ = _verified_pair(
            receiving_snapshot, unmarked,
            dimensions=dimensions, sheet_thickness=sheet_thickness,
            permit_independent_source_marking_crossing=True,
        )
        for side in ("box_body:left_side", "box_body:right_side"):
            physical = owner_render_data(resolved, side)
            # Resolve the actual canonical physical row by its immutable
            # render-data identity, not by a fabricated part_id/filename:
            # BoxBody composite role keys are e.g. box_body:box_body_left_side.
            from ae_engine.manufacturing_export import (
                resolved_physical_render_parts,
            )
            matching_keys = tuple(
                part_id for part_id, render_data
                in resolved_physical_render_parts(selected)
                if render_data is physical and part_id.startswith("box_body:")
            )
            if physical is None or len(matching_keys) != 1:
                raise ValueError("EAR_SIDE_NORMAL_EXPORT_SIDE_OWNER_AMBIGUOUS")
            target = outputs.get(matching_keys[0])
            if not target:
                raise ValueError("EAR_SIDE_NORMAL_EXPORT_SIDE_OUTPUT_MISSING")
            if not verify_saved_part_render_data_dxf(physical, target).ok:
                raise ValueError("EAR_SIDE_NORMAL_EXPORT_SAVED_DXF_INVALID")
            _readback_marking_lines(
                target, (
                    segment
                    for row in receipts if row.side_piece_id == side
                    for segment in row.marking_segments
                ),
                # The NORMAL manufacturing SIDE scene contains both the
                # certified EAR lines and its pre-existing source MARKING.
                # Compare the entire current resolved physical source to the
                # independently reopened DXF, not EAR rows alone. The reader
                # still rejects every unowned or duplicate MARKING LINE.
                check_scene=physical.scene,
            )
    return outputs
