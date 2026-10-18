# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Original-user 固定片.dxf (2026-10-18) source-backed Receiving fixing blanks.

The REVISED 固定片.dxf contains TWO closed source profiles: long 256x105 / four slots
and small 90x90 / two slots (source T2, top R5, slot R5.5). Coordinates below are
local 0,0 normalization of the user's actual LINE/ARC entities, not a new
cabinet placement. Geometry is shared by 2D / 3D flat-material preview and
separate source-flat DXF. The source explicitly contains a 23-mm-from-bottom BEND LINE on BOTH blanks
for T2, and labels T3 fold at 24 mm (21 + physical EAR T). A LINE does NOT
independently specify its signed 90-degree direction or the assembled weld Z.

The long plate applies to W800/T2 at the two verified side positions; the
short profile is catalogued, never silently instantiated in that W800 cabinet.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from math import cos, radians, sin
from pathlib import Path

from .receiving_base_fixing_plate import BASE_FIXING_PLATE_PREFIX

SOURCE_DXF_SHA256 = "dd123595e384b7ce6bf4c444b5af23a11e559de2a715c40ce5d89e2552167cbe"
LARGE_SOURCE = "large"
SMALL_SOURCE = "small"


@dataclass(frozen=True)
class FixingPlateSourcePattern:
    key: str
    width: float
    height: float
    thickness: float
    corner_radius: float
    slot_length: float
    slot_width: float
    slot_centers: tuple[tuple[float, float], ...]
    source_fold_reference: float | None = None


LARGE_PATTERN = FixingPlateSourcePattern(
    LARGE_SOURCE, 256.0, 105.0, 2.0, 5.0, 25.0, 11.0,
    ((23.0, 84.0), (58.0, 84.0), (198.0, 84.0), (233.0, 84.0)),
    source_fold_reference=23.0,
)
SMALL_PATTERN = FixingPlateSourcePattern(
    SMALL_SOURCE, 90.0, 90.0, 2.0, 5.0, 30.0, 11.0,
    ((25.0, 69.0), (65.0, 69.0)),
    source_fold_reference=23.0,
)
# The small plate's straight portion is 19 mm, with 5.5 mm radii on both
# sides => 30 mm total slot width. Long plate is 14+11=25 mm.


def source_pattern(kind: str) -> FixingPlateSourcePattern:
    table = {LARGE_SOURCE: LARGE_PATTERN, SMALL_SOURCE: SMALL_PATTERN}
    try:
        return table[str(kind)]
    except KeyError as exc:
        raise ValueError("UNKNOWN_BASE_FIXING_PLATE_SOURCE_PROFILE") from exc


def _arc(cx, cy, radius, start, end, segments=96):
    return tuple((
        cx + radius * cos(radians(start + (end - start) * i / segments)),
        cy + radius * sin(radians(start + (end - start) * i / segments)),
    ) for i in range(segments + 1))


@lru_cache(maxsize=2)
def _outline(pattern):
    """Source-only immutable arc vertices; never cache a DrawingScene or mating.

    Pattern is a frozen dataclass, so a changed physical source geometry
    cannot accidentally hit an obsolete contour. Original DXF source SHA,
    arc segmentation and coordinate precision are unchanged.
    """
    w, h, r = pattern.width, pattern.height, pattern.corner_radius
    return (
        ((0.0, 0.0), (w, 0.0), (w, h-r))
        + _arc(w-r, h-r, r, 0, 90)
        + ((r, h),)
        + _arc(r, h-r, r, 90, 180)
    )


@lru_cache(maxsize=8)
def _slot(cx, cy, length, diameter):
    """Immutable original source-slot vertices, keyed by exact XY/size."""
    r = diameter / 2.0
    half_straight = (length - diameter) / 2.0
    if half_straight <= 0:
        raise ValueError("source slot must contain straight edges")
    return (
        ((cx-half_straight, cy-r), (cx+half_straight, cy-r))
        + _arc(cx+half_straight, cy, r, -90, 90)
        + ((cx-half_straight, cy+r),)
        + _arc(cx-half_straight, cy, r, 90, 270)
    )


def _source_flat_cutting_scene(pattern):
    """New independent DrawingScene with exactly the original source contours."""
    from .sheetmetal_drawing import DrawingScene
    scene = DrawingScene()
    scene.add_polyline(_outline(pattern), layer="CUTTING", closed=True)
    for center in pattern.slot_centers:
        scene.add_polyline(_slot(*center, pattern.slot_length, pattern.slot_width),
                           layer="CUTTING", closed=True)
    if pattern.source_fold_reference is not None:
        # This BEND is a real LINE in the user-supplied UPDATED
        # 固定片.dxf (handles 9C small / 9D large), not an inferred fold.
        scene.add_line(
            (0.0, pattern.source_fold_reference),
            (pattern.width, pattern.source_fold_reference),
            layer="BEND", color=5)
    return scene


