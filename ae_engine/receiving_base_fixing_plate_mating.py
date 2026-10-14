# -*- coding: utf-8 -*-
# WHD 製造／3D 共用尺寸不變式（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 包外是折後外側面的成形尺寸；料段 len = 其包外段尺寸 −（實際相鄰折彎數 0/1/2 × T），已轉成料長的資料不得重扣 T。
# 展開 CUTTING = 料段累加；BEND 線位 = 同一料鏈的前綴和，不可直接拿包外尺寸充當展開折彎座標。
# 3D 須依相同 Fold Profile／料鏈／BEND 與角度成形；角度正負只決定方向，禁止從 3D bbox 反推料長。
# 這是板厚尺寸語意，非折彎展開補償；WRAP／OVERLAY 是裝配關係，不等於包外。

"""#1503 source-verified 2D XY mating audit for Receiving Base Fixing Plates.

The physical basis is 受電耳朵.dxf + 受電箱底板.dxf.  The factory does NOT use
bend compensation. For W800/T2 the *nominal* fold reference is 23 mm from the
long weld edge because original source slot center is 86 mm away and the
assembled hole is 63 mm from the inside side-panel skin.

This independent 2D proof derives ALL four original slot projections. It
intentionally does not publish a press-brake BEND line, formed 3D geometry, or
a welding Z, because none is established by the original large plate DXF.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping
from math import isclose, isfinite

from .receiving_base_fixing_plate import receiving_base_fixing_plate_previews
from .receiving_base_fixing_plate_geometry import LARGE_PATTERN
from .receiving_weld_ear_policy import resolve_receiving_large_weld_ear_fit


@dataclass(frozen=True)
class FixingPlateXYMating:
    part_id: str
    side: str
    source_longitudinal_center_mm: float
    source_weld_edge_to_slot_center_mm: float
    nominal_fold_from_weld_edge_mm: float
    inside_skin_world_x_mm: float
    selected_fixing_world_x_mm: float
    slot_world_y_mm: tuple[float, ...]
    selected_slot_indexes: tuple[int, int]
    selected_fixing_world_y_mm: tuple[float, float]
    selected_fixing_pitch_y_mm: float
    counterpart_base_fixing_pitch_x_mm: float
    counterpart_base_fixing_pitch_y_mm: float
    factory_bend_compensation_mm: float
    bend_line_confirmed: bool = False
    formed_direction_confirmed: bool = False
    weld_z_confirmed: bool = False

    @property
    def xy_mating_proven(self) -> bool:
        return True

    @property
    def manufacturing_approved(self) -> bool:
        return False


def resolve_base_fixing_plate_xy_mating(
    snapshot: Mapping[str, object], side: str,
) -> FixingPlateXYMating:
    """Match original ear slots to known cabinet and Base Plate hole centers.

    Y is cabinet vertical (long source plate dimension), X across cabinet.
    Source origin for each original long plate is its bottom-left flat corner.
    Datum Y=0 at the original 256-mm longitudinal midpoint. This is a
    centerline projection, not a statement of world Z or plate bend readiness.

    Raises on missing actual Base Plate variant; never presumes 210 over 140.
    """
    data = dict(snapshot or {})
    name = str(side)
    if name not in ("left", "right"):
        raise ValueError("FIXING_PLATE_SIDE_INVALID")
    preview = next((
        p for p in receiving_base_fixing_plate_previews(
            data, available_parts=("base_plate",)
        ) if p.side == name
    ), None)
    if preview is None:
        raise ValueError("FIXING_PLATE_XY_MATING_REQUIRES_W800_T2_RECEIVING")
    pair = preview.applicable_slot_pair_indexes
    if pair is None:
        raise ValueError("FIXING_PLATE_XY_MATING_REQUIRES_CONFIGURED_BASE_PATTERN")
    x_pitch = 670.0
    selected_y_pitch = 210.0 if pair == (0, 3) else 140.0
    fit = resolve_receiving_large_weld_ear_fit(
        box_outer_width_mm=float(data["w"]),
        box_side_thickness_mm=float(data["t"]),
        fixing_hole_pitch_x_mm=x_pitch,
        fixing_hole_pitch_y_mm=selected_y_pitch,
    )
    if pair != fit.slot_pair_indexes:
        raise ValueError("FIXING_PLATE_SLOT_PAIR_MISMATCH")
    if not all(isfinite(float(x)) for x in (data["w"],data["t"])):
        raise ValueError("FIXING_PLATE_GEOMETRY_NONFINITE")
    # Original 256-mm-long source blank has four vertically aligned slots;
    # the center X datum is exactly the common midpoint of either pair.
    centers_x = tuple(float(cx) for cx, _ in LARGE_PATTERN.slot_centers)
    centers_y = tuple(float(cy) for _, cy in LARGE_PATTERN.slot_centers)
    origin = LARGE_PATTERN.width / 2.0
    slot_y = tuple(x - origin for x in centers_x)
    if not isclose(sum(slot_y[i] for i in pair), 0.0, abs_tol=1e-7):
        raise ValueError("FIXING_PLATE_SOURCE_LONGITUDINAL_CENTER_INVALID")
    if not all(isclose(y, centers_y[0], abs_tol=1e-7) for y in centers_y):
        raise ValueError("FIXING_PLATE_SOURCE_HOLE_COLUMN_INVALID")
    if not isclose(centers_y[0],fit.ear_weld_edge_to_hole_center_mm,abs_tol=1e-7):
        raise ValueError("FIXING_PLATE_SOURCE_EDGE_DATUM_INVALID")
    # Left (-X) / right (+X) inside skin: +-398 for W800/T2.
    sign = -1.0 if name == "left" else 1.0
    inner_x = sign * (float(data["w"]) / 2.0 - float(data["t"]))
    projected_x = inner_x - sign * (
        centers_y[0] - fit.nominal_fold_from_weld_edge_mm
    )
    expected_x = sign * x_pitch / 2.0
    if not isclose(projected_x, expected_x,abs_tol=1e-7):
        raise ValueError("FIXING_PLATE_ASSEMBLED_X_MATE_FAILED")
    selected_y = tuple(slot_y[i] for i in pair)
    if not isclose(selected_y[1] - selected_y[0],selected_y_pitch,abs_tol=1e-7):
        raise ValueError("FIXING_PLATE_ASSEMBLED_Y_MATE_FAILED")
    return FixingPlateXYMating(
        part_id=preview.part_id,
        side=name,
        source_longitudinal_center_mm=origin,
        source_weld_edge_to_slot_center_mm=fit.ear_weld_edge_to_hole_center_mm,
        nominal_fold_from_weld_edge_mm=fit.nominal_fold_from_weld_edge_mm,
        inside_skin_world_x_mm=inner_x,
        selected_fixing_world_x_mm=projected_x,
        slot_world_y_mm=slot_y,
        selected_slot_indexes=pair,
        selected_fixing_world_y_mm=(selected_y[0], selected_y[1]),
        selected_fixing_pitch_y_mm=selected_y_pitch,
        counterpart_base_fixing_pitch_x_mm=x_pitch,
        counterpart_base_fixing_pitch_y_mm=selected_y_pitch,
        factory_bend_compensation_mm=0.0,
    )


def resolve_base_fixing_pair_xy_mating(snapshot: Mapping[str, object]):
    """Verify opposing ear slot centers against a single bottom-plate pattern."""
    left = resolve_base_fixing_plate_xy_mating(snapshot, "left")
    right = resolve_base_fixing_plate_xy_mating(snapshot, "right")
    if not isclose(
        right.selected_fixing_world_x_mm - left.selected_fixing_world_x_mm,
        left.counterpart_base_fixing_pitch_x_mm, abs_tol=1e-7,
    ):
        raise ValueError("FIXING_PLATE_OPPOSING_X_PITCH_FAILED")
    if left.selected_fixing_world_y_mm != right.selected_fixing_world_y_mm:
        raise ValueError("FIXING_PLATE_OPPOSING_Y_PITCH_FAILED")
    return left, right
