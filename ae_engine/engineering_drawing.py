# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

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
