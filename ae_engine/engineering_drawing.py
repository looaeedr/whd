# -*- coding: utf-8 -*-
# WHD 製造／3D 共用尺寸不變式（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 包外是折後外側面的成形尺寸；料段 len = 其包外段尺寸 −（實際相鄰折彎數 0/1/2 × T），已轉成料長的資料不得重扣 T。
# 展開 CUTTING = 料段累加；BEND 線位 = 同一料鏈的前綴和，不可直接拿包外尺寸充當展開折彎座標。
# 3D 須依相同 Fold Profile／料鏈／BEND 與角度成形；角度正負只決定方向，禁止從 3D bbox 反推料長。
# 這是板厚尺寸語意，非折彎展開補償；WRAP／OVERLAY 是裝配關係，不等於包外。

"""Shared Engineering Drawing projection built from canonical PartRenderData.

This module is downstream of manufacturing geometry. It owns only annotation
planning/layout and never mutates manufacturing CUTTING/BEND geometry.
"""
from __future__ import annotations

from dataclasses import dataclass

from .drawing_annotations import AnnotationPlan, plan_part_annotations
from .drawing_annotation_layout import AnnotationCollision, resolve_annotation_collisions
from .sheetmetal_drawing import LinePrimitive, TextPrimitive


AnnotationPrimitive = LinePrimitive | TextPrimitive


@dataclass(frozen=True)
class EngineeringDrawingProjection:
    """Immutable annotation projection shared by 2D and Engineering Drawing."""

    part_key: str
    annotation_plan: AnnotationPlan
    primitives: tuple[AnnotationPrimitive, ...]
    diagnostics: tuple[str, ...] = ()
    unresolved_collisions: tuple[AnnotationCollision, ...] = ()


def build_engineering_drawing_projection(
    render_data,
    *,
    part_key: str = "",
    char_height: float = 5.0,
    dimension_offset: float = 15.0,
    reserved_regions=(),
    strict: bool = False,
) -> EngineeringDrawingProjection:
    """Build annotation-only drawing data from canonical manufacturing output."""
    scene = getattr(render_data, "scene", None)
    material = getattr(render_data, "material", None)
    if scene is None or material is None:
        raise ValueError("canonical PartRenderData is required")

    before = tuple(getattr(scene, "primitives", ()) or ())
    plan = plan_part_annotations(
        render_data,
        char_height=float(char_height),
        dimension_offset=float(dimension_offset),
    )
    layout = resolve_annotation_collisions(
        plan,
        reserved_regions=tuple(reserved_regions or ()),
        manufacturing_scene=scene,
        strict=bool(strict),
    )
    after = tuple(getattr(scene, "primitives", ()) or ())
    if before != after:
        raise RuntimeError("annotation projection mutated manufacturing DrawingScene")

    primitives = tuple(
        primitive
        for primitive in tuple(layout.primitives or ())
        if isinstance(primitive, (LinePrimitive, TextPrimitive))
        and str(getattr(primitive, "layer", "")).upper() in {"DIMENSION", "TEXT"}
    )
    return EngineeringDrawingProjection(
        part_key=str(part_key or ""),
        annotation_plan=plan,
        primitives=primitives,
        diagnostics=tuple(layout.diagnostics or ()),
        unresolved_collisions=tuple(layout.unresolved_collisions or ()),
    )
