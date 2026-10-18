# -*- coding: utf-8 -*-
"""#1503: READBACK-VERIFIED Receiving EAR side-sheet CHECK-ONLY DXF pair.

This is an isolated inspection artifact. Never send its altered FinalScene
into production ResolvedManufacturingGeometry, MFG-2, NC or BOM sinks.
Only verified original W800/T2 folded SIDE and EAR worlds may participate.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory
from math import isclose

import ezdxf

from .manufacturing_api import (
    save_part_render_data_dxf,
    verify_saved_part_render_data_dxf,
)
from .manufacturing_export import _atomic_commit_staged_dxfs
from .manufacturing_scene_access import owner_render_data
from .receiving_fixed_plate_side_mark_preview import (
    build_receiving_ear_side_marking_previews,
)
from .receiving_fixed_plate_side_uv_marking import (
    resolve_receiving_ear_side_uv_receipts,
)
from .receiving_fixed_plate_weld_skin_mating import (
    resolve_receiving_ear_side_skin_mating_witnesses,
)
from .dxf_acceptance import _same_line_geometry


_SIDE_NAMES = {
    "box_body:left_side": "WHD_EAR_LEFT_SIDE_CHECK_ONLY.dxf",
    "box_body:right_side": "WHD_EAR_RIGHT_SIDE_CHECK_ONLY.dxf",
}


@dataclass(frozen=True)
class ReceivingEarSideCheckDxfReceipt:
    output_paths: tuple[tuple[str, str], ...]
    part_ids: tuple[str, ...]
    physical_contact_area_mm2: float
    marking_lines_verified: int
    saved_dxf_roundtrip_verified: bool = True
    manufacturing_ready: bool = False
    welding_workmanship_certified: bool = False
    status: str = "RECEIVING_EAR_SIDE_CHECK_DXF_ONLY"


def _verified_pair(snapshot, geometry, *, dimensions, sheet_thickness):
    if (snapshot.get("model") != "受電箱"
            or snapshot.get("nfb_config_submitted") is not True
            or len(tuple(dimensions or ())) != 3
            or not isclose(float(snapshot["w"]), 800., abs_tol=1e-8)
            or not isclose(float(snapshot["t"]), 2., abs_tol=1e-8)
            or not isclose(float(sheet_thickness), 2., abs_tol=1e-8)
            or any(not isclose(float(snapshot[k]), float(dimensions[i]), abs_tol=1e-8)
                   for i, k in enumerate(("w", "h", "d")))):
        raise ValueError("EAR_SIDE_CHECK_REQUIRES_CURRENT_W800_T2_SUBMITTED_SNAPSHOT")

    from phase6_manufacturing_geometry import _phase6_build_joint_world_geometry
    world = _phase6_build_joint_world_geometry(
        tuple(geometry.parts or ()), tuple(float(v) for v in dimensions), 2.,
    )
    uv = resolve_receiving_ear_side_uv_receipts(
        snapshot, world_geometry=world, geometry=geometry,
    )
    physical = resolve_receiving_ear_side_skin_mating_witnesses(
        snapshot, world_geometry=world,
    )
    if len(uv) not in (2, 4) or len(physical) != len(uv):
        raise ValueError("EAR_SIDE_CHECK_INCOMPLETE_SIDE_TIER_SET")
    physical_by_id = {row.ear_part_id: row for row in physical}
    if len(physical_by_id) != len(physical):
        raise ValueError("EAR_SIDE_CHECK_DUPLICATE_PHYSICAL_CONTACT")
    if {row.ear_part_id for row in uv} != set(physical_by_id):
        raise ValueError("EAR_SIDE_CHECK_UV_PHYSICAL_OWNER_MISMATCH")
    for row in uv:
        witness = physical_by_id[row.ear_part_id]
        if (row.base_part_id != witness.base_part_id
                or row.side_piece_id != witness.side_piece_id
                or row.nfb_layer_index != witness.nfb_layer_index
                or not witness.flange_skin_normal_opposed
                or not witness.panel_inside_skin_source_verified
                or not witness.full_contact_material_coverage_verified
                or not witness.no_through_side_skin_penetration_verified
                or witness.welding_workmanship_certified
                or witness.manufacturing_ready
                or row.manufacturing_ready
                or row.weld_contact_verified
                or not isclose(witness.physical_contact_area_mm2, 5632., abs_tol=1.)):
            raise ValueError("EAR_SIDE_CHECK_PHYSICAL_CONTACT_NOT_CERTIFIED")

    side_parts = {
        key: owner_render_data(geometry, key) for key in _SIDE_NAMES
    }
    if any(part is None for part in side_parts.values()):
        raise ValueError("EAR_SIDE_CHECK_SIDE_SOURCE_MISSING")
    previews = build_receiving_ear_side_marking_previews(uv, side_parts)
    if set(previews) != set(_SIDE_NAMES):
        raise ValueError("EAR_SIDE_CHECK_PREVIEW_OWNER_DRIFT")
    return uv, physical, side_parts, previews


def _readback_marking_lines(path, expected_segments):
    """Strict one-to-one source-world-derived MARKING line readback.

    Generic DXF acceptance covers total layer counts and stock geometry;
    this additionally verifies each new weld-footprint LINE coordinate,
    rather than merely accepting a matching number of unrelated lines.
    """
    modelspace = ezdxf.readfile(path).modelspace()
    actual = [
        (float(e.dxf.start.x), float(e.dxf.start.y),
         float(e.dxf.end.x), float(e.dxf.end.y))
        for e in modelspace
        if e.dxftype() == "LINE" and str(e.dxf.layer).upper() == "MARKING"
    ]
    expected = [
        (float(p1[0]), float(p1[1]), float(p2[0]), float(p2[1]))
        for p1, p2 in expected_segments
    ]
    for line in expected:
        match = next(
            (i for i, actual_line in enumerate(actual)
             if _same_line_geometry(line, actual_line, 1e-6)),
            None,
        )
        if match is None:
            raise ValueError("EAR_SIDE_CHECK_SAVED_MARKING_UV_LINE_MISSING")
        actual.pop(match)


def export_receiving_ear_side_check_only_dxf(
    snapshot, geometry, output_dir, *, dimensions, sheet_thickness,
    overwrite=False,
) -> ReceivingEarSideCheckDxfReceipt:
    """Write and independently reopen BOTH side sheets or commit NEITHER.

    Only side MARKING preview copies are serialized, *not* real manufacturing
    geometry. A failed side check, roundtrip, or output collision leaves no
    published partial pair. Names explicitly identify check-only status.
    """
    uv, physical, parts, previews = _verified_pair(
        snapshot, geometry, dimensions=dimensions, sheet_thickness=sheet_thickness,
    )
    by_side = {
        side: tuple(row for row in uv if row.side_piece_id == side)
        for side in _SIDE_NAMES
    }
    if any(not rows for rows in by_side.values()):
        raise ValueError("EAR_SIDE_CHECK_BOTH_SIDE_MARKINGS_REQUIRED")
    root = Path(output_dir)
    # Preflight both target filenames before any directory or DXF is made.
    if not overwrite:
        for name in _SIDE_NAMES.values():
            if (root / name).exists():
                raise FileExistsError(str(root / name))
    root.mkdir(parents=True, exist_ok=True)
    staged = {}
    with TemporaryDirectory(prefix=".whd-ear-check-stage-", dir=root) as temp:
        for side, filename in _SIDE_NAMES.items():
            original = parts[side]
            metadata = {
                **dict(original.metadata or {}),
                "receiving_ear_check_only": True,
                "receiving_ear_check_uv_verified": True,
                "receiving_ear_check_physical_contact_verified": True,
                "manufacturing_ready": False,
                "welding_workmanship_certified": False,
                "ear_side_mfg2_release_approved": False,
            }
            check_render = replace(
                original, scene=previews[side], metadata=metadata,
            )
            staged_path = Path(temp) / filename
            save_part_render_data_dxf(
                check_render, staged_path, overwrite=False,
            )
            accepted = verify_saved_part_render_data_dxf(
                check_render, staged_path,
            )
            if not accepted.ok:
                raise ValueError(
                    "EAR_SIDE_CHECK_SAVED_DXF_ROUNDTRIP_FAILED:" + side
                )
            _readback_marking_lines(
                staged_path,
                (segment for row in by_side[side] for segment in row.marking_segments),
            )
            staged[side] = staged_path
        committed = _atomic_commit_staged_dxfs(
            staged, root, overwrite=overwrite,
        )
    return ReceivingEarSideCheckDxfReceipt(
        output_paths=tuple((side, committed[side]) for side in _SIDE_NAMES),
        part_ids=tuple(sorted(row.ear_part_id for row in uv)),
        physical_contact_area_mm2=sum(
            row.physical_contact_area_mm2 for row in physical
        ),
        marking_lines_verified=sum(
            len(row.marking_segments) for row in uv
        ),
    )
