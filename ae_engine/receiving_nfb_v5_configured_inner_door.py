# -*- coding: utf-8 -*-
"""Physical NFB V5 inner-door CUTTING trial using the established #1497 X/Y.

Unlike a centre-of-blank demonstration, this consumes actual configured
world X, actual upper inner-door placement and current operator layer Y.
The result is real PartRenderData (2D/3D common FinalScene) but *never* a
manufacturing-capability grant or an exportable customer DXF.

The opening goes on the INNER DOOR.  Mounting screws on other parts are
separately owned by those parts; do not punch them in this door.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from hashlib import sha256
from math import isfinite
from typing import Mapping, Sequence

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from .manufacturing_api import build_inner_door_panel_render_data
from .manufacturing_render_data import PartRenderData, material_polygon_from_final_scene
from .receiving_nfb_legacy_feature_bridge import existing_inner_door_feature_finalscene
from .receiving_nfb_manufacturing_release import _resolve_physical_panel
from .receiving_nfb_numeric_catalog import brand_csv_path
from .receiving_nfb_model_identity import parse_numeric_model_ref
from .receiving_nfb_numeric_panel_projection import (
    NfbPanelDatum, NfbV5PanelPattern, project_nfb_v5_to_panel,
)
from .receiving_nfb_y_projection import project_nfb_inner_door_nominal_y
from .sheetmetal_drawing import DrawingScene

STATUS = "NFB_V5_CONFIGURED_INNER_DOOR_FINALSCENE_TRIAL_UNVERIFIED"
AXES = {
    0: ((1, 0), (0, 1)),
    90: ((0, 1), (-1, 0)),
    180: ((-1, 0), (0, -1)),
    270: ((0, -1), (1, 0)),
}


@dataclass(frozen=True)
class NfbV5ConfiguredInnerDoorHole:
    physical_hole_id: str
    brand: str
    model_ref: str
    world_x_mm: float
    layer_count: int
    slot_index: int
    rotation_deg: int = 0


@dataclass(frozen=True)
class NfbV5ConfiguredInnerDoorTrial:
    part_id: str
    hole_ids: tuple[str, ...]
    patterns: tuple[NfbV5PanelPattern, ...]
    render_data: PartRenderData
    status: str = STATUS
    manufacturing_ready: bool = False


def trial_configured_nfb_v5_inner_door_render_data(
    snapshot: Mapping[str, object],
    inner_door_id: str,
    *,
    holes: Sequence[NfbV5ConfiguredInnerDoorHole],
    existing_render_data: PartRenderData | None = None,
) -> NfbV5ConfiguredInnerDoorTrial:
    """Atomically cut configured V5 rectangles into one *physical* upper door.

    No guessed world X, no mapping from model names to implied X, and no
    original-DXF filename masquerading as a V5 model. Fail closed on missing
    numbers, model/brand mismatch, reused IDs, existing legacy collisions,
    neighbouring V5 collisions, and out-of-core placement.
    """
    entries = tuple(holes)
    if not entries:
        raise ValueError("NFB V5 內門必須有已配置的開孔")
    if any(not isinstance(entry, NfbV5ConfiguredInnerDoorHole) for entry in entries):
        raise TypeError("NFB V5 必須傳入已配置的實體孔位")

    # Verify the same immutable CSV source for the INNER DOOR and every
    # actual tier Base Plate. The source may change between opening preview
    # and base screw projection even when the hole centre stays unchanged.
    source_brands = {entry.brand for entry in entries}
    def csv_source_hashes():
        try:
            return tuple(sorted(
                (brand, sha256(brand_csv_path(brand).read_bytes()).hexdigest())
                for brand in source_brands
            ))
        except OSError as exc:
            raise ValueError("NFB V5 內門缺少目前廠牌 CSV 來源") from exc

    source_sha = csv_source_hashes()
    panel, placement = _resolve_physical_panel(snapshot, inner_door_id)
    baseline = existing_inner_door_feature_finalscene(
        snapshot, panel, existing_render_data=existing_render_data,
    )
    if baseline is None:
        baseline = build_inner_door_panel_render_data(panel)
    if (baseline.unfolded_topology is None
            or baseline.unfolded_topology.piece_id != panel.stable_id
            or baseline.metadata.get("stable_id") != panel.stable_id
            or baseline.metadata.get("cell_key") != panel.cell_key
            or baseline.metadata.get("nfb_v5_trial_status") is not None
            or baseline.metadata.get("nfb_trial_export_approved") is True):
        raise ValueError("NFB V5 原實體內門／已提交來源不一致")
    actual = material_polygon_from_final_scene(baseline.scene)
    if (baseline.material is None or baseline.material.is_empty
            or baseline.material.symmetric_difference(actual).area > 1e-6):
        raise ValueError("NFB V5 原內門 FinalScene 與實際材料不一致")

    # A hole must be on this door's FLAT FINISHED CORE, not on folded flanges.
    core = box(panel.fold_left, panel.fold_bottom,
               panel.unfolded_width - panel.fold_right,
               panel.unfolded_height - panel.fold_top)
    core_width = panel.unfolded_width - panel.fold_left - panel.fold_right
    if core_width <= 0:
        raise ValueError("NFB V5 內門實體折邊／核心寬度錯誤")

    ids: set[str] = set()
    patterns: list[NfbV5PanelPattern] = []
    polygons: list[Polygon] = []
    for entry in entries:
        if not isinstance(entry, NfbV5ConfiguredInnerDoorHole):
            raise TypeError("NFB V5 必須傳入已配置的實體孔位")
        owner = entry.physical_hole_id
        if not isinstance(owner, str) or not owner.strip() or owner in ids:
            raise ValueError("NFB V5 重複或缺少實體孔 ID")
        ids.add(owner)
        parsed = parse_numeric_model_ref(entry.model_ref)
        if parsed is None or parsed[0] != entry.brand:
            raise ValueError("NFB V5 型號與實際有效廠牌不一致")
        if (type(entry.world_x_mm) not in (int, float)
                or not isfinite(float(entry.world_x_mm))):
            raise ValueError("NFB V5 必須提供實際配置的 world X")
        if type(entry.rotation_deg) is not int or entry.rotation_deg not in AXES:
            raise ValueError("NFB V5 旋轉角度只允許 0/90/180/270")
        x_world = float(entry.world_x_mm)
        uv_x = (panel.fold_left + core_width / 2.0
                + x_world - float(placement.world_offset[0]))
        recovered = (float(placement.world_offset[0])
                     + uv_x - panel.fold_left - core_width / 2.0)
        if not isfinite(uv_x) or not isfinite(recovered) or abs(x_world - recovered) > 1e-7:
            raise ValueError("NFB V5 裝配 X 到內門展開 UV 反算不一致")
        y = project_nfb_inner_door_nominal_y(
            snapshot, inner_door_id,
            layer_count=entry.layer_count, slot_index=entry.slot_index,
        )
        if y.part_id != panel.stable_id or y.cell_key != panel.cell_key:
            raise ValueError("NFB V5 層高投影到錯誤實體內門")
        ux, uy = AXES[entry.rotation_deg]
        datum = NfbPanelDatum(panel.stable_id, "inner-door",
                              (uv_x, y.unfolded_uv_y_mm), ux, uy)
        pattern = project_nfb_v5_to_panel(
            entry.brand, parsed[1], datum, feature="opening",
        )
        if pattern.screw_centres_uv_mm is not None:
            raise ValueError("NFB V5 內門只允許主開孔，螺絲孔屬其他板件")
        polygon = Polygon(pattern.opening_uv_mm)
        if (not polygon.is_valid or polygon.area <= 1e-9
                or not core.contains(polygon)
                or not baseline.material.contains(polygon)):
            raise ValueError("NFB V5 開孔超出內門平面或碰到既有 Hole Editor 孔")
        if any(polygon.intersects(other) for other in polygons):
            raise ValueError("NFB V5 內門新孔彼此碰撞，整批拒絕")
        patterns.append(pattern)
        polygons.append(polygon)

    if csv_source_hashes() != source_sha:
        raise ValueError("NFB V5 內門計算期間 CSV 來源已變更")
    candidate_scene = DrawingScene(list(baseline.scene.primitives))
    for pattern in patterns:
        candidate_scene.add_polyline(
            pattern.opening_uv_mm, layer="CUTTING", closed=True, color=3,
        )
    actual_material = material_polygon_from_final_scene(candidate_scene)
    calculated = baseline.material.difference(unary_union(polygons))
    if (actual_material.is_empty or not actual_material.is_valid
            or actual_material.symmetric_difference(calculated).area > 1e-5):
        raise ValueError("NFB V5 實際 FinalScene 挖孔結果不一致")

    trial = replace(
        baseline, scene=candidate_scene, material=actual_material,
        metadata={
            **dict(baseline.metadata),
            "nfb_v5_trial_status": STATUS,
            "nfb_v5_source_models": tuple((p.brand, p.model) for p in patterns),
            "nfb_v5_source_csv_sha256": source_sha,
            "nfb_v5_hole_ids": tuple(entry.physical_hole_id for entry in entries),
            "nfb_trial_export_approved": False,
        },
    )
    return NfbV5ConfiguredInnerDoorTrial(
        part_id=panel.stable_id,
        hole_ids=tuple(entry.physical_hole_id for entry in entries),
        patterns=tuple(patterns),
        render_data=trial,
    )
