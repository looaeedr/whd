# -*- coding: utf-8 -*-
"""Four-side flange geometry owner."""
from __future__ import annotations

from dataclasses import dataclass

try:
    from shapely.geometry import box, LineString
    from shapely.geometry.polygon import orient
    from shapely.ops import unary_union
except Exception:  # pragma: no cover
    box = None
    LineString = None
    orient = None
    unary_union = None

from .sheetmetal_geometry_core import GeometryError, Vec2, BendLine
from .sheetmetal_corner_policy import FourCornerTypePolicy, resolve_corner_relief
from .sheetmetal_geometry_shared import (
    _placed_corner_cut_polygons,
    _clip_axis_bend,
    _require_shapely,
    _normalize_ring,
)

@dataclass(frozen=True)
class FourSideFlangeGeometry:
    total_width: float
    total_height: float
    thickness: float
    left_fold: float
    right_fold: float
    top_fold: float
    bottom_fold: float


@dataclass(frozen=True)
class RectCornerReliefPolicy:
    bottom_left_x: float
    bottom_right_x: float
    top_left_x: float
    top_right_x: float
    bottom_y: float
    top_y: float

@dataclass(frozen=True)
class FourSideBendExtentPolicy:
    horizontal_to_blank_edges: bool = False


def _validate_four_side_geometry(g: FourSideFlangeGeometry) -> None:
    if g.total_width <= 0 or g.total_height <= 0:
        raise GeometryError("blank dimensions must be greater than zero")
    if g.thickness <= 0:
        raise GeometryError("板厚必須大於 0")
    if any(v < 0 for v in (g.left_fold, g.right_fold, g.top_fold, g.bottom_fold)):
        raise GeometryError("fold dimensions must not be negative")


def _validate_four_side(g: FourSideFlangeGeometry, policy: RectCornerReliefPolicy) -> None:
    _validate_four_side_geometry(g)
    values = (
        policy.bottom_left_x, policy.bottom_right_x,
        policy.top_left_x, policy.top_right_x,
        policy.bottom_y, policy.top_y,
    )
    if any(v < 0 for v in values):
        raise GeometryError("relief dimensions must not be negative")
    if policy.bottom_left_x + policy.bottom_right_x >= g.total_width:
        raise GeometryError("bottom corner reliefs consume blank width")
    if policy.top_left_x + policy.top_right_x >= g.total_width:
        raise GeometryError("top corner reliefs consume blank width")
    if policy.bottom_y + policy.top_y >= g.total_height:
        raise GeometryError("corner reliefs consume blank height")






def _four_side_type_cut_polygons(g: FourSideFlangeGeometry, policy: FourCornerTypePolicy):
    _validate_four_side_geometry(g)
    specs = {
        "bottom_left": (policy.bottom_left, g.left_fold, g.bottom_fold),
        "bottom_right": (policy.bottom_right, g.right_fold, g.bottom_fold),
        "top_left": (policy.top_left, g.left_fold, g.top_fold),
        "top_right": (policy.top_right, g.right_fold, g.top_fold),
    }
    cuts = []
    for name, (selection, fold_u, fold_v) in specs.items():
        relief = resolve_corner_relief(
            selection, fold_u=fold_u, fold_v=fold_v, thickness=g.thickness,
            fw=policy.fw_for(name),
        )
        if relief.primary_u > g.total_width or relief.primary_v > g.total_height:
            raise GeometryError("corner relief exceeds blank dimensions")
        if relief.secondary_u is not None and relief.secondary_u > g.total_width:
            raise GeometryError("secondary corner relief exceeds blank dimensions")
        if relief.secondary_depth is not None and relief.primary_v + relief.secondary_depth > g.total_height:
            raise GeometryError("secondary corner relief exceeds blank dimensions")
        cuts.extend(_placed_corner_cut_polygons(
            corner_name=name, relief=relief, width=g.total_width, height=g.total_height
        ))
    return cuts


def _four_side_material_polygon(
    g: FourSideFlangeGeometry,
    policy: RectCornerReliefPolicy | FourCornerTypePolicy,
):
    _require_shapely()
    w, h = g.total_width, g.total_height
    blank = box(0.0, 0.0, w, h)
    if isinstance(policy, RectCornerReliefPolicy):
        _validate_four_side(g, policy)
        cuts = [
            box(0.0, 0.0, policy.bottom_left_x, policy.bottom_y),
            box(w - policy.bottom_right_x, 0.0, w, policy.bottom_y),
            box(0.0, h - policy.top_y, policy.top_left_x, h),
            box(w - policy.top_right_x, h - policy.top_y, w, h),
        ]
    elif isinstance(policy, FourCornerTypePolicy):
        cuts = _four_side_type_cut_polygons(g, policy)
    else:
        raise TypeError(f"unsupported corner policy: {type(policy).__name__}")
    cut_union = unary_union(cuts) if cuts else None
    result = blank if cut_union is None else blank.difference(cut_union)
    if result.geom_type != "Polygon" or result.is_empty or not result.is_valid:
        raise GeometryError("invalid four-side flange outline")
    return orient(result, sign=1.0)


def build_four_side_outline(
    g: FourSideFlangeGeometry,
    policy: RectCornerReliefPolicy | FourCornerTypePolicy,
) -> list[Vec2]:
    result = _four_side_material_polygon(g, policy)
    return _normalize_ring(result.exterior.coords)



def build_four_side_bend_segments(
    g: FourSideFlangeGeometry,
    policy: RectCornerReliefPolicy | FourCornerTypePolicy,
    extent: FourSideBendExtentPolicy = FourSideBendExtentPolicy(),
) -> list[BendLine]:
    _require_shapely()
    material = _four_side_material_polygon(g, policy)
    w, h = g.total_width, g.total_height
    vertical = [
        _clip_axis_bend("left", LineString([(g.left_fold, 0.0), (g.left_fold, h)]), material, True),
        _clip_axis_bend("right", LineString([(w - g.right_fold, 0.0), (w - g.right_fold, h)]), material, True),
    ]
    if extent.horizontal_to_blank_edges:
        horizontal = [
            BendLine("bottom", Vec2(0.0, g.bottom_fold), Vec2(w, g.bottom_fold)),
            BendLine("top", Vec2(0.0, h - g.top_fold), Vec2(w, h - g.top_fold)),
        ]
    else:
        horizontal = [
            _clip_axis_bend("bottom", LineString([(0.0, g.bottom_fold), (w, g.bottom_fold)]), material, False),
            _clip_axis_bend("top", LineString([(0.0, h - g.top_fold), (w, h - g.top_fold)]), material, False),
        ]
    return vertical + horizontal
