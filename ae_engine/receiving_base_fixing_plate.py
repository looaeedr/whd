# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Receiving Base Plate > Base Fixing Plate (formerly 'ear') source preview.

The physical plates weld inside the cabinet sides and are separate physical
parts from Base Plate. The UPDATED fixing-plate source contains an actual BEND
line; exact signed forming and weld-Z proof remain separate from this preview.

Updated 2026-10-18 固定片.dxf SHA256:
dd123595e384b7ce6bf4c444b5af23a11e559de2a715c40ce5d89e2552167cbe
T2, 256x105, large hole row y84, y-BEND23; small 90x90, hole y69/BEND23.
Do not use the preview geometry as manufacturing CUTTING/BEND authority:
the source and material may be edited and must be re-read and recertified for
each actual production request.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from .receiving_base_plate_config import RECEIVING_FAMILIES
from .receiving_weld_ear_policy import (
    resolve_receiving_large_weld_ear_fit, receiving_source_fixing_pitch_x_mm,
)

BASE_FIXING_PLATE_PARENT_ID = "base_plate"
BASE_FIXING_PLATE_PREFIX = "base_plate:fixing_plate:"
BASE_FIXING_PLATE_DISPLAY_NAME = "底板固定片"
SOURCE_FLAT_SIZE_MM = (256.0, 105.0)
SOURCE_TOP_CORNER_RADIUS_MM = 0.0
SOURCE_SLOT_SIZE_MM = (25.0, 11.0)
SOURCE_SLOT_CENTERS_MM = ((23.0, 84.0), (58.0, 84.0),
                          (198.0, 84.0), (233.0, 84.0))
MANUFACTURING_STATUS = "EAR_SOURCE_BEND_VERIFIED_FORMING_WELD_Z_UNVERIFIED"


@dataclass(frozen=True)
class BaseFixingPlatePreview:
    part_id: str
    parent_part_id: str
    display_name: str
    side: str
    stock_thickness_mm: float
    nominal_source_outline_mm: tuple[float, float]
    nominal_source_slot_centers_mm: tuple[tuple[float, float], ...]
    source_slot_size_mm: tuple[float, float]
    source_top_corner_radius_mm: float
    nominal_fold_from_weld_edge_mm: float
    applicable_slot_pair_indexes: tuple[int, int] | None
    manufacturing_status: str = MANUFACTURING_STATUS

    @property
    def manufacturing_ready(self) -> bool:
        return False


