# -*- coding: utf-8 -*-
"""Headless projection of canonical physical corner-relief measurements.

This is a read-only Engine API adapter over the existing certified material
measurement owner; it does not generate new CUTTING or DXF geometry.
"""
from __future__ import annotations

from dataclasses import dataclass

from .assembly_collision_corner import (
    CornerReliefMeasurement, measure_material_corner_reliefs,
)


@dataclass(frozen=True)
class RenderCornerDimensionGroup:
    """Measurements for one physical material carrier (or one whole part)."""

    role: str | None
    measurements: tuple[CornerReliefMeasurement, ...]


def project_render_corner_relief_measurements(render_data) -> tuple[RenderCornerDimensionGroup, ...]:
    """Measure actual resolved material, never GUI labels or preview geometry.

    Multi-piece BoxBody displays each physical piece in the original order.
    For a single part the returned role is None; a sheet without real corner
    material removal produces no row rather than a manufactured dimension.
    """
    groups = []
    pieces = tuple(getattr(render_data, "pieces", ()) or ())
    if pieces:
        for piece in pieces:
            material = getattr(getattr(piece, "render_data", None), "material", None)
            measurements = measure_material_corner_reliefs(material)
            if not measurements:
                continue
            role = str(getattr(piece, "role", getattr(piece, "key", "板件")) or "板件")
            groups.append(RenderCornerDimensionGroup(role, tuple(measurements)))
    else:
        material = getattr(render_data, "material", None)
        measurements = measure_material_corner_reliefs(material)
        if measurements:
            groups.append(RenderCornerDimensionGroup(None, tuple(measurements)))
    return tuple(groups)
