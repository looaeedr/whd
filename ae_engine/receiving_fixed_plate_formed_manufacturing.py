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
        raise ValueError("EAR_FORM_MFG_QUANTITY_NEEDS_EACH_VERSION")
    uv, side_contact, side_parts, side_scenes = _verified_pair(
        snapshot, original_geometry, dimensions=dimensions,
        sheet_thickness=sheet_thickness,
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
    _reject_unapproved_nfb_pad_ear_manufacturing(standard_rows)
    for key, _, render in standard_rows:
        reject_unverified_receiving_nfb_tier_base(render, output_key=key)
        if (getattr(render, "metadata", None) or {}).get(
            "receiving_base_plate_unconfigured"
        ) is True:
            raise ValueError("EAR_FORM_MFG_SELECTED_UNCONFIGURED_BASE")
    _validate_nfb_base_part_scope(standard_rows, part_only=False)
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