def receiving_base_fixing_plate_previews(
    snapshot: Mapping[str, object] | None,
    *,
    available_parts=(),
) -> tuple[BaseFixingPlatePreview, ...]:
    """Read-only part preview; never changes physical scene or BOM.

    Use the existing T2/BEND23 fixed-plate source for each physical Bay. Its
    assembled X pitch follows the actual cabinet inside side skin; independent
    source contact and material checks still gate manufacture. A missing explicit base variant is previewable with
    the 210-mm outer slot pair, but remains *unconfigured* and never releasable.
    """
    data = dict(snapshot or {})
    model = str(data.get("model") or data.get("baseline_model") or "").strip()
    parts=set(str(value) for value in tuple(available_parts or ()))
    if (model not in RECEIVING_FAMILIES
            or (BASE_FIXING_PLATE_PARENT_ID not in parts
                and not any(p.startswith("base_plate:nfb_layer:") for p in parts))):
        return ()
    if isinstance(data.get("w"), bool) or isinstance(data.get("t"), bool):
        return ()
    try:
        w = float(data.get("w", 0))
        side_t = float(data.get("t", 0))
    except (TypeError, ValueError, OverflowError):
        return ()
    if not (isfinite(w) and isfinite(side_t)):
        return ()
    # Preserve historical pattern-only preview inputs (which are NOT a
    # fully configured physical BasePlate). A legacy flat preview may name
    # LEFT/CENTER/RIGHT solely to display the correct source slot pair.
    # ONLY when no explicit pattern is present, resolve the real physical
    # type from a submitted NFB CSV; never guess an unrecognized source.
    config = data.get("receiving_base_plate")
    pattern = (str(config.get("pattern") or "")
               if isinstance(config, Mapping) else "")
    if not pattern:
        from .receiving_base_plate_config import receiving_base_plate_values
        try:
            actual_source = receiving_base_plate_values(data)
        except (KeyError, TypeError, ValueError):
            # A preview must not imply a certified manufacturing plate.
            return ()
        pattern = (str(actual_source["receiving_bend_pattern"])
                   if actual_source is not None else "")
    from .sheetmetal_part_adapters import (
        RECEIVING_BASE_PATTERN_CENTER, RECEIVING_BASE_PATTERN_LEFT,
        RECEIVING_BASE_PATTERN_RIGHT,
    )
    # Source plate offers both slot pairs, but an unconfigured bottom plate
    # cannot silently claim to mate the 210-mm pair.
    chosen_pair = (
        (1, 2) if pattern == RECEIVING_BASE_PATTERN_CENTER else
        (0, 3) if pattern in (RECEIVING_BASE_PATTERN_LEFT, RECEIVING_BASE_PATTERN_RIGHT)
        else None
    )
    pitch_y = 140.0 if chosen_pair == (1, 2) else 210.0
    try:
        fit = resolve_receiving_large_weld_ear_fit(
            box_outer_width_mm=w,
            box_side_thickness_mm=side_t,
            fixing_hole_pitch_x_mm=receiving_source_fixing_pitch_x_mm(
                box_outer_width_mm=w, box_side_thickness_mm=side_t,
            ),
            fixing_hole_pitch_y_mm=pitch_y,
        )
    except (TypeError, ValueError, OverflowError):
        return ()
    # One NFB layer owns ONE source Base Plate and exactly two welded-ear
    # children (left/right). Two NFB layers inside the UPPER Outer Door must
    # NEVER silently share the same two ear IDs. The OUTER lower compartment
    # has no such NFB Base Plate. These are source-flat previews, not fake
    # certified BEND/weld/3D manufacturing parts.
    owner_ids=(BASE_FIXING_PLATE_PARENT_ID,)
    config_nfb=data.get("nfb_config")
    if (data.get("nfb_config_submitted") is True
            and isinstance(config_nfb,Mapping)
            and config_nfb.get("layer_count")==2):
        from .receiving_nfb_base_assembly_xy import receiving_nfb_layer_centers
        upper=tuple(
            row for row in tuple(data.get("inner_doors") or ())
            if isinstance(row,Mapping)
            and str(row.get("cell_key") or "").split(":")[-1]=="0"
            and str(row.get("stable_id") or "").strip()
        )
        if len(upper)!=1:
            return ()
        try:
            tiers=receiving_nfb_layer_centers(
                data,str(upper[0]["stable_id"]),
            )
        except ValueError as exc:
            if str(exc) in {
                "RECEIVING_NFB_LAYER_SET_IDENTITY_DRIFT",
                "RECEIVING_NFB_LAYER_BAY_IDENTITY_DRIFT",
                "RECEIVING_NFB_LAYER_CONFIG_IDENTITY_DRIFT",
            }:
                return ()  # UI switching: do not invent stale tier children
            raise
        if len(tiers)!=2:
            return ()
        owner_ids=tuple(tier.layer_part_id for tier in tiers)

    return tuple(
        BaseFixingPlatePreview(
            part_id=(
                BASE_FIXING_PLATE_PREFIX+side
                if owner_id==BASE_FIXING_PLATE_PARENT_ID
                else BASE_FIXING_PLATE_PREFIX +
                     f"nfb_layer:{owner_id.rsplit(':',1)[-1]}:{side}"
            ),
            parent_part_id=owner_id,
            display_name=(
                BASE_FIXING_PLATE_DISPLAY_NAME +
                ("（左）" if side=="left" else "（右）")
                if owner_id==BASE_FIXING_PLATE_PARENT_ID else
                f"{BASE_FIXING_PLATE_DISPLAY_NAME}（第{int(owner_id.rsplit(':',1)[-1])+1}層" +
                ("左）" if side=="left" else "右）")
            ),
            side=side,
            stock_thickness_mm=fit.ear_thickness_mm,
            nominal_source_outline_mm=SOURCE_FLAT_SIZE_MM,
            nominal_source_slot_centers_mm=SOURCE_SLOT_CENTERS_MM,
            source_slot_size_mm=SOURCE_SLOT_SIZE_MM,
            source_top_corner_radius_mm=SOURCE_TOP_CORNER_RADIUS_MM,
            nominal_fold_from_weld_edge_mm=fit.nominal_fold_from_weld_edge_mm,
            applicable_slot_pair_indexes=chosen_pair,
        )
        for owner_id in owner_ids
        for side in ("left","right")
    )