@lru_cache(maxsize=2)
def _cached_source_flat_material_wkb(source_kind):
    """Store only source-SHA-pinned immutable flat CUTTING material bytes.

    The resolved physical PartRenderData, individual scenes, side identity,
    XY mating, world placement, and unfinished bend/weld proof remain NEW for
    each request. WKB roundtrip returns a distinct shapely geometry per call.
    This cache does not parse customer DXF or certify manufacture.
    """
    from .manufacturing_render_data import material_polygon_from_final_scene
    source = _source_flat_cutting_scene(source_pattern(source_kind))
    material = material_polygon_from_final_scene(source)
    if material.is_empty or not material.is_valid:
        raise ValueError("BASE_FIXING_PLATE_SOURCE_INVALID")
    return material.wkb


def build_fixing_plate_source_render_data(
    part_id: str, *, source_kind: str = LARGE_SOURCE, snapshot=None,
):
    """Real standalone PartRenderData from source CUTTING plus existing BEND.

    T2 source BEND exists; signed forming direction/weld remain separate proofs.
    The same geometry is used for material, 2D and 3D flat-thickness preview.
    """
    from .manufacturing_render_data import (
        PartRenderData, UnfoldedBlankTopology, MaterialSegment,
        fold_guides_from_final_scene,
    )
    from shapely import wkb as shapely_wkb

    key = str(part_id or "")
    legacy_ids = (BASE_FIXING_PLATE_PREFIX + "left",
                  BASE_FIXING_PLATE_PREFIX + "right")
    is_tier_ear = (
        key.startswith(BASE_FIXING_PLATE_PREFIX + "nfb_layer:")
        and key.rsplit(":", 1)[-1] in ("left", "right")
    )
    if source_kind == LARGE_SOURCE:
        if key not in legacy_ids and not is_tier_ear:
            raise ValueError("unknown physical large fixing-plate identity")
        if is_tier_ear and snapshot is None:
            raise ValueError("TIER_FIXING_PLATE_NEEDS_CURRENT_SOURCE_SNAPSHOT")
    elif source_kind == SMALL_SOURCE:
        if key != BASE_FIXING_PLATE_PREFIX + "small_source":
            raise ValueError("small original drawing is a source part, not an installed W800 ear")
    else:
        raise ValueError("UNKNOWN_BASE_FIXING_PLATE_SOURCE_PROFILE")
    pattern = source_pattern(source_kind)
    scene = _source_flat_cutting_scene(pattern)
    # Recreate a distinct, mutable-independent geometry wrapper from a
    # certified constant source contour; placement/proof stays uncached.
    material = shapely_wkb.loads(_cached_source_flat_material_wkb(source_kind))
    if material.is_empty or not material.is_valid:
        raise ValueError("BASE_FIXING_PLATE_SOURCE_INVALID")
    topology = UnfoldedBlankTopology(
        piece_id=key,
        x_segments=(MaterialSegment("X", "source_flat_width", pattern.width, "ORIGINAL_EAR_DXF"),),
        y_segments=(MaterialSegment("Y", "source_flat_height", pattern.height, "ORIGINAL_EAR_DXF"),),
        source="ORIGINAL_EAR_DXF", revision=1,
    )
    mating = None
    tier_xy = None
    tier_contact = None
    preview = None
    if snapshot is not None and source_kind == LARGE_SOURCE:
        from .receiving_base_fixing_plate import receiving_base_fixing_plate_previews
        data = dict(snapshot or {})
        candidates = receiving_base_fixing_plate_previews(
            data, available_parts=("base_plate",),
        )
        preview = next((row for row in candidates if row.part_id == key), None)
        if preview is None:
            raise ValueError("BASE_FIXING_PLATE_CABINET_MISMATCH")
        if preview.applicable_slot_pair_indexes is not None:
            # A submitted SINGLE NFB tier is as physical as TWO tiers.
            # Legacy root EAR lookup used base-local +/-70/105 world Y,
            # ignoring the actual NFB opening-centred Base Plate offset.
            # Only UNCOMMITTED legacy source-flat previews use old-local XY.
            if is_tier_ear or data.get("nfb_config_submitted") is True:
                from .receiving_tier_ear_assembly_xy import (
                    resolve_receiving_tier_ear_mating_xy,
                )
                from .receiving_tier_ear_z_targets import (
                    resolve_receiving_tier_ear_contact_targets,
                )
                tier_xy = next((row for row in
                                resolve_receiving_tier_ear_mating_xy(data)
                                if row.ear_id == key), None)
                tier_contact = next((row for row in
                                     resolve_receiving_tier_ear_contact_targets(data)
                                     if row.ear_id == key), None)
                if (tier_xy is None or tier_contact is None
                        or tier_xy.parent_base_id != preview.parent_part_id
                        or tier_contact.parent_base_id != preview.parent_part_id
                        or tier_contact.layer_index != tier_xy.layer_index):
                    raise ValueError("TIER_FIXING_PLATE_SOURCE_OWNER_DRIFT")
            else:
                from .receiving_base_fixing_plate_mating import (
                    resolve_base_fixing_plate_xy_mating,
                )
                mating = resolve_base_fixing_plate_xy_mating(
                    data, key.rsplit(":", 1)[-1],
                )
    metadata = {
            "stable_id": key,
            "physical_part_role": "BASE_FIXING_PLATE",
            "source_profile": pattern.key,
            "source_dxf_sha256": SOURCE_DXF_SHA256,
            "thickness": pattern.thickness,
            "source_flat_dimensions": (pattern.width, pattern.height),
            # One materialized physical instance per stable ID. The long
            # profile has two separate installed instances (left and right);
            # they must not each be counted twice in a BOM.
            "quantity_of_this_part": 1,
            "source_profile_total_installed_per_w800": (
                2 if source_kind == LARGE_SOURCE else None
            ),
            "source_cutting_verified": True,
            "source_bend_verified": True,
            "source_bend_axis": "y",
            "source_bend_line_mm": pattern.source_fold_reference,
            "source_bend_rule": "21+EAR_T",
            "formed_direction_verified": False,
            "formed_geometry_verified": False,
            "weld_z_verified": False,
            "factory_bend_compensation_required": False,
            "xy_mating_proven": mating is not None or tier_xy is not None,
            "parent_base_id": (
                preview.parent_part_id if preview is not None else None
            ),
            "nfb_layer_index": (
                tier_xy.layer_index if tier_xy is not None else None
            ),
            "nominal_weld_inside_skin_x_mm": (
                tier_xy.side_inside_weld_x_mm if tier_xy is not None else
                mating.inside_skin_world_x_mm if mating is not None else None
            ),
            "nominal_base_fixing_hole_world_x_mm": (
                tier_xy.selected_slot_column_x_mm if tier_xy is not None else
                mating.selected_fixing_world_x_mm if mating is not None else None
            ),
            "nominal_base_fixing_hole_world_y_mm": (
                tier_xy.selected_slot_pair_world_y_mm if tier_xy is not None else
                mating.selected_fixing_world_y_mm if mating is not None else ()
            ),
            "nominal_slot_pair_indexes": (
                preview.applicable_slot_pair_indexes if preview is not None else
                mating.selected_slot_indexes if mating is not None else None
            ),
            "base_back_skin_world_z_mm": (
                tier_contact.base_back_skin_world_z_mm
                if tier_contact is not None else None
            ),
            "ear_contact_target_world_z_mm": (
                tier_contact.target_ear_contact_world_z_mm
                if tier_contact is not None else None
            ),
            "base_skin_z_source_verified": (
                tier_contact.base_skin_z_source_verified
                if tier_contact is not None else False
            ),
            "manufacturing_ready": False,
        }
    return PartRenderData(
        scene=scene, material=material, unfolded_topology=topology,
        fold_guides=fold_guides_from_final_scene(scene),
        metadata=metadata,
    )


def save_independent_source_flat_dxf(part_id, output_path, *, overwrite=False):
    """Produce only the unbent original-source CUTTING, with round-trip check.

    This deliberately bypasses *neither* machine bend certification nor the
    full-assembly EAR/PAD guard: it creates a separate source-flat DXF, not a
    claimed formed/welded manufacturing part or whole-cabinet release.
    """
    from .manufacturing_api import (
        save_part_render_data_dxf, verify_saved_part_render_data_dxf,
    )
    kind = SMALL_SOURCE if str(part_id).endswith("small_source") else LARGE_SOURCE
    data = build_fixing_plate_source_render_data(part_id, source_kind=kind)
    destination = Path(output_path)
    if destination.exists() and not overwrite:
        raise FileExistsError(str(destination))
    path = save_part_render_data_dxf(data, destination, overwrite=overwrite)
    verified = verify_saved_part_render_data_dxf(data, path)
    if not verified.ok:
        Path(path).unlink(missing_ok=True)
        raise ValueError("BASE_FIXING_PLATE_SOURCE_DXF_ROUNDTRIP_FAILED")
    return path
