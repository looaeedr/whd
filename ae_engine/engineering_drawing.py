# -*- coding: utf-8 -*-
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
