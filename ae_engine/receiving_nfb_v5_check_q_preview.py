# -*- coding: utf-8 -*-
"""#1502: CSV V5 tier-base geometry -> canonical CHECK/Q *preview*.

This consumes real physical FinalScene material from the existing per-tier
base-plate projection. It groups exact manufacturing geometry, NOT part
names, NFB source filenames or just bounding boxes. No MFG-2 export grant is
created: EAR BEND/contact, side MARKING and release remain separate gates.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
from typing import Sequence

from .manufacturing_equivalence import (
    ManufacturingParameters, QuantityManufacturingGroup,
    group_quantity_physical_demands,
)
from .manufacturing_quantity import PhysicalPartDemand
from .manufacturing_render_data import material_polygon_from_final_scene
from .receiving_nfb_numeric_catalog import brand_csv_path
from .receiving_nfb_v5_actual_base_screws import (
    STATUS as V5_BASE_TRIAL_STATUS, NfbV5ActualBaseScrewTrial,
)
from .sheetmetal_drawing import CirclePrimitive, PolylinePrimitive


@dataclass(frozen=True)
class CsvV5BaseCheckDemand:
    """One actual tier sheet times the approved quantity of that version."""
    version_id: str
    part: NfbV5ActualBaseScrewTrial
    quantity: int
    parameters: ManufacturingParameters


@dataclass(frozen=True)
class CsvV5BaseCheckPreview:
    groups: tuple[QuantityManufacturingGroup, ...]
    physical_part_ids: tuple[str, ...]
    status: str = "NFB_V5_CSV_BASE_CHECK_Q_PREVIEW_ONLY"
    manufacturing_ready: bool = False


def check_csv_v5_base_part_only_groups(
    demands: Sequence[CsvV5BaseCheckDemand],
) -> CsvV5BaseCheckPreview:
    """Compute Q with the canonical exact-FinalScene grouping implementation.

    Reject a stale CSV, a wrong CUTTING owner, unfinished or duplicate physical
    sheets. This is validation evidence only; never return an export-ready
    PartRenderData or unfreeze any global MFG-2 gate.
    """
    rows = tuple(demands)
    if not rows:
        raise ValueError("CSV V5 CHECK Q 沒有任何實體底板")
    physical_demands = []
    parameters_by_source = {}
    seen = set()
    for row in rows:
        if not isinstance(row, CsvV5BaseCheckDemand):
            raise TypeError("CHECK Q 每張底板必須有完整版本與實體資料")
        part = row.part
        if not isinstance(part, NfbV5ActualBaseScrewTrial):
            raise TypeError("CHECK Q 僅接受既有實體底板的 CSV V5 螺絲試作")
        if (not isinstance(row.version_id, str) or not row.version_id.strip()
                or type(row.quantity) is not int or row.quantity < 1
                or not isinstance(row.parameters, ManufacturingParameters)):
            raise ValueError("CHECK Q 版本、件數或材料製程參數不合法")
        key = (row.version_id, part.part_id)
        if key in seen:
            raise ValueError("CHECK Q 同版本實體底板重複")
        seen.add(key)
        render = part.render_data
        info = dict(render.metadata or {})
        if (part.status != V5_BASE_TRIAL_STATUS or part.manufacturing_ready
                or not part.hole_ids or len(set(part.hole_ids)) != len(part.hole_ids)
                or len(part.patterns) != len(part.hole_ids)
                or info.get("stable_id") != part.part_id
                or info.get("nfb_v5_trial_status") != V5_BASE_TRIAL_STATUS
                or tuple(info.get("nfb_v5_hole_ids") or ()) != part.hole_ids
                or info.get("nfb_v5_target_role") != "base-plate"
                or info.get("nfb_trial_export_approved") is not False
                or info.get("nfb_base_mfg2_release_approved") is not False):
            raise ValueError("CSV V5 底板缺少同源實體與未放行狀態")
        csv_sources = tuple(info.get("nfb_v5_source_csv_sha256") or ())
        active_brands = {pattern.brand for pattern in part.patterns}
        csv_brands = {brand for brand, _ in csv_sources}
        # An actual physical tier may use one brand even when the full
        # verified inner-door proof contains other tiers with other brands.
        # Retain and validate *all* full-proof source hashes.
        if (not active_brands.issubset(csv_brands)
                or len(csv_sources) != len(csv_brands)):
            raise ValueError("CSV V5 底板缺少來源 CSV SHA")
        try:
            fresh = tuple(sorted(
                (brand, sha256(brand_csv_path(brand).read_bytes()).hexdigest())
                for brand in csv_brands
            ))
        except OSError as exc:
            raise ValueError("CSV V5 檢查時來源資料不可讀") from exc
        if csv_sources != fresh:
            raise ValueError("CSV V5 檢查時來源 CSV 已變更")
        screws = [primitive for primitive in render.scene.primitives
                  if isinstance(primitive, CirclePrimitive)
                  and primitive.layer == "CUTTING"
                  and primitive.source_type == "NFB_V5_NUMERIC_BASE_TRIAL"]
        native = [primitive for primitive in render.scene.primitives
                  if isinstance(primitive, PolylinePrimitive)
                  and primitive.closed and primitive.layer == "CUTTING"]
        expected_ids = {
            f"{hole_id}:screw:{i}"
            for hole_id in part.hole_ids for i in range(1, 5)
        }
        if (len(screws) != 4 * len(part.hole_ids)
                or {item.source_id for item in screws} != expected_ids
                or len(native) != 5
                or render.material is None or render.material.is_empty
                or not render.material.is_valid):
            raise ValueError("CSV V5 底板孔數、EAR 固定孔或材料不一致")
        # A matching source ID/count and internally consistent material alone
        # cannot prove these are the four CSV-derived screw holes. Compare
        # every actual CUTTING circle to the current numeric catalog and the
        # original projected physical face. No DXF or new source is created.
        from .receiving_nfb_numeric_panel_projection import (
            NfbV5PanelPattern, project_nfb_v5_to_panel,
        )
        if tuple(info.get("nfb_v5_source_models") or ()) != tuple(
            (pattern.brand, pattern.model) for pattern in part.patterns
        ):
            raise ValueError("CSV V5 底板型號來源與孔位模型不一致")
        actual_screws = {circle.source_id: circle for circle in screws}
        for hole_id, pattern in zip(part.hole_ids, part.patterns):
            if (not isinstance(pattern, NfbV5PanelPattern)
                    or pattern.feature != "screws"
                    or pattern.datum.part_id != part.part_id
                    or pattern.datum.role != "base-plate"
                    or pattern.screw_centres_uv_mm is None):
                raise ValueError("CSV V5 底板螺絲孔缺少實體來源投影")
            recalculated = project_nfb_v5_to_panel(
                pattern.brand, pattern.model, pattern.datum, feature="screws",
            )
            if (recalculated.screw_centres_uv_mm
                    != pattern.screw_centres_uv_mm
                    or recalculated.screw_diameter_mm != pattern.screw_diameter_mm):
                raise ValueError("CSV V5 螺絲孔已偏離目前 CSV 數值")
            diameter = float(recalculated.screw_diameter_mm)
            if not isfinite(diameter) or diameter <= 0:
                raise ValueError("CSV V5 螺絲孔直徑無效")
            for index, (x, y) in enumerate(
                recalculated.screw_centres_uv_mm, start=1
            ):
                observed = actual_screws[f"{hole_id}:screw:{index}"]
                if (abs(observed.center.x - x) > 1e-6
                        or abs(observed.center.y - y) > 1e-6
                        or abs(observed.radius - diameter / 2) > 1e-6
                        or observed.color != 30):
                    raise ValueError("CSV V5 CUTTING 螺絲孔與數值規格座標／孔徑不符")
        measured = material_polygon_from_final_scene(render.scene)
        if measured.symmetric_difference(render.material).area > 1e-4:
            raise ValueError("CSV V5 底板 FinalScene 與材料差異")
        physical_demands.append(PhysicalPartDemand(
            row.version_id, part.part_id, part.part_id,
            row.quantity, 1, render,
        ))
        parameters_by_source[(row.version_id, part.part_id)] = row.parameters
    groups = group_quantity_physical_demands(
        physical_demands, parameters_by_source,
    )
    return CsvV5BaseCheckPreview(
        groups=groups,
        physical_part_ids=tuple(sorted(part.part_id for part in
                                       (row.part for row in rows))),
    )
