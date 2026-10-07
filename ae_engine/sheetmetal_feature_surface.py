# -*- coding: utf-8 -*-
"""Finished-face surface validation and feature placement guides."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

try:
    from shapely.geometry import Point as ShapelyPoint, Polygon as ShapelyPolygon, box as shapely_box
except Exception:  # pragma: no cover
    ShapelyPoint = None
    ShapelyPolygon = None
    shapely_box = None

from .sheetmetal_geometry import Vec2
from .sheetmetal_feature_core import (
    FeatureAnchor,
    CircleFeature,
    RectFeature,
    ProfileFeature,
    Feature,
    ResolvedCircle,
    ResolvedRect,
    ResolvedProfile,
    ResolvedFeature,
    _normalize_rotation,
    _rotate_local_point,
    _anchor_point,
    feature_finished_point,
)

@dataclass(frozen=True)
class FeatureSurface:
    """A generic polygonal region that may own user-created features.

    The validation engine deliberately knows nothing about part names.  Any
    valid polygon supplied by a structural result or finished-face adapter can
    become a feature surface.
    """
    surface_id: str
    outline: tuple[Vec2, ...]
    polygon: object
    allow_features: bool = True


def _require_surface_geometry() -> None:
    if ShapelyPolygon is None or ShapelyPoint is None or shapely_box is None:
        raise RuntimeError("Shapely is required for feature-surface validation")


def feature_surface_from_outline(surface_id: str, outline: Iterable[Vec2], *, allow_features: bool = True) -> FeatureSurface:
    _require_surface_geometry()
    pts = tuple(Vec2(float(p.x), float(p.y)) for p in outline)
    if len(pts) < 3:
        raise ValueError("feature surface requires at least 3 outline points")
    polygon = ShapelyPolygon([(p.x, p.y) for p in pts])
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.is_empty or polygon.area <= 0:
        raise ValueError("feature surface polygon must have positive area")
    return FeatureSurface(str(surface_id), pts, polygon, bool(allow_features))


def feature_surface_from_structural_result(surface_id: str, result, *, allow_features: bool = True) -> FeatureSurface:
    return feature_surface_from_outline(surface_id, result.outline, allow_features=allow_features)


def feature_surface_from_rect(surface_id: str, min_point: Vec2, max_point: Vec2, *, allow_features: bool = True) -> FeatureSurface:
    return feature_surface_from_outline(
        surface_id,
        (
            Vec2(min_point.x, min_point.y),
            Vec2(max_point.x, min_point.y),
            Vec2(max_point.x, max_point.y),
            Vec2(min_point.x, max_point.y),
        ),
        allow_features=allow_features,
    )


def _feature_footprint(feature: Feature, width: float, height: float):
    _require_surface_geometry()
    center = feature_finished_point(feature, width, height)
    if isinstance(feature, CircleFeature):
        return ShapelyPoint(center.x, center.y).buffer(float(feature.diameter) / 2.0, quad_segs=32)
    if isinstance(feature, RectFeature):
        hw = float(feature.width) / 2.0
        hh = float(feature.height) / 2.0
        local = (Vec2(-hw, -hh), Vec2(hw, -hh), Vec2(hw, hh), Vec2(-hw, hh))
    else:
        if getattr(feature, "layered_profiles", ()):
            from shapely.geometry import LineString
            from shapely.ops import unary_union
            geoms = []
            for _layer, profile_points, closed in feature.layered_profiles:
                pts = [center + _rotate_local_point(p, feature.rotation_deg) for p in profile_points]
                if closed and len(pts) >= 3:
                    geoms.append(ShapelyPolygon([(p.x, p.y) for p in pts]))
                elif len(pts) >= 2:
                    geoms.append(LineString([(p.x, p.y) for p in pts]))
            return unary_union(geoms) if geoms else ShapelyPoint(center.x, center.y)
        local = tuple(feature.points)
    pts = [center + _rotate_local_point(p, feature.rotation_deg) for p in local]
    return ShapelyPolygon([(p.x, p.y) for p in pts])


def feature_is_within_surface(surface: FeatureSurface, feature: Feature, width: float, height: float) -> bool:
    if not surface.allow_features:
        return False
    footprint = _feature_footprint(feature, float(width), float(height))
    return bool(surface.polygon.covers(footprint))


def feature_is_strictly_within_surface(surface: FeatureSurface, feature: Feature, width: float, height: float) -> bool:
    """Return True only when the complete footprint is inside without touching a surface boundary.

    Automatic source admission uses this stricter rule so a contour that touches,
    crosses, or lies outside a finished-face edge never reaches replacement/LOG.
    Interactive feature movement keeps using the boundary-inclusive helper above.
    """
    if not surface.allow_features:
        return False
    footprint = _feature_footprint(feature, float(width), float(height))
    if not surface.polygon.covers(footprint):
        return False
    return not bool(surface.polygon.boundary.intersects(footprint))

def move_feature_within_surface(
    feature: Feature,
    point: Vec2,
    width: float,
    height: float,
    surface: FeatureSurface,
) -> Feature:
    """Move to a world point only if the complete feature footprint remains legal.

    Returning the original immutable feature gives drag interactions a natural
    "stop at the last valid position" behaviour.
    """
    candidate = move_feature_to_finished_point(feature, point, width, height)
    return candidate if feature_is_within_surface(surface, candidate, width, height) else feature


def resolve_surface_features(
    surface: FeatureSurface,
    features: Iterable[Feature],
    width: float,
    height: float,
) -> list[ResolvedFeature]:
    """Resolve features already authored in the surface/world coordinate space.

    Every feature is validated by its complete footprint before being returned.
    """
    resolved: list[ResolvedFeature] = []
    for feature in features:
        if not feature_is_within_surface(surface, feature, width, height):
            raise ValueError(f"feature outside feature surface: {surface.surface_id}")
        center = feature_finished_point(feature, width, height)
        if isinstance(feature, CircleFeature):
            resolved.append(ResolvedCircle(
                center=center, radius=float(feature.diameter) / 2.0,
                layer=feature.layer, add_centerline=feature.add_centerline,
                source_type=feature.source_type,
            ))
        elif isinstance(feature, RectFeature):
            resolved.append(ResolvedRect(
                center=center, width=float(feature.width), height=float(feature.height),
                layer=feature.layer, source_type=feature.source_type, rotation_deg=_normalize_rotation(feature.rotation_deg),
            ))
        else:
            layered = tuple(
                (layer, tuple(center + _rotate_local_point(p, feature.rotation_deg) for p in pts), closed)
                for layer, pts, closed in getattr(feature, "layered_profiles", ())
            )
            resolved.append(ResolvedProfile(
                points=tuple(center + _rotate_local_point(p, feature.rotation_deg) for p in feature.points),
                layer=feature.layer, source_type=feature.source_type, layered_profiles=layered,
            ))
    return resolved


@dataclass(frozen=True)
class RectGuide:
    min_point: Vec2
    max_point: Vec2
    role: str

    @property
    def width(self) -> float:
        return float(self.max_point.x - self.min_point.x)

    @property
    def height(self) -> float:
        return float(self.max_point.y - self.min_point.y)


@dataclass(frozen=True)
class DimensionGuide:
    start: Vec2
    end: Vec2
    value: float
    axis: str


@dataclass(frozen=True)
class FeaturePlacement:
    anchor: FeatureAnchor
    offset: Vec2
    absolute_point: Vec2


@dataclass(frozen=True)
class PlacementGuideSet:
    anchor: FeatureAnchor
    anchor_point: Vec2
    feature_point: Vec2
    horizontal: DimensionGuide
    vertical: DimensionGuide
    center_alignment_x: bool = False
    center_alignment_y: bool = False


def resolve_endcap_finished_face_guide(width: float, depth: float, thickness: float) -> RectGuide:
    width = float(width)
    depth = float(depth)
    thickness = float(thickness)
    if thickness <= 0:
        raise ValueError("thickness must be > 0")
    if width <= 0 or depth <= 0:
        raise ValueError("width/depth must be > 0")
    return RectGuide(
        min_point=Vec2(2.0 * thickness, 2.0 * thickness),
        max_point=Vec2(width - 2.0 * thickness, depth - thickness),
        role="endcap_finished_face",
    )


def endcap_finished_feature_surface(width: float, depth: float, thickness: float, *, surface_id: str = "endcap_finished_face") -> FeatureSurface:
    guide = resolve_endcap_finished_face_guide(width, depth, thickness)
    return feature_surface_from_rect(surface_id, guide.min_point, guide.max_point)

def choose_feature_anchor(point: Vec2, width: float, height: float) -> FeatureAnchor:
    """Choose the nearest semantic anchor using normalized world-space distance."""
    width = float(width)
    height = float(height)
    if width <= 0 or height <= 0:
        raise ValueError("width/height must be > 0")
    order = (
        FeatureAnchor.PANEL_CENTER,
        FeatureAnchor.TOP_LEFT,
        FeatureAnchor.TOP_RIGHT,
        FeatureAnchor.BOTTOM_LEFT,
        FeatureAnchor.BOTTOM_RIGHT,
    )
    def score(anchor: FeatureAnchor) -> float:
        a = _anchor_point(anchor, width, height)
        dx = (point.x - a.x) / width
        dy = (point.y - a.y) / height
        return dx * dx + dy * dy
    return min(order, key=score)


def placement_from_finished_point(
    point: Vec2,
    width: float,
    height: float,
    preferred_anchor: FeatureAnchor | None = None,
) -> FeaturePlacement:
    anchor = preferred_anchor or choose_feature_anchor(point, width, height)
    anchor_point = _anchor_point(anchor, float(width), float(height))
    return FeaturePlacement(anchor=anchor, offset=point - anchor_point, absolute_point=point)


def reanchor_feature(feature: Feature, new_anchor: FeatureAnchor, width: float, height: float) -> Feature:
    point = feature_finished_point(feature, width, height)
    placement = placement_from_finished_point(point, width, height, preferred_anchor=new_anchor)
    return replace(feature, anchor=placement.anchor, offset=placement.offset)


def move_feature_to_finished_point(feature: Feature, point: Vec2, width: float, height: float) -> Feature:
    placement = placement_from_finished_point(point, width, height)
    return replace(feature, anchor=placement.anchor, offset=placement.offset)


def feature_with_offset(feature: Feature, offset: Vec2) -> Feature:
    return replace(feature, offset=offset)


def build_feature_placement_guides(
    feature: Feature,
    width: float,
    height: float,
    *,
    center_snap_tolerance: float = 2.0,
) -> PlacementGuideSet:
    anchor_point = _anchor_point(feature.anchor, float(width), float(height))
    point = feature_finished_point(feature, width, height)
    horizontal = DimensionGuide(
        start=Vec2(anchor_point.x, point.y),
        end=point,
        value=abs(point.x - anchor_point.x),
        axis="x",
    )
    vertical = DimensionGuide(
        start=Vec2(point.x, anchor_point.y),
        end=point,
        value=abs(point.y - anchor_point.y),
        axis="y",
    )
    return PlacementGuideSet(
        anchor=feature.anchor,
        anchor_point=anchor_point,
        feature_point=point,
        horizontal=horizontal,
        vertical=vertical,
        center_alignment_x=abs(point.x - float(width) / 2.0) <= center_snap_tolerance,
        center_alignment_y=abs(point.y - float(height) / 2.0) <= center_snap_tolerance,
    )
