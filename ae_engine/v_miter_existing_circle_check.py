# -*- coding: utf-8 -*-
"""One narrowly source-qualified existing CUTTING circle for Custom EndCap V CHECK.

The existing V stock/mother/Fold solvers accept a single solid outer polygon.
This adapter proves exactly one genuine *additional* through-hole against the
original Engine PartSpec/FinalScene/PartRenderData.material before handing them
a detached outer-only CHECK input. It never modifies canonical material, grants
production DXF, or pretends the existing thick 3D includes the hole.
"""
from __future__ import annotations

from dataclasses import replace
import math

from shapely.geometry import Point, Polygon

from .contracts import EndCapPartSpec
from .manufacturing_render_data import (
    PartRenderData, material_polygon_from_final_scene,
)
from .sheetmetal_drawing import CirclePrimitive, DrawingScene, PolylinePrimitive
from .sheetmetal_feature_core import CircleFeature, FeatureAnchor
from .sheetmetal_geometry_core import GeometryError
from .v_miter_material_trial import _single_source_material

UNSUPPORTED_HOLE_3D = "V_MITER_LIVE_EXISTING_CUTTING_HOLE_3D_UNSUPPORTED"
_SOURCE_ERROR = "V_MITER_EXISTING_HOLE_SOURCE_UNVERIFIED"


def qualify_live_endcap_circle_source(part_spec, render_data):
    """Return (detached solid-only CHECK input, original CirclePrimitive, void).

    No-hole inputs and all non-EndCap callers retain their exact old behavior.
    This first slice accepts one genuine PANEL_CENTER CircleFeature in a Custom
    EndCap only. More CUTTING paths, duplicated/ambiguous holes, lost interior
    material, unsupported Families and provenance drift fail closed.
    """
    if not isinstance(part_spec, EndCapPartSpec):
        return render_data, None, None
    if (not isinstance(render_data, PartRenderData)
            or not isinstance(render_data.scene, DrawingScene)):
        raise GeometryError(_SOURCE_ERROR)
    scene = render_data.scene
    cutting = tuple(
        p for p in scene.primitives
        if str(getattr(p, "layer", "")).upper() == "CUTTING"
    )
    circles = tuple(p for p in cutting if isinstance(p, CirclePrimitive))
    if not circles:
        # Existing zero-hole source still uses the original strict path.
        # Do not accept a silently missing hole in a mismatched Custom input.
        if (part_spec.model_name == "自訂"
                and (getattr(render_data.material, "interiors", ())
                     or any(isinstance(p, CircleFeature) and p.layer == "CUTTING"
                            for p in part_spec.holes))):
            raise GeometryError(_SOURCE_ERROR)
        return render_data, None, None
    if (part_spec.model_name != "自訂"
            or len(cutting) != 2 or len(circles) != 1
            or len(part_spec.holes) != 1
            or not isinstance(part_spec.holes[0], CircleFeature)
            or part_spec.holes[0].anchor is not FeatureAnchor.PANEL_CENTER
            or part_spec.holes[0].layer != "CUTTING"
            or part_spec.holes[0].add_centerline
            or not isinstance(render_data.material, Polygon)):
        raise GeometryError(_SOURCE_ERROR)
    circle = circles[0]
    if (any(type(value) not in (int, float) or not math.isfinite(value)
            for value in (circle.center.x, circle.center.y, circle.radius))
            or circle.radius <= 0
            or abs(circle.radius * 2 - part_spec.holes[0].diameter) > 1e-8):
        raise GeometryError(_SOURCE_ERROR)
    outer_rows = tuple(p for p in cutting if isinstance(p, PolylinePrimitive))
    if len(outer_rows) != 1:
        raise GeometryError(_SOURCE_ERROR)
    outer_scene = DrawingScene([p for p in scene.primitives if p is not circle])
    outer = _single_source_material(outer_scene)
    material = render_data.material
    if (not material.is_valid or material.is_empty
            or len(material.interiors) != 1
            or outer.area <= material.area):
        raise GeometryError(_SOURCE_ERROR)
    # Exactly match Engine's existing canonical CUTTING circle polygonization
    # (32 quadrants/segments), not a guessed inscribed hole or largest outline.
    void = Point(circle.center.x, circle.center.y).buffer(
        circle.radius, quad_segs=32,
    )
    if (not outer.contains(void) or outer.boundary.distance(void) <= 1e-6
            or outer.difference(void).symmetric_difference(material).area > 1e-6):
        raise GeometryError(_SOURCE_ERROR)
    try:
        scene_material = material_polygon_from_final_scene(scene)
        # Rebuild the original Custom EndCap PartSpec with the same existing
        # public manufacturing API, so caller-forged scenes cannot be endorsed.
        from .manufacturing_api import build_operator_part_render_data
        rebuilt = build_operator_part_render_data(part_spec)
    except (TypeError, ValueError, GeometryError) as exc:
        raise GeometryError(_SOURCE_ERROR) from exc
    if (not isinstance(rebuilt, PartRenderData)
            or tuple(rebuilt.scene.primitives) != tuple(scene.primitives)
            or not isinstance(rebuilt.material, Polygon)
            or rebuilt.material.symmetric_difference(material).area > 1e-6
            or scene_material.symmetric_difference(material).area > 1e-6):
        raise GeometryError(_SOURCE_ERROR)
    return replace(render_data, scene=outer_scene, material=outer), circle, void
