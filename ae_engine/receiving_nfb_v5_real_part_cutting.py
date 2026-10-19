# -*- coding: utf-8 -*-
"""Real WHD PartRenderData/FinalScene V5 numeric cutting *trial*.

This is not a parallel renderer or a DXF-derived outline.  It applies the
operator's V5 numeric geometry to an actual canonical manufactured panel's
unfolded material and CUTTING primitives, so the same polygon can be consumed
by WHD's standard 2D and folded 3D machinery.  The caller must provide a
real per-part UV basis.  This trial NEVER sets production release metadata
and offers no DXF export API: physical datum/collision/export acceptance must
still be completed in the caller's actual part/manufacturing path.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from math import isfinite

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from .manufacturing_render_data import (
    PartRenderData, material_polygon_from_final_scene,
)
from .receiving_nfb_numeric_panel_projection import (
    NfbPanelDatum, NfbV5PanelPattern, project_nfb_v5_to_panel,
)
from .sheetmetal_drawing import DrawingScene

TRIAL_STATUS = "NFB_V5_REAL_PART_CUTTING_TRIAL_UNVERIFIED"


@dataclass(frozen=True)
class NfbV5RealPartCuttingTrial:
    part_id: str
    brand: str
    model: str
    feature: str
    pattern: NfbV5PanelPattern
    render_data: PartRenderData
    status: str = TRIAL_STATUS
    manufacturing_ready: bool = False


def trial_v5_numeric_cutting_on_real_part(
    baseline: PartRenderData,
    *,
    datum: NfbPanelDatum,
    brand: str,
    model: str,
    feature: str,
) -> NfbV5RealPartCuttingTrial:
    """Punch selected V5 shapes into an existing real sheet's FinalScene.

    Requires genuine material, Part ID and stable unfolded topology.  The
    supplied UV origin and axes are NOT guessed: manufacturing adapters own
    that positioning decision.  All holes must strictly fit existing material
    and be mutually separated; reject the whole edit otherwise.  Original
    CUTTING/BEND and original render data remain untouched.
    """
    if not isinstance(baseline, PartRenderData):
        raise TypeError("NFB V5 真實板件必須提供 PartRenderData")
    if not isinstance(datum, NfbPanelDatum):
        raise TypeError("NFB V5 必須提供板件 UV 基準")
    datum.validate()
    meta = dict(baseline.metadata or {})
    topology = baseline.unfolded_topology
    if (not meta.get("stable_id") or meta["stable_id"] != datum.part_id
            or topology is None or topology.piece_id != datum.part_id
            or baseline.material is None
            or not baseline.material.is_valid or baseline.material.is_empty):
        raise ValueError("NFB V5 缺少相同 Part ID 的真實板件幾何與展開基準")
    if (meta.get("nfb_trial_export_approved") is True
            or meta.get("nfb_v5_trial_status") is not None):
        raise ValueError("NFB V5 不可疊寫既有已提交或另一組試作孔")
    actual = material_polygon_from_final_scene(baseline.scene)
    if (actual.is_empty or
            not baseline.material.equals_exact(actual, 1e-6)):
        # Never re-cut a stale render whose scene/material have diverged.
        if actual.symmetric_difference(baseline.material).area > 1e-6:
            raise ValueError("NFB V5 真實板件 CUTTING 與實際板材不一致")
    pattern = project_nfb_v5_to_panel(
        brand, model, datum, feature=feature,
    )
    footprints = []
    if pattern.opening_uv_mm is not None:
        outline = Polygon(pattern.opening_uv_mm)
        if not outline.is_valid or outline.area <= 1e-9:
            raise ValueError("NFB V5 矩形開孔幾何不合法")
        footprints.append(outline)
    if pattern.screw_centres_uv_mm is not None:
        radius = pattern.screw_diameter_mm / 2.0
        if not isfinite(radius) or radius <= 0:
            raise ValueError("NFB V5 螺絲孔徑不合法")
        footprints.extend(
            Point(*center).buffer(radius, quad_segs=32)
            for center in pattern.screw_centres_uv_mm
        )
    if not footprints:
        raise ValueError("NFB V5 沒有可加工的數值孔")
    for i, foot in enumerate(footprints):
        # Strict containment protects BEND/blank boundaries and native holes.
        if not baseline.material.contains(foot):
            raise ValueError("NFB V5 孔超出實際板材或與既有孔重疊")
        for other in footprints[:i]:
            if foot.intersects(other):
                raise ValueError("NFB V5 新開孔與螺絲孔互相碰撞")
    whole = unary_union(footprints)
    scene = DrawingScene(list(baseline.scene.primitives))
    if pattern.opening_uv_mm is not None:
        scene.add_polyline(pattern.opening_uv_mm, layer="CUTTING",
                           closed=True, color=3)
    if pattern.screw_centres_uv_mm is not None:
        for index, center in enumerate(pattern.screw_centres_uv_mm):
            scene.add_circle(
                center, pattern.screw_diameter_mm / 2.0,
                layer="CUTTING", color=3,
                source_type="NFB_V5_NUMERIC_TRIAL",
                source_id=f"{datum.part_id}:nfb-v5:{brand}:{model}:screw:{index+1}",
            )
    material = material_polygon_from_final_scene(scene)
    expected = baseline.material.difference(whole)
    if (material.is_empty or not material.is_valid or
            material.symmetric_difference(expected).area > 1e-5
            or baseline.material.area - material.area <= 1e-9):
        raise ValueError("NFB V5 真實 FinalScene 材料挖孔驗算失敗")
    trial = replace(
        baseline, scene=scene, material=material,
        metadata={
            **meta,
            "nfb_v5_trial_status": TRIAL_STATUS,
            "nfb_v5_numeric_source": (brand, model),
            "nfb_v5_feature": feature,
            "nfb_v5_target_role": datum.role,
            "nfb_trial_export_approved": False,
        },
    )
    return NfbV5RealPartCuttingTrial(
        part_id=datum.part_id, brand=brand, model=model, feature=feature,
        pattern=pattern, render_data=trial,
    )
