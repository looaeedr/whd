# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Independent, original-DXF-derived Receiving bottom fixing-plate blanks.

受電耳朵.dxf contains TWO closed source profiles: long 256x105 / four slots
and small 90x90 / two slots (T3, top R5, slot R5.5). Coordinates below are
local 0,0 normalization of the user's actual LINE/ARC entities, not a new
cabinet placement. Geometry is shared by 2D / 3D flat-material preview and
separate source-flat DXF. The source does not establish the finished weld Z,
large-ear fold direction/line or the number of *small* plates to install in a cabinet.

The long plate applies to W800/T2 at the two verified side positions; the
short profile is catalogued, never silently instantiated in that W800 cabinet.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians, sin
from pathlib import Path

from .receiving_base_fixing_plate import BASE_FIXING_PLATE_PREFIX

SOURCE_DXF_SHA256 = "2d8b96ff88882c033a08da223f112e2d7573f787fb13fa056cf71626bfeec8a8"
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
    LARGE_SOURCE, 256.0, 105.0, 3.0, 5.0, 25.0, 11.0,
    ((23.0, 86.0), (58.0, 86.0), (198.0, 86.0), (233.0, 86.0)),
)
SMALL_PATTERN = FixingPlateSourcePattern(
    SMALL_SOURCE, 90.0, 90.0, 3.0, 5.0, 30.0, 11.0,
    ((25.0, 68.0), (65.0, 68.0)),
    source_fold_reference=22.0,
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


def _outline(pattern):
    w, h, r = pattern.width, pattern.height, pattern.corner_radius
    return (
        ((0.0, 0.0), (w, 0.0), (w, h-r))
        + _arc(w-r, h-r, r, 0, 90)
        + ((r, h),)
        + _arc(r, h-r, r, 90, 180)
    )


def _slot(cx, cy, length, diameter):
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


def build_fixing_plate_source_render_data(
    part_id: str, *, source_kind: str = LARGE_SOURCE, snapshot=None,
):
    """Real standalone PartRenderData from source CUTTING, never fake BEND.

    Output remains a source-flat manufacturing part until bend/weld proofs pass.
    The same geometry is used for material, 2D and 3D flat-thickness preview.
    """
    from .manufacturing_render_data import (
        PartRenderData, UnfoldedBlankTopology, MaterialSegment,
        material_polygon_from_final_scene,
    )
    from .sheetmetal_drawing import DrawingScene

    key = str(part_id or "")
    if source_kind == LARGE_SOURCE:
        if key not in (BASE_FIXING_PLATE_PREFIX + "left",
                       BASE_FIXING_PLATE_PREFIX + "right"):
            raise ValueError("unknown physical large fixing-plate identity")
    elif source_kind == SMALL_SOURCE:
        if key != BASE_FIXING_PLATE_PREFIX + "small_source":
            raise ValueError("small original drawing is a source part, not an installed W800 ear")
    else:
        raise ValueError("UNKNOWN_BASE_FIXING_PLATE_SOURCE_PROFILE")
    pattern = source_pattern(source_kind)
    scene = DrawingScene()
    scene.add_polyline(_outline(pattern), layer="CUTTING", closed=True)
    for center in pattern.slot_centers:
        scene.add_polyline(_slot(*center, pattern.slot_length, pattern.slot_width),
                           layer="CUTTING", closed=True)
    # Color-150 original source line is an observed reference, NOT a
    # machine-certified brake line. Show it as marking only.
    if pattern.source_fold_reference is not None:
        scene.add_line(
            (0.0, pattern.source_fold_reference),
            (pattern.width, pattern.source_fold_reference),
            layer="MARKING", color=150,
        )
    material = material_polygon_from_final_scene(scene)
    if material.is_empty or not material.is_valid:
        raise ValueError("BASE_FIXING_PLATE_SOURCE_INVALID")
    topology = UnfoldedBlankTopology(
        piece_id=key,
        x_segments=(MaterialSegment("X", "source_flat_width", pattern.width, "ORIGINAL_EAR_DXF"),),
        y_segments=(MaterialSegment("Y", "source_flat_height", pattern.height, "ORIGINAL_EAR_DXF"),),
        source="ORIGINAL_EAR_DXF", revision=1,
    )
    mating = None
    if snapshot is not None and source_kind == LARGE_SOURCE:
        from .receiving_base_fixing_plate_mating import (
            resolve_base_fixing_plate_xy_mating,
        )
        from .receiving_base_fixing_plate import receiving_base_fixing_plate_previews
        data = dict(snapshot or {})
        candidates = receiving_base_fixing_plate_previews(
            data, available_parts=("base_plate",),
        )
        if key not in {row.part_id for row in candidates}:
            raise ValueError("BASE_FIXING_PLATE_CABINET_MISMATCH")
        if any(row.part_id == key and row.applicable_slot_pair_indexes is not None for row in candidates):
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
            "formed_geometry_verified": False,
            "weld_z_verified": False,
            "factory_bend_compensation_required": False,
            "xy_mating_proven": mating is not None,
            "nominal_weld_inside_skin_x_mm": (
                mating.inside_skin_world_x_mm if mating is not None else None
            ),
            "nominal_base_fixing_hole_world_x_mm": (
                mating.selected_fixing_world_x_mm if mating is not None else None
            ),
            "nominal_base_fixing_hole_world_y_mm": (
                mating.selected_fixing_world_y_mm if mating is not None else ()
            ),
            "nominal_slot_pair_indexes": (
                mating.selected_slot_indexes if mating is not None else None
            ),
            "manufacturing_ready": False,
        }
    return PartRenderData(
        scene=scene, material=material, unfolded_topology=topology,
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
