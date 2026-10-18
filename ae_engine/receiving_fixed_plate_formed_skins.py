# -*- coding: utf-8 -*-
"""#1503: source-derived 90° large EAR formed world skin, no extra user signoff.

The revised 2026-10-18 固定片.dxf ALREADY defines actual T2 BEND y=23.
Unlike source-flat/CUTTING previews, this maps that exact physical flat
material (including its four slots) through the shared WHD folded-mesh
engine, retaining per-triangle original UV for later side MARKING.

The fixture is supported by its already-defined installation: the flange
toward the cabinet side wall, the main ear toward cabinet center and the
free weld leg away from the Base Plate back skin. This is an ASSEMBLY TRIAL,
not a false assertion that the unfinished weld/contact/MFG-2 is certified.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isclose
from typing import Mapping


@dataclass(frozen=True)
class ReceivingFormedFixingPlateSkin:
    part_id: str
    base_part_id: str
    side: str
    layer_index: int
    source_bend_y_mm: float
    source_sheet_t_mm: float
    signed_source_fold_degrees: float
    source_to_cabinet_hole_x_mm: float
    fold_station_world_x_mm: float
    side_wall_inside_world_x_mm: float
    parent_base_back_skin_world_z_mm: float
    mapped_world_middle: tuple
    mapped_world_skins: tuple
    source_bend_verified: bool = True
    actual_signed_forming_constructed: bool = True
    weld_contact_verified: bool = False
    side_sheet_uv_marking_ready: bool = False
    manufacturing_ready: bool = False


def build_receiving_formed_fixing_plate_skins(
    snapshot: Mapping[str, object], part_id: str,
) -> ReceivingFormedFixingPlateSkin:
    """Fold authentic T2 material exactly once; one or two NFB tiers share it.

    The 21+T fold is SOURCE, not bend compensation. Physical 3D holes and
    left/right owner come from the same current Set/Bay source as Base Plate.
    This is deliberately opt-in so GUI Configure/repaint is not slowed.
    """
    from .assembly_geometry import (
        FoldedTriangleMap, MappedSkinTriangle,
        folded_mesh_with_flat_uv_from_polygon,
    )
    from .contracts import FoldProfileSegment
    from .receiving_base_fixing_plate_geometry import (
        LARGE_PATTERN, SOURCE_DXF_SHA256,
        build_fixing_plate_source_render_data,
    )
    from .receiving_tier_ear_assembly_xy import resolve_receiving_tier_ear_mating_xy
    from .receiving_tier_ear_z_targets import resolve_receiving_tier_ear_contact_targets

    if not isinstance(snapshot, Mapping) or snapshot.get("nfb_config_submitted") is not True:
        raise ValueError("EAR_FORM_REQUIRES_SUBMITTED_CURRENT_BAY")
    ear_id = str(part_id)
    xy_rows = resolve_receiving_tier_ear_mating_xy(snapshot)
    z_rows = resolve_receiving_tier_ear_contact_targets(snapshot)
    xy = next((x for x in xy_rows if x.ear_id == ear_id), None)
    contact = next((x for x in z_rows if x.ear_id == ear_id), None)
    if (xy is None or contact is None
            or xy.parent_base_id != contact.parent_base_id
            or xy.layer_index != contact.layer_index
            or xy.side != contact.side
            or not contact.base_skin_z_source_verified
            or contact.base_back_skin_world_z_mm is None):
        raise ValueError("EAR_FORM_PHYSICAL_OWNER_OR_Z_UNVERIFIED")
    source = build_fixing_plate_source_render_data(ear_id, snapshot=snapshot)
    pattern = LARGE_PATTERN
    guides = tuple(source.fold_guides)
    if (source.metadata.get("source_dxf_sha256") != SOURCE_DXF_SHA256
            or source.metadata.get("source_bend_verified") is not True
            or source.metadata.get("source_cutting_verified") is not True
            or not isclose(pattern.thickness, 2.0, abs_tol=1e-8)
            or len(guides) != 1
            or guides[0].axis != "y"
            or not isclose(guides[0].position, 23.0, abs_tol=1e-8)
            or not isclose(guides[0].span_start, 0.0, abs_tol=1e-8)
            or not isclose(guides[0].span_end, pattern.width, abs_tol=1e-8)):
        raise ValueError("EAR_FORM_NOT_CURRENT_20261018_SOURCE_BEND")
    if xy.side not in ("left", "right"):
        raise ValueError("EAR_FORM_SIDE_INVALID")
    inward = 1.0 if xy.side == "left" else -1.0
    inside_x = float(xy.side_inside_weld_x_mm)
    base_z = float(contact.base_back_skin_world_z_mm)
    # Flat u = long direction along cabinet world Y; y=23 source leg.
    # Source +90 produces a rear/down-going side-weld leg with its main
    # perforated face horizontal, identical left/right after mirroring X.
    xprof = (FoldProfileSegment(pattern.width, core="D"),)
    yprof = (
        FoldProfileSegment(pattern.source_fold_reference, angle=90.0,
                           core="weld_leg"),
        FoldProfileSegment(pattern.height-pattern.source_fold_reference, core="D"),
    )
    folded = folded_mesh_with_flat_uv_from_polygon(
        source.material, xprof, yprof, fold_guides=guides,
    )
    if not folded:
        raise ValueError("EAR_FORM_SOURCE_FOLD_MESH_EMPTY")
    # WHD canonical 21+T world datum: hole at source flat y=84 is 63
    # inside the *actual* wall inner skin. Do not borrow original T3/86.
    y_hole = pattern.slot_centers[0][1]
    y_core_center = (pattern.source_fold_reference + pattern.height)/2.0
    hole_local_y = y_hole - y_core_center
    cross_offset = (
        abs(float(xy.selected_slot_column_x_mm) - inside_x)
        - hole_local_y
    )
    if not isclose(cross_offset, 43.0, rel_tol=0, abs_tol=1e-6):
        raise ValueError("EAR_FORM_REVISED_T2_HOLE_TO_WALL_DRIFT")
    skin_t = float(pattern.thickness)
    # Source profile is centred about main/core. Its local Z=0 is a
    # sheet MID-surface; base back skin is the main face's TOP physical skin.
    def place(point):
        return (
            inside_x + inward*(float(point[1]) + cross_offset),
            float(xy.base_center_y_mm) + float(point[0]),
            base_z - skin_t/2.0 + float(point[2]),
        )

    mapped_world = []
    skins = []
    for item in folded:
        tri = tuple(place(pt) for pt in item.local)
        mapped_world.append(FoldedTriangleMap(flat=item.flat, local=tri))
        av = tuple(tri[1][i]-tri[0][i] for i in range(3))
        bv = tuple(tri[2][i]-tri[0][i] for i in range(3))
        normal = (
            av[1]*bv[2]-av[2]*bv[1],
            av[2]*bv[0]-av[0]*bv[2],
            av[0]*bv[1]-av[1]*bv[0],
        )
        magnitude = sum(v*v for v in normal)**0.5
        if magnitude < 1e-10:
            continue
        normal = tuple(v/magnitude for v in normal)
        for direction in (-1, 1):
            physical = tuple(
                tuple(v + direction*skin_t/2.0*normal[i]
                      for i,v in enumerate(pt))
                for pt in tri
            )
            skins.append(MappedSkinTriangle(
                flat=item.flat, world=physical, side=direction,
            ))
    if not skins:
        raise ValueError("EAR_FORM_PHYSICAL_SKINS_EMPTY")
    predicted_hole_x = inside_x + inward*(hole_local_y+cross_offset)
    if not isclose(predicted_hole_x, float(xy.selected_slot_column_x_mm),
                   rel_tol=0, abs_tol=1e-6):
        raise ValueError("EAR_FORM_HOLE_WORLD_X_MISMATCH")
    return ReceivingFormedFixingPlateSkin(
        part_id=ear_id, base_part_id=xy.parent_base_id,
        side=xy.side, layer_index=xy.layer_index,
        source_bend_y_mm=float(pattern.source_fold_reference),
        source_sheet_t_mm=skin_t,
        signed_source_fold_degrees=90.0,
        source_to_cabinet_hole_x_mm=predicted_hole_x,
        fold_station_world_x_mm=inside_x+inward*(
            -y_core_center+pattern.source_fold_reference+cross_offset),
        side_wall_inside_world_x_mm=inside_x,
        parent_base_back_skin_world_z_mm=base_z,
        mapped_world_middle=tuple(mapped_world),
        mapped_world_skins=tuple(skins),
    )
