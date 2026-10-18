# -*- coding: utf-8 -*-
"""#1503: verify real assembled Base Plate skins against the four source EARs.

An independent *read-only* geometric receipt. This does NOT infer the missing
large-ear forming direction, weld seam, side-sheet flat UV or manufacturing
approval. Source EAR parts have the actual T2 BEND, not yet an approved signed
90-degree formed solid or completed weld. No DXF conversions or output are performed.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite
from typing import Mapping


TOLERANCE_MM = 1e-6


@dataclass(frozen=True)
class TierFixingContactReceipt:
    ear_part_id: str
    base_part_id: str
    layer_index: int
    side: str
    fixing_hole_world_x_mm: float
    fixing_hole_world_y_mm: tuple[float, float]
    side_skin_world_x_mm: float
    actual_base_back_skin_world_z_mm: float
    expected_ear_contact_world_z_mm: float
    source_outline_verified: bool = True
    base_assembly_xyz_verified: bool = True
    formed_ear_verified: bool = False
    side_marking_export_approved: bool = False
    manufacturing_ready: bool = False


def _same(lhs, rhs):
    return (isfinite(float(lhs)) and isfinite(float(rhs))
            and isclose(float(lhs), float(rhs), rel_tol=0,
                        abs_tol=TOLERANCE_MM))


def validate_receiving_tier_fixing_contact_receipts(
    snapshot: Mapping[str, object],
    assembly_parts,
) -> tuple[TierFixingContactReceipt, ...]:
    """Fail closed if a source EAR's XYZ doesn't agree with the *actual* Base Plate.

    A target-vs-target test is not enough: consume the assembled FinalScene
    Base Plate's real offset, source topology and folded NFB mounting skin,
    each physical EAR's own real revised T2 source material, and the independently
    derived side-wall mount column. One and two tiers share this same check.
    """
    from .receiving_base_fixing_plate_geometry import (
        SOURCE_DXF_SHA256, build_fixing_plate_source_render_data,
    )
    from .receiving_base_plate_config import receiving_base_plate_values
    from .receiving_base_plate_real_skins import receiving_base_actual_local_nfb_skins
    from .receiving_tier_ear_assembly_xy import resolve_receiving_tier_ear_mating_xy
    from .receiving_tier_ear_z_targets import (
        resolve_receiving_tier_base_z_targets,
        resolve_receiving_tier_ear_contact_targets,
    )
    from .sheetmetal_drawing import PolylinePrimitive

    if not isinstance(snapshot, Mapping) or snapshot.get("nfb_config_submitted") is not True:
        raise ValueError("EAR_RECEIPT_REQUIRES_CURRENT_SUBMITTED_NFB_SOURCE")
    xy = resolve_receiving_tier_ear_mating_xy(snapshot)
    contacts = resolve_receiving_tier_ear_contact_targets(snapshot)
    depths = resolve_receiving_tier_base_z_targets(snapshot)
    if (not xy or len(xy) not in (2, 4)
            or len(contacts) != len(xy)
            or len(depths) * 2 != len(xy)):
        raise ValueError("EAR_RECEIPT_INCOMPLETE_PHYSICAL_OWNERS")
    by_ear = {row.ear_id: row for row in contacts}
    by_base = {row.parent_base_id: row for row in depths}
    if len(by_ear) != len(contacts) or len(by_base) != len(depths):
        raise ValueError("EAR_RECEIPT_DUPLICATE_SOURCE_IDENTITY")
    expected_bases = set(by_base)
    actual = [part for part in tuple(assembly_parts or ())
              if str(getattr(part, "part_key", "")) in expected_bases]
    bases = {str(part.part_key): part for part in actual}
    if len(bases) != len(actual) or set(bases) != expected_bases:
        raise ValueError("EAR_RECEIPT_ACTUAL_BASE_PART_MISSING_OR_DUPLICATED")
    physical = receiving_base_plate_values(snapshot)
    if not isinstance(physical, Mapping):
        raise ValueError("EAR_RECEIPT_SOURCE_BASE_VARIANT_MISSING")

    result = []
    for xy_row in xy:
        target = by_ear.get(xy_row.ear_id)
        base = bases.get(xy_row.parent_base_id)
        depth = by_base.get(xy_row.parent_base_id)
        if (target is None or depth is None or base is None
                or target.parent_base_id != xy_row.parent_base_id
                or target.layer_index != xy_row.layer_index
                or target.side != xy_row.side
                or depth.layer_index != xy_row.layer_index):
            raise ValueError("EAR_RECEIPT_CROSS_TIER_OR_SIDE_IDENTITY_DRIFT")
        if (not depth.physical_skin_z_resolved
                or not target.base_skin_z_source_verified
                or depth.world_offset_z_mm is None
                or depth.base_back_skin_world_z_mm is None
                or target.target_ear_contact_world_z_mm is None):
            raise ValueError("EAR_RECEIPT_SOURCE_Z_NOT_VERIFIED")
        if getattr(base, "placement", None) != "offset":
            raise ValueError("EAR_RECEIPT_BASE_NOT_OFFSET_PLACED")
        offset = tuple(getattr(base, "offset", ()))
        if (len(offset) != 3
                or not _same(offset[0], 0.0)
                or not _same(offset[1], xy_row.base_center_y_mm)
                or not _same(offset[2], depth.world_offset_z_mm)):
            raise ValueError("EAR_RECEIPT_ACTUAL_BASE_XYZ_DRIFT")
        render = getattr(base, "render_data", None)
        topology = getattr(render, "unfolded_topology", None)
        if (getattr(topology, "piece_id", None) != xy_row.parent_base_id
                or getattr(render, "scene", None) is None
                or getattr(render, "material", None) is None
                or render.material.is_empty):
            raise ValueError("EAR_RECEIPT_ACTUAL_BASE_SOURCE_MISSING")
        metadata = dict(getattr(render, "metadata", {}) or {})
        if metadata.get("manufacturing_ready") is True:
            raise ValueError("EAR_RECEIPT_PREMATURE_MFG_RELEASE")
        if xy_row.parent_base_id.startswith("base_plate:nfb_layer:"):
            if (metadata.get("nfb_layer_index") != xy_row.layer_index
                    or metadata.get("nfb_tier_real_skin_z_resolved") is not True):
                raise ValueError("EAR_RECEIPT_ACTUAL_BASE_LAYER_SOURCE_DRIFT")
        local = dict(physical)
        local["receiving_nfb_depth_pair_mm"] = (
            tuple(depth.source_depths_mm) if len(depth.source_depths_mm) == 2
            else None
        )
        front, _ = receiving_base_actual_local_nfb_skins(snapshot, local)
        back_skin_z = float(offset[2]) + front - float(snapshot["t"])
        if (not _same(back_skin_z, depth.base_back_skin_world_z_mm)
                or not _same(back_skin_z, target.target_ear_contact_world_z_mm)
                or not _same(back_skin_z, target.base_back_skin_world_z_mm)):
            raise ValueError("EAR_RECEIPT_REAL_BACK_SKIN_CONTACT_Z_DRIFT")
        if (not _same(xy_row.selected_slot_column_x_mm,
                      target.fixing_hole_world_x_mm)
                or xy_row.selected_slot_pair_world_y_mm != target.fixing_hole_world_y_mm
                or not _same(xy_row.side_inside_weld_x_mm,
                             target.side_inside_weld_x_mm)):
            raise ValueError("EAR_RECEIPT_REAL_MOUNT_XY_DRIFT")
        source = build_fixing_plate_source_render_data(
            xy_row.ear_id, snapshot=snapshot,
        )
        ear_meta = dict(source.metadata)
        if (ear_meta.get("stable_id") != xy_row.ear_id
                or ear_meta.get("parent_base_id") != xy_row.parent_base_id
                or ear_meta.get("source_dxf_sha256") != SOURCE_DXF_SHA256
                or ear_meta.get("source_cutting_verified") is not True
                or not _same(ear_meta.get("thickness"), 2.0)
                or ear_meta.get("source_bend_verified") is not True
                or not _same(ear_meta.get("source_bend_line_mm"), 23.0)
                or ear_meta.get("formed_direction_verified") is not False
                or ear_meta.get("formed_geometry_verified") is not False
                or ear_meta.get("weld_z_verified") is not False
                or ear_meta.get("manufacturing_ready") is not False):
            raise ValueError("EAR_RECEIPT_SOURCE_EAR_NOT_AUTHENTIC_OR_UNFORMED")
        cuts = [p for p in source.scene.primitives
                if isinstance(p, PolylinePrimitive)
                and p.layer == "CUTTING" and p.closed]
        if (len(cuts) != 5 or len(source.fold_guides) != 1
                or source.fold_guides[0].axis != "y"
                or not _same(source.fold_guides[0].position, 23.0)
                or not _same(source.fold_guides[0].span_start, 0.0)
                or not _same(source.fold_guides[0].span_end, 256.0)):
            raise ValueError("EAR_RECEIPT_SOURCE_EAR_CUTTING_OR_BEND_DRIFT")
        if (not _same(ear_meta.get("nominal_base_fixing_hole_world_x_mm"),
                      xy_row.selected_slot_column_x_mm)
                or tuple(ear_meta.get("nominal_base_fixing_hole_world_y_mm", ()))
                   != xy_row.selected_slot_pair_world_y_mm):
            raise ValueError("EAR_RECEIPT_EAR_SOURCE_MATING_DRIFT")
        result.append(TierFixingContactReceipt(
            ear_part_id=xy_row.ear_id,
            base_part_id=xy_row.parent_base_id,
            layer_index=xy_row.layer_index,
            side=xy_row.side,
            fixing_hole_world_x_mm=xy_row.selected_slot_column_x_mm,
            fixing_hole_world_y_mm=xy_row.selected_slot_pair_world_y_mm,
            side_skin_world_x_mm=xy_row.side_inside_weld_x_mm,
            actual_base_back_skin_world_z_mm=back_skin_z,
            expected_ear_contact_world_z_mm=target.target_ear_contact_world_z_mm,
        ))
    if len({r.ear_part_id for r in result}) != len(result):
        raise ValueError("EAR_RECEIPT_REUSED_PHYSICAL_SOURCE_EAR")
    return tuple(result)
