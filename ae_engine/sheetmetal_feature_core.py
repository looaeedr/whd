# -*- coding: utf-8 -*-
"""Core sheet-metal feature values and BoxBody face projection.

This is the lowest feature layer. It never imports the public
sheetmetal_features facade.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .sheetmetal_geometry import (
    Vec2,
    StripFoldChain,
    FourCornerTypePolicy,
    box_body_vertical_offsets,
)

class FeatureAnchor(Enum):
    ABSOLUTE_FINISHED_FACE = "absolute_finished_face"
    PANEL_CENTER = "panel_center"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


@dataclass(frozen=True)
class CircleFeature:
    diameter: float
    anchor: FeatureAnchor
    offset: Vec2
    layer: str = "CUTTING"
    add_centerline: bool = False
    source_type: str | None = None
    source_params: tuple[tuple[str, object], ...] = ()
    rotation_deg: int = 0


@dataclass(frozen=True)
class RectFeature:
    width: float
    height: float
    anchor: FeatureAnchor
    offset: Vec2
    layer: str = "CUTTING"
    source_type: str | None = None
    source_params: tuple[tuple[str, object], ...] = ()
    rotation_deg: int = 0


@dataclass(frozen=True)
class ProfileFeature:
    points: tuple[Vec2, ...]
    anchor: FeatureAnchor
    offset: Vec2
    layer: str = "CUTTING"
    source_type: str | None = None
    source_params: tuple[tuple[str, object], ...] = ()
    rotation_deg: int = 0
    layered_profiles: tuple[tuple[str, tuple[Vec2, ...], bool], ...] = ()


@dataclass(frozen=True)
class ResolvedCircle:
    center: Vec2
    radius: float
    layer: str = "CUTTING"
    add_centerline: bool = False
    source_type: str | None = None


@dataclass(frozen=True)
class ResolvedRect:
    center: Vec2
    width: float
    height: float
    layer: str = "CUTTING"
    source_type: str | None = None
    rotation_deg: int = 0

    @property
    def points(self) -> tuple[Vec2, Vec2, Vec2, Vec2]:
        hw = self.width / 2.0
        hh = self.height / 2.0
        local = (Vec2(-hw, -hh), Vec2(hw, -hh), Vec2(hw, hh), Vec2(-hw, hh))
        return tuple(self.center + _rotate_local_point(p, self.rotation_deg) for p in local)


@dataclass(frozen=True)
class ResolvedProfile:
    points: tuple[Vec2, ...]
    layer: str = "CUTTING"
    source_type: str | None = None
    layered_profiles: tuple[tuple[str, tuple[Vec2, ...], bool], ...] = ()


ResolvedFeature = ResolvedCircle | ResolvedRect | ResolvedProfile
Feature = CircleFeature | RectFeature | ProfileFeature


BOX_BODY_FACE_SEGMENTS = {
    "left": "depth_left",
    "back": "front",
    "right": "depth_right",
}


@dataclass(frozen=True)
class BoxBodyFaceContext:
    """User-facing WHD face coordinates mapped to one unfolded strip segment.

    The editor always exposes the enclosure dimensions directly.  For example,
    a 500×600×200 enclosure shows side faces as 200×600 and the back face as
    500×600.  Thickness compensation is only applied here, at the boundary
    between user coordinates and manufacturing/unfolded coordinates.
    """

    face_key: str
    segment_name: str
    outer_width: float
    outer_height: float
    thickness: float
    unfolded_min_x: float
    unfolded_max_x: float
    unfolded_height: float
    bottom_outer_offset: float
    top_outer_offset: float

    def local_to_unfolded(self, point: Vec2) -> Vec2:
        flat_width = self.outer_width - 2.0 * self.thickness
        flat_height = self.outer_height - self.bottom_outer_offset - self.top_outer_offset
        if flat_width <= 0 or flat_height <= 0:
            raise ValueError("套用截角裝配偏移後，箱身面尺寸必須仍大於 0")
        span_x = self.unfolded_max_x - self.unfolded_min_x
        x = self.unfolded_min_x + ((point.x - self.thickness) / flat_width) * span_x
        y = ((point.y - self.bottom_outer_offset) / flat_height) * self.unfolded_height
        return Vec2(x, y)

    def unfolded_to_local(self, point: Vec2) -> Vec2:
        span_x = self.unfolded_max_x - self.unfolded_min_x
        if span_x <= 0 or self.unfolded_height <= 0:
            raise ValueError("invalid unfolded box body face span")
        flat_width = self.outer_width - 2.0 * self.thickness
        flat_height = self.outer_height - self.bottom_outer_offset - self.top_outer_offset
        x = self.thickness + ((point.x - self.unfolded_min_x) / span_x) * flat_width
        y = self.bottom_outer_offset + (point.y / self.unfolded_height) * flat_height
        return Vec2(x, y)


def box_body_face_dimensions(*, w: float, h: float, d: float) -> dict[str, tuple[float, float]]:
    """Return direct enclosure dimensions for the three editable Box Body faces."""
    w = float(w); h = float(h); d = float(d)
    if w <= 0 or h <= 0 or d <= 0:
        raise ValueError("W/H/D must be > 0")
    return {
        "left": (d, h),
        "back": (w, h),
        "right": (d, h),
    }


def box_body_face_contexts_from_strip(
    topology: StripFoldChain,
    *,
    w: float,
    h: float,
    d: float,
    t: float,
    head_corner_policy: FourCornerTypePolicy | None = None,
    tail_corner_policy: FourCornerTypePolicy | None = None,
) -> dict[str, BoxBodyFaceContext]:
    """Create direct-WHD face contexts from the authoritative StripFoldChain."""
    if not isinstance(topology, StripFoldChain):
        raise ValueError("box body topology must be StripFoldChain")
    dims = box_body_face_dimensions(w=w, h=h, d=d)
    t = float(t)
    if t <= 0:
        raise ValueError("thickness must be > 0")
    bottom_outer_offset, top_outer_offset = box_body_vertical_offsets(
        t,
        head_corner_policy=head_corner_policy,
        tail_corner_policy=tail_corner_policy,
    )

    spans: dict[str, tuple[float, float]] = {}
    cursor = 0.0
    for segment in topology.segments:
        span = float(segment.length) + float(segment.compensation)
        spans[segment.name] = (cursor, cursor + span)
        cursor += span

    contexts: dict[str, BoxBodyFaceContext] = {}
    for face_key, segment_name in BOX_BODY_FACE_SEGMENTS.items():
        if segment_name not in spans:
            raise ValueError(f"box body topology has no {segment_name} segment")
        outer_width, outer_height = dims[face_key]
        x0, x1 = spans[segment_name]
        contexts[face_key] = BoxBodyFaceContext(
            face_key=face_key,
            segment_name=segment_name,
            outer_width=outer_width,
            outer_height=outer_height,
            thickness=t,
            unfolded_min_x=x0,
            unfolded_max_x=x1,
            unfolded_height=float(topology.height),
            bottom_outer_offset=bottom_outer_offset,
            top_outer_offset=top_outer_offset,
        )
    return contexts


def _resolve_box_body_face_feature(context: BoxBodyFaceContext, feature: Feature) -> ResolvedFeature:
    local_center = feature_finished_point(feature, context.outer_width, context.outer_height)
    center = context.local_to_unfolded(local_center)
    if isinstance(feature, CircleFeature):
        return ResolvedCircle(
            center=center,
            radius=float(feature.diameter) / 2.0,
            layer=feature.layer,
            add_centerline=feature.add_centerline,
            source_type=feature.source_type,
        )
    if isinstance(feature, RectFeature):
        return ResolvedRect(
            center=center,
            width=float(feature.width),
            height=float(feature.height),
            layer=feature.layer,
            source_type=feature.source_type,
            rotation_deg=_normalize_rotation(feature.rotation_deg),
        )

    mapped_points = []
    for local_point in feature.points:
        rotated = _rotate_local_point(local_point, feature.rotation_deg)
        mapped_points.append(context.local_to_unfolded(local_center + rotated))
    layered = []
    for layer, pts, closed in feature.layered_profiles:
        mapped = []
        for local_point in pts:
            rotated = _rotate_local_point(local_point, feature.rotation_deg)
            mapped.append(context.local_to_unfolded(local_center + rotated))
        layered.append((layer, tuple(mapped), closed))
    return ResolvedProfile(
        tuple(mapped_points),
        layer=feature.layer,
        source_type=feature.source_type,
        layered_profiles=tuple(layered),
    )


def resolve_box_body_face_features(
    contexts: dict[str, BoxBodyFaceContext],
    face_features: dict[str, Iterable[Feature]] | None,
) -> list[ResolvedFeature]:
    """Resolve three face-local WHD feature stores into one unfolded Box Body scene."""
    if not face_features:
        return []
    resolved: list[ResolvedFeature] = []
    for face_key in ("left", "back", "right"):
        context = contexts[face_key]
        for feature in face_features.get(face_key, ()):  # stable face order for preview/tests
            resolved.append(_resolve_box_body_face_feature(context, feature))
    return resolved

def _normalize_rotation(rotation_deg: int | float) -> int:
    value = int(round(float(rotation_deg))) % 360
    if value not in (0, 90, 180, 270):
        raise ValueError("rotation must be 0/90/180/270/360 degrees")
    return value


def _rotate_local_point(point: Vec2, rotation_deg: int | float) -> Vec2:
    rotation = _normalize_rotation(rotation_deg)
    if rotation == 0:
        return point
    if rotation == 90:
        return Vec2(-point.y, point.x)
    if rotation == 180:
        return Vec2(-point.x, -point.y)
    return Vec2(point.y, -point.x)

def _anchor_point(
    anchor: FeatureAnchor,
    width: float,
    height: float,
) -> Vec2:
    if anchor is FeatureAnchor.ABSOLUTE_FINISHED_FACE:
        return Vec2(0.0, 0.0)
    if anchor is FeatureAnchor.PANEL_CENTER:
        return Vec2(width / 2.0, height / 2.0)
    if anchor is FeatureAnchor.TOP_LEFT:
        return Vec2(0.0, height)
    if anchor is FeatureAnchor.TOP_RIGHT:
        return Vec2(width, height)
    if anchor is FeatureAnchor.BOTTOM_LEFT:
        return Vec2(0.0, 0.0)
    if anchor is FeatureAnchor.BOTTOM_RIGHT:
        return Vec2(width, 0.0)
    raise ValueError(f"Unsupported anchor: {anchor}")

def feature_finished_point(feature: Feature, width: float, height: float) -> Vec2:
    return _anchor_point(feature.anchor, float(width), float(height)) + feature.offset
