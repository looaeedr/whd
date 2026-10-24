# -*- coding: utf-8 -*-
"""#1503: source-authenticated EAR MARKING in ordinary SIDE manufacturing DXFs.

Scope is deliberately *two physical side panels only*: verified left/right
W800/T2 CUTTING+BEND+MARKING. This is not a fabricated EAR part, PAD,
full-cabinet NFB MFG-2 release, or welding-workmanship certification.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from math import isclose
from pathlib import Path

from .manufacturing_api import save_part_render_data_dxf, verify_saved_part_render_data_dxf
from .manufacturing_export import (
    _save_resolved_rows_atomic,
    resolved_physical_dxf_filename,
)
from .receiving_fixed_plate_side_check_dxf import (
    _SIDE_NAMES,
    _readback_marking_lines,
    _verified_pair,
)


@dataclass(frozen=True)
class ReceivingEarSideManufacturingMarkingReceipt:
    output_paths: tuple[tuple[str, str], ...]
    physical_ear_ids: tuple[str, ...]
    marking_lines_verified: int
    material_skin_contact_area_mm2: float
    saved_roundtrip_verified: bool = True
    side_only_manufacturing_marking_verified: bool = True
    whole_cabinet_manufacturing_ready: bool = False
    welding_workmanship_certified: bool = False
    status: str = "EAR_SIDE_ONLY_MFG_MARKING_VERIFIED"



def with_verified_receiving_ear_side_markings(
    snapshot, geometry, *, dimensions, sheet_thickness,
):
    """Immutable, source-verified replacement for canonical box-body DXF data.

    Operates *before* ordinary manufacture export: only real left/right SIDE
    drawing scenes acquire EAR weld-position MARKING; all other physical
    owners and normal DXF guards remain unchanged. No preview/CHECK scene
    becomes a release authority and no source geometry is mutated.
    """
    from .manufacturing_scene_access import replace_owner_render_data
    uv, physical, parts, scenes = _verified_pair(
        snapshot, geometry, dimensions=dimensions,
        sheet_thickness=sheet_thickness,
        permit_independent_source_marking_crossing=True,
    )
    side_keys = ("box_body:left_side", "box_body:right_side")
    if set(parts) != set(side_keys) or set(scenes) != set(side_keys):
        raise ValueError("EAR_SIDE_NORMAL_EXPORT_SOURCE_SIDE_PAIR_MISSING")
    if len(uv) not in (2, 4):
        raise ValueError("EAR_SIDE_NORMAL_EXPORT_INCOMPLETE_SIDE_MARKING")
    if len({row.ear_part_id for row in uv}) != len(uv):
        raise ValueError("EAR_SIDE_NORMAL_EXPORT_DUPLICATE_SOURCE")
    result = geometry
    for side in side_keys:
        source = parts[side]
        source_meta = dict(source.metadata or {})
        if (source_meta.get("receiving_ear_check_only")
                or source_meta.get("ear_side_mark_preview_only")
                or source_meta.get("ear_side_mfg2_release_approved")):
            raise ValueError("EAR_SIDE_NORMAL_EXPORT_TAINTED_SOURCE")
        segments = sum(
            len(row.marking_segments) for row in uv if row.side_piece_id == side
        )
        if segments != (len(uv) // 2) * 4:
            raise ValueError("EAR_SIDE_NORMAL_EXPORT_INCOMPLETE_SIDE_MARKING")
        verified = replace(
            source, scene=scenes[side],
            metadata={
                **source_meta,
                "receiving_ear_side_marking_provenance": "SOURCE_T2_BEND23_3D_CONTACT_UV",
                "receiving_ear_side_manufacturing_scope": "SIDE_SHEET_MARKING_ONLY",
                "receiving_ear_side_marking_segment_count": segments,
                "manufacturing_ready": False,
                "welding_workmanship_certified": False,
            },
        )
        result = replace_owner_render_data(result, side, verified)
    return result


def export_receiving_ear_side_manufacturing_marking_dxf(
    snapshot,
    geometry,
    output_dir,
    *,
    dimensions,
    sheet_thickness,
    overwrite=False,
) -> ReceivingEarSideManufacturingMarkingReceipt:
    """Manufacturing side plates with verified physical EAR weld-position marks.

    The real source-formed EAR and world-to-UV mapped side geometry MUST pass
    the same independent 3D mating/2D CUTTING/BEND/source feature tests as
    CHECK/Q. Export ordinary physical side DXFs using the existing atomic
    manufacturing sink and *its* filenames. Do not mutate canonical geometry.
    The normal full-cabinet/PAD/EAR manufacturing guards remain untouched.
    """
    if str(snapshot.get("active_mode") or "") == "quantity":
        raise ValueError("EAR_SIDE_MFG_QUANTITY_REQUIRES_PER_VERSION_SOURCE")
    if type(overwrite) is not bool:
        raise TypeError("EAR_SIDE_MFG_OVERWRITE_MUST_BE_BOOLEAN")

    uv, physical, parts, previews = _verified_pair(
        snapshot, geometry,
        dimensions=dimensions, sheet_thickness=sheet_thickness,
        permit_independent_source_marking_crossing=True,
    )
    # The only supported output is precisely one LEFT and RIGHT physical
    # sheet, not an EAR/PAD blank or a merged multi-bay DXF inventory.
    side_keys = ("box_body:left_side", "box_body:right_side")
    if set(parts) != set(side_keys) or set(previews) != set(side_keys):
        raise ValueError("EAR_SIDE_MFG_EXACT_SIDE_PAIR_REQUIRED")
    if len({r.ear_part_id for r in uv}) != len(uv):
        raise ValueError("EAR_SIDE_MFG_DUPLICATE_EAR")
    if not all(isclose(w.physical_contact_area_mm2, 5632., abs_tol=1.) for w in physical):
        raise ValueError("EAR_SIDE_MFG_SOURCE_CONTACT_AREA_MISMATCH")
    by_side = {
        side: tuple(row for row in uv if row.side_piece_id == side)
        for side in side_keys
    }
    if any(len(rows) != len(uv) // 2 for rows in by_side.values()):
        raise ValueError("EAR_SIDE_MFG_INCOMPLETE_LAYER_SIDE_PAIR")

    # The source panel's physical material, CUTTING and BEND are unchanged.
    # Add ONLY validated positioning MARKING segments to each isolated copy.
    rows = []
    for side in side_keys:
        source = parts[side]
        if source is None:
            raise ValueError("EAR_SIDE_MFG_PHYSICAL_SIDE_SOURCE_MISSING")
        meta = dict(source.metadata or {})
        if (meta.get("receiving_ear_check_only")
                or meta.get("ear_side_mark_preview_only")
                or meta.get("ear_side_mfg2_release_approved")):
            raise ValueError("EAR_SIDE_MFG_SOURCE_PREVIEW_OR_APPROVAL_TAINT")
        side_render = replace(
            source,
            scene=previews[side],
            metadata={
                **meta,
                "receiving_ear_side_marking_provenance": "SOURCE_T2_BEND23_3D_CONTACT_UV",
                "receiving_ear_side_manufacturing_scope": "SIDE_SHEET_MARKING_ONLY",
                "receiving_ear_side_marking_segment_count": sum(
                    len(row.marking_segments) for row in by_side[side]
                ),
                # Explicitly not a CABINET/WELD/NC authorization.
                "manufacturing_ready": False,
                "welding_workmanship_certified": False,
            },
        )
        standard_name = resolved_physical_dxf_filename(
            side,
            box_body_physical_piece_roles={"left_side", "right_side"},
        )
        rows.append((side, standard_name, side_render))

    from .sheetmetal_drawing import LinePrimitive

    segments = {
        side: tuple(
            ((float(p.p1.x), float(p.p1.y)), (float(p.p2.x), float(p.p2.y)))
            for p in tuple(getattr(parts[side].scene, "primitives", ()) or ())
            if isinstance(p, LinePrimitive)
            and str(getattr(p, "layer", "") or "").upper() == "MARKING"
        ) + tuple(segment for row in by_side[side] for segment in row.marking_segments)
        for side in side_keys
    }

    def save_and_verify(render, path, *, overwrite):
        written = save_part_render_data_dxf(render, path, overwrite=overwrite)
        verified = verify_saved_part_render_data_dxf(render, path)
        if not verified.ok:
            raise ValueError("EAR_SIDE_MFG_SAVED_DXF_ROUNDTRIP_FAILED")
        # The physical side ID is derived from the filename/row, never from
        # user-provided metadata. Compare every actual output MARKING LINE.
        key = next((side for side in side_keys
                    if Path(path).name == resolved_physical_dxf_filename(
                        side,
                        box_body_physical_piece_roles={"left_side", "right_side"},
                    )), None)
        if key is None:
            raise ValueError("EAR_SIDE_MFG_NONSTANDARD_OUTPUT_NAME")
        _readback_marking_lines(written, segments[key])
        return written

    result = _save_resolved_rows_atomic(
        rows,
        output_dir,
        save_part_render_data_dxf=save_and_verify,
        overwrite=overwrite,
        part_only=True,
    )
    if set(result) != set(side_keys):
        raise ValueError("EAR_SIDE_MFG_ATOMIC_RESULT_INCOMPLETE")
    return ReceivingEarSideManufacturingMarkingReceipt(
        output_paths=tuple((side, str(result[side])) for side in side_keys),
        physical_ear_ids=tuple(sorted(row.ear_part_id for row in uv)),
        marking_lines_verified=sum(len(row.marking_segments) for row in uv),
        material_skin_contact_area_mm2=sum(
            row.physical_contact_area_mm2 for row in physical
        ),
    )
