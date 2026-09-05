# -*- coding: utf-8 -*-
"""Pure 2D feature placement for holes/cutouts/marking.

No tkinter or ezdxf dependency is allowed here.  This module converts design
intent in finished-face coordinates into resolved unfolded geometry that can be
consumed by both GUI preview and DXF serialization.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable

try:
    from shapely.geometry import Point as ShapelyPoint, Polygon as ShapelyPolygon, LineString as ShapelyLineString, box as shapely_box
except Exception:  # pragma: no cover
    ShapelyPoint = None
    ShapelyPolygon = None
    ShapelyLineString = None
    shapely_box = None

from .sheetmetal_geometry import Vec2, EndCapGeometry, ReliefConfig, StripFoldChain, FourCornerTypePolicy, box_body_vertical_offsets, calculate_endcap_relief_dimensions


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


class ReferenceAnchor(Enum):
    CENTER = "center"
    TOP_CENTER = "top_center"
    BOTTOM_CENTER = "bottom_center"
    LEFT_CENTER = "left_center"
    RIGHT_CENTER = "right_center"
    TOP_LEFT = "top_left"
    BOTTOM_LEFT = "bottom_left"
    TOP_RIGHT = "top_right"
    BOTTOM_RIGHT = "bottom_right"


REFERENCE_ANCHOR_LABELS = {
    ReferenceAnchor.CENTER: "中心",
    ReferenceAnchor.TOP_CENTER: "中上",
    ReferenceAnchor.BOTTOM_CENTER: "中下",
    ReferenceAnchor.LEFT_CENTER: "中左",
    ReferenceAnchor.RIGHT_CENTER: "中右",
    ReferenceAnchor.TOP_LEFT: "左上",
    ReferenceAnchor.BOTTOM_LEFT: "左下",
    ReferenceAnchor.TOP_RIGHT: "右上",
    ReferenceAnchor.BOTTOM_RIGHT: "右下",
}
REFERENCE_ANCHOR_BY_LABEL = {label: anchor for anchor, label in REFERENCE_ANCHOR_LABELS.items()}


@dataclass(frozen=True)
class ReferenceNeighbor:
    index: int
    feature: Feature
    anchor_point: Vec2
    perpendicular_distance: float
    axis_distance: float


@dataclass(frozen=True)
class ReferenceDistances:
    x_side: str
    y_side: str
    x_edge_distance: float
    y_edge_distance: float
    x_neighbor_index: int | None
    y_neighbor_index: int | None
    x_neighbor_distance: float | None
    y_neighbor_distance: float | None


def feature_reference_anchor(feature: Feature) -> ReferenceAnchor:
    params = dict(getattr(feature, "source_params", ()))
    raw = params.get("reference_anchor", ReferenceAnchor.CENTER.value)
    try:
        return ReferenceAnchor(str(raw))
    except ValueError:
        return ReferenceAnchor.CENTER


def feature_with_reference_anchor(feature: Feature, anchor: ReferenceAnchor) -> Feature:
    params = dict(getattr(feature, "source_params", ()))
    params["reference_anchor"] = anchor.value
    return replace(feature, source_params=tuple(sorted(params.items(), key=lambda item: item[0])))


def feature_with_process(feature: Feature, process: str) -> Feature:
    process = str(process).upper()
    if process not in {"CUTTING", "BLIND_HOLE"}:
        raise ValueError("process must be CUTTING or BLIND_HOLE")
    if isinstance(feature, ProfileFeature):
        layered = tuple((process, pts, closed) for _layer, pts, closed in feature.layered_profiles)
        return replace(feature, layer=process, layered_profiles=layered)
    return replace(feature, layer=process)


def _feature_bounds(feature: Feature, width: float, height: float) -> tuple[float, float, float, float]:
    footprint = _feature_footprint(feature, width, height)
    return tuple(float(v) for v in footprint.bounds)


def feature_reference_point(feature: Feature, anchor: ReferenceAnchor, width: float, height: float) -> Vec2:
    minx, miny, maxx, maxy = _feature_bounds(feature, width, height)
    cx = (minx + maxx) / 2.0
    cy = (miny + maxy) / 2.0
    mapping = {
        ReferenceAnchor.CENTER: (cx, cy),
        ReferenceAnchor.TOP_CENTER: (cx, maxy),
        ReferenceAnchor.BOTTOM_CENTER: (cx, miny),
        ReferenceAnchor.LEFT_CENTER: (minx, cy),
        ReferenceAnchor.RIGHT_CENTER: (maxx, cy),
        ReferenceAnchor.TOP_LEFT: (minx, maxy),
        ReferenceAnchor.BOTTOM_LEFT: (minx, miny),
        ReferenceAnchor.TOP_RIGHT: (maxx, maxy),
        ReferenceAnchor.BOTTOM_RIGHT: (maxx, miny),
    }
    x, y = mapping[anchor]
    return Vec2(x, y)


def _surface_axis_edges(surface: FeatureSurface, point: Vec2) -> tuple[float, float, float, float]:
    _require_surface_geometry()
    minx, miny, maxx, maxy = surface.polygon.bounds
    span = max(maxx-minx, maxy-miny, 1.0) * 2.0 + 10.0
    h = ShapelyLineString([(minx-span, point.y), (maxx+span, point.y)])
    v = ShapelyLineString([(point.x, miny-span), (point.x, maxy+span)])
    hi = surface.polygon.intersection(h)
    vi = surface.polygon.intersection(v)
    if hi.is_empty or vi.is_empty:
        return float(minx), float(maxx), float(miny), float(maxy)
    hminx, _, hmaxx, _ = hi.bounds
    _, vminy, _, vmaxy = vi.bounds
    return float(hminx), float(hmaxx), float(vminy), float(vmaxy)


def _reference_axis_edges(surface: FeatureSurface, point: Vec2, reference_guide: "RectGuide | None" = None) -> tuple[float, float, float, float]:
    if reference_guide is not None:
        return (
            float(reference_guide.min_point.x), float(reference_guide.max_point.x),
            float(reference_guide.min_point.y), float(reference_guide.max_point.y),
        )
    return _surface_axis_edges(surface, point)


def reference_edge_directions(surface: FeatureSurface, feature: Feature, anchor: ReferenceAnchor, width: float, height: float, reference_guide: "RectGuide | None" = None) -> tuple[str, str]:
    p = feature_reference_point(feature, anchor, width, height)
    left, right, bottom, top = _reference_axis_edges(surface, p, reference_guide)
    if anchor in {ReferenceAnchor.LEFT_CENTER, ReferenceAnchor.TOP_LEFT, ReferenceAnchor.BOTTOM_LEFT}:
        x_side = "left"
    elif anchor in {ReferenceAnchor.RIGHT_CENTER, ReferenceAnchor.TOP_RIGHT, ReferenceAnchor.BOTTOM_RIGHT}:
        x_side = "right"
    else:
        dl, dr = abs(p.x-left), abs(right-p.x)
        x_side = "left" if dl <= dr else "right"
    if anchor in {ReferenceAnchor.TOP_CENTER, ReferenceAnchor.TOP_LEFT, ReferenceAnchor.TOP_RIGHT}:
        y_side = "top"
    elif anchor in {ReferenceAnchor.BOTTOM_CENTER, ReferenceAnchor.BOTTOM_LEFT, ReferenceAnchor.BOTTOM_RIGHT}:
        y_side = "bottom"
    else:
        db, dt = abs(p.y-bottom), abs(top-p.y)
        y_side = "bottom" if db <= dt else "top"
    return x_side, y_side


def find_reference_neighbor(features: Iterable[Feature], current_index: int, anchor: ReferenceAnchor, axis: str, side: str, width: float, height: float) -> ReferenceNeighbor | None:
    items = list(features)
    if not (0 <= current_index < len(items)):
        return None
    axis = axis.lower(); side = side.lower()
    current_p = feature_reference_point(items[current_index], anchor, width, height)
    ranked = []
    for i, feature in enumerate(items):
        if i == current_index:
            continue
        p = feature_reference_point(feature, anchor, width, height)
        if axis == "x":
            delta = p.x-current_p.x
            if (side == "left" and delta >= -1e-9) or (side == "right" and delta <= 1e-9):
                continue
            perpendicular = abs(p.y-current_p.y)
            along = abs(delta)
        elif axis == "y":
            delta = p.y-current_p.y
            if (side == "bottom" and delta >= -1e-9) or (side == "top" and delta <= 1e-9):
                continue
            perpendicular = abs(p.x-current_p.x)
            along = abs(delta)
        else:
            raise ValueError("axis must be x or y")
        ranked.append((perpendicular, along, i, feature, p))
    if not ranked:
        return None
    perpendicular, along, i, feature, p = min(ranked, key=lambda row: (row[0], row[1], row[2]))
    return ReferenceNeighbor(i, feature, p, float(perpendicular), float(along))


def reference_distances(surface: FeatureSurface, features: Iterable[Feature], current_index: int, anchor: ReferenceAnchor, width: float, height: float, reference_guide: "RectGuide | None" = None) -> ReferenceDistances:
    items = list(features)
    feature = items[current_index]
    p = feature_reference_point(feature, anchor, width, height)
    x_side, y_side = reference_edge_directions(surface, feature, anchor, width, height, reference_guide)
    left, right, bottom, top = _reference_axis_edges(surface, p, reference_guide)
    x_edge = p.x-left if x_side == "left" else right-p.x
    y_edge = p.y-bottom if y_side == "bottom" else top-p.y
    xn = find_reference_neighbor(items, current_index, anchor, "x", x_side, width, height)
    yn = find_reference_neighbor(items, current_index, anchor, "y", y_side, width, height)
    return ReferenceDistances(
        x_side=x_side, y_side=y_side,
        x_edge_distance=float(x_edge), y_edge_distance=float(y_edge),
        x_neighbor_index=None if xn is None else xn.index,
        y_neighbor_index=None if yn is None else yn.index,
        x_neighbor_distance=None if xn is None else float(xn.axis_distance),
        y_neighbor_distance=None if yn is None else float(yn.axis_distance),
    )


def move_feature_by_reference_distance(surface: FeatureSurface, features: Iterable[Feature], current_index: int, anchor: ReferenceAnchor, width: float, height: float, *, axis: str, mode: str, value: float, reference_guide: "RectGuide | None" = None) -> Feature:
    items = list(features)
    feature = items[current_index]
    current_ref = feature_reference_point(feature, anchor, width, height)
    distances = reference_distances(surface, items, current_index, anchor, width, height, reference_guide)
    axis = axis.lower(); mode = mode.lower(); value = float(value)
    target_ref = Vec2(current_ref.x, current_ref.y)
    if axis == "x":
        side = distances.x_side
        if mode == "edge":
            left, right, _, _ = _reference_axis_edges(surface, current_ref, reference_guide)
            tx = left + value if side == "left" else right - value
        elif mode == "neighbor":
            idx = distances.x_neighbor_index
            if idx is None:
                return feature
            np = feature_reference_point(items[idx], anchor, width, height)
            tx = np.x + value if side == "left" else np.x - value
        else:
            raise ValueError("mode must be edge or neighbor")
        target_ref = Vec2(tx, current_ref.y)
    elif axis == "y":
        side = distances.y_side
        if mode == "edge":
            _, _, bottom, top = _reference_axis_edges(surface, current_ref, reference_guide)
            ty = bottom + value if side == "bottom" else top - value
        elif mode == "neighbor":
            idx = distances.y_neighbor_index
            if idx is None:
                return feature
            np = feature_reference_point(items[idx], anchor, width, height)
            ty = np.y + value if side == "bottom" else np.y - value
        else:
            raise ValueError("mode must be edge or neighbor")
        target_ref = Vec2(current_ref.x, ty)
    else:
        raise ValueError("axis must be x or y")
    delta = target_ref-current_ref
    center = feature_finished_point(feature, width, height)
    return move_feature_within_surface(feature, center+delta, width, height, surface)



def circle_center_distance_from_gap(gap: float, diameter_a: float, diameter_b: float) -> float:
    """Return circle center distance for a requested shortest perimeter gap."""
    return float(gap) + float(diameter_a) / 2.0 + float(diameter_b) / 2.0


def circle_gap_from_center_distance(center_distance: float, diameter_a: float, diameter_b: float) -> float:
    """Return shortest perimeter gap represented by a circle center distance."""
    return float(center_distance) - float(diameter_a) / 2.0 - float(diameter_b) / 2.0


def align_circle_to_neighbor(
    feature: CircleFeature,
    neighbor: CircleFeature,
    alignment: str,
    axis: str,
    width: float,
    height: float,
) -> CircleFeature:
    """Align one circle to a circular neighbor on the axis perpendicular to a run.

    Horizontal runs (axis='x') support center/top/bottom perimeter alignment.
    Vertical runs preserve the selected circle's Y and center-align X because the
    requested pipe-top/pipe-bottom semantics describe horizontal pipe rows.
    """
    if not isinstance(feature, CircleFeature) or not isinstance(neighbor, CircleFeature):
        raise TypeError("circle alignment requires circular features")
    axis = str(axis).lower()
    alignment = str(alignment).lower()
    if alignment not in {"center", "top", "bottom"}:
        raise ValueError("alignment must be center, top, or bottom")
    if axis not in {"x", "y"}:
        raise ValueError("axis must be x or y")
    point = feature_finished_point(feature, width, height)
    other = feature_finished_point(neighbor, width, height)
    if axis == "x":
        if alignment == "center":
            y = other.y
        elif alignment == "top":
            y = other.y + float(neighbor.diameter) / 2.0 - float(feature.diameter) / 2.0
        else:
            y = other.y - float(neighbor.diameter) / 2.0 + float(feature.diameter) / 2.0
        target = Vec2(point.x, y)
    else:
        target = Vec2(other.x, point.y)
    return move_feature_to_finished_point(feature, target, width, height)


def _round_pattern_pitch(feature: CircleFeature, driver: str, value: float) -> float:
    driver = str(driver).lower()
    value = float(value)
    if driver == "center":
        pitch = value
    elif driver == "gap":
        pitch = circle_center_distance_from_gap(value, feature.diameter, feature.diameter)
    else:
        raise ValueError("driver must be center or gap")
    if pitch <= 0:
        raise ValueError("round-hole pitch must be > 0")
    return pitch


def _round_candidate(seed: CircleFeature, x: float, y: float, width: float, height: float) -> CircleFeature:
    return move_feature_to_finished_point(seed, Vec2(float(x), float(y)), width, height)


def generate_round_fill(
    seed: CircleFeature,
    surface: FeatureSurface,
    *,
    width: float,
    height: float,
    direction: str,
    driver: str,
    value: float,
) -> tuple[CircleFeature, ...]:
    """Fill from the current seed position in one/all requested directions."""
    if not isinstance(seed, CircleFeature):
        raise TypeError("round fill requires a CircleFeature seed")
    direction = str(direction).lower()
    valid = {"left", "right", "up", "down", "both_horizontal", "both_vertical"}
    if direction not in valid:
        raise ValueError(f"unsupported round fill direction: {direction}")
    pitch = _round_pattern_pitch(seed, driver, value)
    origin = feature_finished_point(seed, width, height)
    if not feature_is_within_surface(surface, seed, width, height):
        return ()

    def walk(dx: float, dy: float) -> list[CircleFeature]:
        result = []
        i = 1
        while i < 10000:
            candidate = _round_candidate(seed, origin.x + dx * pitch * i, origin.y + dy * pitch * i, width, height)
            if not feature_is_within_surface(surface, candidate, width, height):
                break
            result.append(candidate)
            i += 1
        return result

    if direction == "right":
        return tuple([seed] + walk(1, 0))
    if direction == "left":
        return tuple(list(reversed(walk(-1, 0))) + [seed])
    if direction == "up":
        return tuple([seed] + walk(0, 1))
    if direction == "down":
        return tuple(list(reversed(walk(0, -1))) + [seed])
    if direction == "both_horizontal":
        return tuple(list(reversed(walk(-1, 0))) + [seed] + walk(1, 0))
    return tuple(list(reversed(walk(0, -1))) + [seed] + walk(0, 1))


def generate_round_refill(
    seed: CircleFeature,
    surface: FeatureSurface,
    *,
    width: float,
    height: float,
    direction: str,
    driver: str,
    value: float,
) -> tuple[CircleFeature, ...]:
    """Rebuild a full row/column without preserving the seed's run coordinate."""
    if not isinstance(seed, CircleFeature):
        raise TypeError("round refill requires a CircleFeature seed")
    direction = str(direction).lower()
    valid = {"left", "right", "up", "down", "both_horizontal", "both_vertical"}
    if direction not in valid:
        raise ValueError(f"unsupported round refill direction: {direction}")
    pitch = _round_pattern_pitch(seed, driver, value)
    center = feature_finished_point(seed, width, height)
    minx, miny, maxx, maxy = (float(v) for v in surface.polygon.bounds)
    r = float(seed.diameter) / 2.0

    horizontal = direction in {"left", "right", "both_horizontal"}
    lo = (minx + r) if horizontal else (miny + r)
    hi = (maxx - r) if horizontal else (maxy - r)
    span = max(0.0, hi - lo)
    count = max(1, int(span // pitch) + 1)
    used = pitch * (count - 1)
    if direction in {"left", "down"}:
        start = lo
    elif direction in {"right", "up"}:
        start = hi - used
    else:
        start = lo + (span - used) / 2.0

    result = []
    for i in range(count):
        along = start + pitch * i
        point = Vec2(along, center.y) if horizontal else Vec2(center.x, along)
        candidate = _round_candidate(seed, point.x, point.y, width, height)
        if feature_is_within_surface(surface, candidate, width, height):
            result.append(candidate)
    return tuple(result)

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


@dataclass(frozen=True)
class VaultEndCapFeaturePolicy:
    hanging_hole_radius: float
    hanging_hole_y_from_top_bend: float
    square_hole_origin: Vec2
    square_hole_size: Vec2
    tail_bottom_hole_radius: float
    tail_bottom_hole_y: float
    hanging_hole_offset_from_primary: float = 10.5


def resolve_vault_endcap_fixed_features(
    geometry: EndCapGeometry,
    *,
    relief_config: ReliefConfig,
    policy: VaultEndCapFeaturePolicy,
    is_tail: bool,
) -> tuple[ResolvedFeature, ...]:
    relief = calculate_endcap_relief_dimensions(geometry, relief_config)
    hanging_y = geometry.total_depth - abs(geometry.top_first_fold) + float(policy.hanging_hole_y_from_top_bend)
    left_x = relief.top_primary_left + float(policy.hanging_hole_offset_from_primary)
    right_x = geometry.total_width - relief.top_primary_right - float(policy.hanging_hole_offset_from_primary)
    features: list[ResolvedFeature] = [
        ResolvedCircle(
            center=Vec2(left_x, hanging_y),
            radius=float(policy.hanging_hole_radius),
            layer="CUTTING",
            source_type="vault_endcap_hanging",
        ),
        ResolvedCircle(
            center=Vec2(right_x, hanging_y),
            radius=float(policy.hanging_hole_radius),
            layer="CUTTING",
            source_type="vault_endcap_hanging",
        ),
        ResolvedRect(
            center=Vec2(
                policy.square_hole_origin.x + policy.square_hole_size.x / 2.0,
                policy.square_hole_origin.y + policy.square_hole_size.y / 2.0,
            ),
            width=float(policy.square_hole_size.x),
            height=float(policy.square_hole_size.y),
            layer="CUTTING",
            source_type="vault_endcap_square",
        ),
    ]
    if is_tail:
        features.append(
            ResolvedCircle(
                center=Vec2(geometry.total_width / 2.0, float(policy.tail_bottom_hole_y)),
                radius=float(policy.tail_bottom_hole_radius),
                layer="CUTTING",
                source_type="vault_tail_bottom",
            )
        )
    return tuple(features)



@dataclass(frozen=True)
class CanvasTransform:
    """Map millimetre world coordinates (Y up) to Canvas pixels (Y down)."""

    scale: float
    origin_x: float
    origin_y: float

    def __post_init__(self) -> None:
        if self.scale <= 0:
            raise ValueError("scale must be > 0")

    def world_to_canvas(self, point: Vec2) -> tuple[float, float]:
        return (
            self.origin_x + point.x * self.scale,
            self.origin_y - point.y * self.scale,
        )

    def canvas_to_world(self, x: float, y: float) -> Vec2:
        return Vec2(
            (x - self.origin_x) / self.scale,
            (self.origin_y - y) / self.scale,
        )


@dataclass(frozen=True)
class EndCapFeatureContext:
    finished_width: float
    finished_depth: float
    thickness: float
    left_fold: float
    right_fold: float
    bottom_fold: float
    unfolded_width: float

    @property
    def unfolded_flat_left(self) -> float:
        return abs(self.left_fold)

    @property
    def unfolded_flat_right(self) -> float:
        return self.unfolded_width - abs(self.right_fold)

    @property
    def unfolded_flat_bottom(self) -> float:
        return self.bottom_fold

    @property
    def unfolded_flat_top(self) -> float:
        return self.bottom_fold + (self.finished_depth - 3.0 * self.thickness)


def legacy_hole_to_feature(hole: dict) -> Feature:
    """Convert existing GUI hole dictionaries into semantic Features."""
    htype = hole["type"]
    offset = Vec2(float(hole["x"]), float(hole["y"]))
    params = hole.get("params", {})
    rotation = int(params.get("rotation_deg", 0))
    explicit_layer = params.get("layer")

    if "points" in params:
        points = tuple(Vec2(float(x), float(y)) for x, y in params["points"])
        layered_raw = params.get("layered_profiles", ())
        layered_profiles = tuple(
            (str(layer), tuple(Vec2(float(x), float(y)) for x, y in pts), bool(closed))
            for layer, pts, closed in layered_raw
        )
        return ProfileFeature(
            points=points,
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=offset,
            layer=str(explicit_layer or ("FROM_DXF" if layered_profiles else "CUTTING")),
            source_type=htype,
            source_params=tuple(sorted((str(k), v) for k, v in params.items() if k not in {"points", "layered_profiles", "rotation_deg", "layer"})),
            rotation_deg=rotation,
            layered_profiles=layered_profiles,
        )
    if "width" in params and "height" in params:
        return RectFeature(
            width=float(params["width"]),
            height=float(params["height"]),
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=offset,
            layer=str(explicit_layer or "CUTTING"),
            source_type=htype,
            source_params=tuple(sorted((str(k), v) for k, v in params.items() if k not in {"width", "height", "rotation_deg", "layer"})),
            rotation_deg=rotation,
        )
    if "diameter" in params:
        is_pipe = htype == "管孔" or str(explicit_layer or "") == "BLIND_HOLE"
        return CircleFeature(
            diameter=float(params["diameter"]),
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=offset,
            layer=str(explicit_layer or ("BLIND_HOLE" if is_pipe else "CUTTING")),
            add_centerline=is_pipe,
            source_type=htype,
            source_params=tuple(sorted((str(k), v) for k, v in params.items() if k not in {"diameter", "rotation_deg", "layer"})),
            rotation_deg=rotation,
        )
    raise ValueError(f"Unsupported legacy hole type: {htype}")



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


def feature_finished_point(feature: Feature, width: float, height: float) -> Vec2:
    return _anchor_point(feature.anchor, float(width), float(height)) + feature.offset


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


def feature_to_legacy_hole(feature: Feature, width: float, height: float) -> dict:
    point = feature_finished_point(feature, width, height)
    source_type = feature.source_type
    if not source_type:
        source_type = "方形" if isinstance(feature, RectFeature) else "圓形"
    params = dict(feature.source_params)
    if isinstance(feature, CircleFeature):
        params["diameter"] = float(feature.diameter)
    elif isinstance(feature, RectFeature):
        params["width"] = float(feature.width)
        params["height"] = float(feature.height)
    else:
        params["points"] = tuple((float(p.x), float(p.y)) for p in feature.points)
        if getattr(feature, "layered_profiles", ()):
            params["layered_profiles"] = tuple(
                (layer, tuple((float(p.x), float(p.y)) for p in pts), bool(closed))
                for layer, pts, closed in feature.layered_profiles
            )
    if getattr(feature, "rotation_deg", 0):
        params["rotation_deg"] = int(feature.rotation_deg)
    if getattr(feature, "layer", "CUTTING") != "CUTTING" and not (source_type == "管孔" and feature.layer == "BLIND_HOLE"):
        params["layer"] = feature.layer
    return {"type": source_type, "x": point.x, "y": point.y, "params": params}


def expand_linear_pattern(feature: Feature, count: int, pitch: float, axis: str) -> tuple[Feature, ...]:
    count = int(count)
    if count < 1:
        raise ValueError("count must be >= 1")
    axis = axis.lower()
    if axis not in {"x", "y"}:
        raise ValueError("axis must be 'x' or 'y'")
    result = []
    for i in range(count):
        delta = Vec2(float(pitch) * i, 0.0) if axis == "x" else Vec2(0.0, float(pitch) * i)
        result.append(replace(feature, offset=feature.offset + delta))
    return tuple(result)


def expand_grid_pattern(
    feature: Feature,
    rows: int,
    columns: int,
    pitch_x: float,
    pitch_y: float,
) -> tuple[Feature, ...]:
    rows = int(rows)
    columns = int(columns)
    if rows < 1 or columns < 1:
        raise ValueError("rows/columns must be >= 1")
    result = []
    for row in range(rows):
        for column in range(columns):
            delta = Vec2(float(pitch_x) * column, float(pitch_y) * row)
            result.append(replace(feature, offset=feature.offset + delta))
    return tuple(result)


def _map_endcap_finished_point(ctx: EndCapFeatureContext, point: Vec2) -> Vec2:
    """Preserve the legacy end-cap finished-face → unfolded linear mapping."""

    finished_flat_width = ctx.finished_width - 4.0 * ctx.thickness
    finished_flat_depth = ctx.finished_depth - 3.0 * ctx.thickness

    if abs(finished_flat_width) > 1e-12:
        x = ctx.unfolded_flat_left + (
            (point.x - 2.0 * ctx.thickness) / finished_flat_width
        ) * (ctx.unfolded_flat_right - ctx.unfolded_flat_left)
    else:
        x = ctx.unfolded_flat_left

    if abs(finished_flat_depth) > 1e-12:
        y = ctx.unfolded_flat_bottom + (
            (point.y - 2.0 * ctx.thickness) / finished_flat_depth
        ) * (ctx.unfolded_flat_top - ctx.unfolded_flat_bottom)
    else:
        y = ctx.unfolded_flat_bottom

    return Vec2(x, y)


def endcap_feature_context_from_geometry(geometry, finished_width: float, finished_depth: float) -> EndCapFeatureContext:
    """Build the shared finished-face -> unfolded mapping context from authoritative EndCapGeometry."""
    return EndCapFeatureContext(
        finished_width=float(finished_width),
        finished_depth=float(finished_depth),
        thickness=float(geometry.thickness),
        left_fold=float(geometry.left_fold),
        right_fold=float(geometry.right_fold),
        bottom_fold=float(geometry.bottom_fold),
        unfolded_width=float(geometry.total_width),
    )


def resolve_endcap_features(
    context: EndCapFeatureContext,
    features: Iterable[Feature],
) -> list[ResolvedFeature]:
    resolved: list[ResolvedFeature] = []
    for feature in features:
        anchor = _anchor_point(
            feature.anchor,
            context.finished_width,
            context.finished_depth,
        )
        finished_point = anchor + feature.offset
        center = _map_endcap_finished_point(context, finished_point)

        if isinstance(feature, CircleFeature):
            resolved.append(
                ResolvedCircle(
                    center=center,
                    radius=feature.diameter / 2.0,
                    layer=feature.layer,
                    add_centerline=feature.add_centerline,
                    source_type=feature.source_type,
                )
            )
        elif isinstance(feature, RectFeature):
            resolved.append(
                ResolvedRect(
                    center=center,
                    width=feature.width,
                    height=feature.height,
                    layer=feature.layer,
                    source_type=feature.source_type,
                    rotation_deg=_normalize_rotation(feature.rotation_deg),
                )
            )
        else:
            finished_center = finished_point
            mapped_points = []
            for local_point in feature.points:
                rotated = _rotate_local_point(local_point, feature.rotation_deg)
                mapped_points.append(_map_endcap_finished_point(context, finished_center + rotated))
            layered = []
            for layer, pts, closed in getattr(feature, "layered_profiles", ()):
                mapped = []
                for local_point in pts:
                    rotated = _rotate_local_point(local_point, feature.rotation_deg)
                    mapped.append(_map_endcap_finished_point(context, finished_center + rotated))
                layered.append((layer, tuple(mapped), closed))
            resolved.append(ResolvedProfile(tuple(mapped_points), layer=feature.layer, source_type=feature.source_type, layered_profiles=tuple(layered)))
    return resolved



def identify_door_baseline_nameplate_circles(circle_rows, *, radius_tolerance: float = 0.05, y_tolerance: float = 0.1) -> dict[str, str]:
    """Return baseline entity-handle -> stable nameplate feature ID.

    The current certified Door baseline encodes the nameplate pair as exactly
    two CUTTING circles of radius 1.6 mm on one horizontal centerline. This
    parser turns that baseline signature into durable feature identity once;
    downstream consumers use ``nameplate_mount`` instead of rediscovering two
    anonymous circles by screen position.
    """
    rows = []
    for raw in tuple(circle_rows or ()):
        handle, layer, x, y, radius = raw
        if str(layer).upper() != "CUTTING":
            continue
        if abs(float(radius) - 1.6) <= float(radius_tolerance):
            rows.append((str(handle), float(x), float(y)))
    if len(rows) != 2 or abs(rows[0][2] - rows[1][2]) > float(y_tolerance):
        return {}
    rows.sort(key=lambda item: item[1])
    return {
        rows[0][0]: "door:nameplate_mount:left",
        rows[1][0]: "door:nameplate_mount:right",
    }

def resolved_circles_from_baseline(mapped_circles) -> list[ResolvedCircle]:
    """Normalize existing baseline mapping output without changing its geometry.

    Supports both historic shapes: ``((x, y), radius, layer)`` and
    ``(x, y, radius, layer)``.
    """
    resolved: list[ResolvedCircle] = []
    for item in mapped_circles:
        if len(item) == 3:
            center, radius, layer = item
            x, y = center
        elif len(item) == 4:
            x, y, radius, layer = item
        else:
            raise ValueError(f"Unsupported mapped circle shape: {item!r}")
        resolved.append(
            ResolvedCircle(
                center=Vec2(float(x), float(y)),
                radius=float(radius),
                layer=str(layer),
                add_centerline=(str(layer) == "MARKING"),
                source_type="baseline",
            )
        )
    return resolved


@dataclass(frozen=True)
class DoorIndicatorContext:
    finished_width: float
    finished_height: float
    left_fold: float
    bottom_fold: float
    center_override: Vec2 | None = None

    def group_center(self, layer_groups: list[int] | tuple[int, ...]) -> Vec2:
        g_max = max(layer_groups) if layer_groups else 1
        if self.center_override is not None:
            return self.center_override
        dx_offset = 28.0 if g_max == 1 else 18.0
        return Vec2(
            self.left_fold + self.finished_width / 2.0 - dx_offset,
            self.bottom_fold + self.finished_height / 2.0 - 25.0,
        )


def indicator_box_outer_size(layer_groups: list[int] | tuple[int, ...]) -> tuple[float, float]:
    groups = tuple(int(v) for v in layer_groups)
    if not groups:
        raise ValueError("indicator box requires at least one layer")
    if any(v <= 0 for v in groups):
        raise ValueError("indicator box group counts must be > 0")
    g_max = max(groups)
    width = 326.0 if g_max == 1 else 171.0 + 90.0 * (g_max - 1) + 135.0
    height = 445.0 + 280.0 * (len(groups) - 1)
    return width, height


def indicator_box_opening_size(
    layer_groups: list[int] | tuple[int, ...],
    *,
    thickness: float,
) -> tuple[float, float]:
    """Door cutout needed by one indicator-box assembly."""
    outer_w, outer_h = indicator_box_outer_size(layer_groups)
    t = float(thickness)
    return outer_w - 98.0 - t, outer_h - 98.0 - t


def resolve_door_indicator_features(
    context: DoorIndicatorContext,
    layer_groups: list[int] | tuple[int, ...],
    offset: Vec2 = Vec2(0.0, 0.0),
) -> list[ResolvedCircle]:
    """Resolve the legacy vault door indicator/nameplate pattern once.

    The returned coordinates are unfolded/world coordinates and are shared by
    GUI preview and DXF serialization.
    """
    groups = [int(value) for value in layer_groups]
    layers = len(groups)
    if layers == 0:
        return []
    g_max = max(groups) if groups else 1

    if g_max == 1:
        box_width = 326.0
    else:
        box_width = 171.0 + 90.0 * (g_max - 1) + 135.0
    box_height = 280.0 * max(0, layers - 1) + 445.0

    center = context.group_center(groups) + offset
    resolved: list[ResolvedCircle] = []

    for ly, g_current in enumerate(groups):
        if g_current <= 0:
            continue
        layer_y_start = 133.5 + 280.0 * (layers - 1 - ly)
        for i in range(g_current):
            local_x = 191.0 if g_max == 1 else 171.0 + 90.0 * i
            dx = local_x - box_width / 2.0

            for j in range(3):
                local_y = layer_y_start + 90.0 * j
                dy = local_y - box_height / 2.0
                resolved.append(
                    ResolvedCircle(
                        center=Vec2(center.x + dx, center.y + dy),
                        radius=15.5,
                        layer="CUTTING",
                        source_type="indicator_lamp",
                    )
                )

            y_top_light = layer_y_start + 180.0
            dy_plate = (y_top_light + 48.0) - box_height / 2.0
            for local_plate_x in (local_x - 22.0, local_x + 22.0):
                dx_plate = local_plate_x - box_width / 2.0
                resolved.append(
                    ResolvedCircle(
                        center=Vec2(center.x + dx_plate, center.y + dy_plate),
                        radius=1.6,
                        layer="CUTTING",
                        source_type="nameplate_mount",
                    )
                )

    if g_max <= 1:
        hole_count = 1
    elif g_max <= 3:
        hole_count = 2
    elif g_max <= 5:
        hole_count = 3
    else:
        hole_count = 4

    x_left_light = 171.0
    x_right_light = 171.0 + 90.0 * max(0, g_max - 1)
    if hole_count > 1:
        max_pitch = (x_right_light - x_left_light) / (hole_count - 1)
        pitch = max(50.0, float(int(max_pitch // 50) * 50))
    else:
        pitch = 150.0

    marking_xs: list[float] = []
    for k in range(hole_count):
        if hole_count > 1:
            x_mid = (x_left_light + x_right_light) / 2.0
            local_x = x_mid - (hole_count - 1) * pitch / 2.0 + pitch * k
        else:
            local_x = 191.0
        marking_xs.append(local_x)

    for ly in range(layers):
        local_y = 178.5 + 280.0 * (layers - 1 - ly)
        dy = local_y - box_height / 2.0
        for local_x in marking_xs:
            if local_x < box_width - 49.0:
                dx = local_x - box_width / 2.0
                resolved.append(
                    ResolvedCircle(
                        center=Vec2(center.x + dx, center.y + dy),
                        radius=2.0,
                        layer="MARKING",
                        add_centerline=True,
                        source_type="wireway_mark",
                    )
                )

    return resolved


@dataclass(frozen=True)
class WorldBounds:
    min_x: float
    min_y: float
    max_x: float
    max_y: float

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y

    def expanded(self, amount: float) -> "WorldBounds":
        amount = float(amount)
        return WorldBounds(
            self.min_x - amount,
            self.min_y - amount,
            self.max_x + amount,
            self.max_y + amount,
        )

    def contains(self, point: Vec2) -> bool:
        return (
            self.min_x <= point.x <= self.max_x
            and self.min_y <= point.y <= self.max_y
        )


@dataclass(frozen=True)
class DoorIndicatorLayout:
    context: DoorIndicatorContext
    layer_groups: tuple[int, ...]
    offset: Vec2
    features: tuple[ResolvedCircle, ...]
    interaction_bounds: WorldBounds
    base_interaction_center: Vec2
    left_lamp_center: Vec2
    top_lamp_center: Vec2

    def hit_test(self, point: Vec2, padding: float = 15.0) -> bool:
        return self.interaction_bounds.expanded(padding).contains(point)

    def clamp_offset(self, desired_offset: Vec2) -> Vec2:
        face = WorldBounds(
            self.context.left_fold,
            self.context.bottom_fold,
            self.context.left_fold + self.context.finished_width,
            self.context.bottom_fold + self.context.finished_height,
        )
        half_w = self.interaction_bounds.width / 2.0
        half_h = self.interaction_bounds.height / 2.0
        min_x = face.min_x + half_w - self.base_interaction_center.x
        max_x = face.max_x - half_w - self.base_interaction_center.x
        min_y = face.min_y + half_h - self.base_interaction_center.y
        max_y = face.max_y - half_h - self.base_interaction_center.y
        return Vec2(
            min(max(float(desired_offset.x), min_x), max_x),
            min(max(float(desired_offset.y), min_y), max_y),
        )


@dataclass(frozen=True)
class DoorIndicatorPosition:
    reference_x: float
    reference_y: float
    target_x: float
    target_y: float
    distance_x: float
    distance_y: float


def resolve_door_indicator_dimension_guides(
    position: DoorIndicatorPosition,
) -> tuple[DimensionGuide, DimensionGuide]:
    return (
        DimensionGuide(
            start=Vec2(position.reference_x, position.target_y),
            end=Vec2(position.target_x, position.target_y),
            value=position.distance_x,
            axis="x",
        ),
        DimensionGuide(
            start=Vec2(position.target_x, position.reference_y),
            end=Vec2(position.target_x, position.target_y),
            value=position.distance_y,
            axis="y",
        ),
    )


def resolve_door_indicator_layout(
    context: DoorIndicatorContext,
    layer_groups: list[int] | tuple[int, ...],
    offset: Vec2 = Vec2(0.0, 0.0),
) -> DoorIndicatorLayout:
    groups = tuple(int(value) for value in layer_groups)
    if not groups:
        raise ValueError("door indicator layout requires at least one layer")
    g_max = max(groups) if groups else 1
    layers = len(groups)
    features = tuple(resolve_door_indicator_features(context, groups, offset))

    active_width = 90.0 * (g_max - 1) + 80.0
    active_height = 280.0 * (layers - 1) + 250.0
    physical_offset = Vec2(28.0 if g_max == 1 else 18.0, 17.25)
    base_interaction_center = context.group_center(groups) + physical_offset
    interaction_center = base_interaction_center + offset
    bounds = WorldBounds(
        interaction_center.x - active_width / 2.0,
        interaction_center.y - active_height / 2.0,
        interaction_center.x + active_width / 2.0,
        interaction_center.y + active_height / 2.0,
    )

    lamps = [feature for feature in features if feature.source_type == "indicator_lamp"]
    if not lamps:
        raise ValueError("door indicator layout has no lamp features")
    left_lamp = min(lamps, key=lambda feature: feature.center.x).center
    top_lamp = max(lamps, key=lambda feature: feature.center.y).center

    return DoorIndicatorLayout(
        context=context,
        layer_groups=groups,
        offset=offset,
        features=features,
        interaction_bounds=bounds,
        base_interaction_center=base_interaction_center,
        left_lamp_center=left_lamp,
        top_lamp_center=top_lamp,
    )


def door_enclosure_reference_offsets(
    frame_edges=None,
    *,
    frame_width: float,
    thickness: float,
    gap_w: float,
    gap_h: float,
) -> dict[str, float]:
    """Distance from each Door finished-face edge to its enclosure reference.

    Door gap always exists.  A surrounding enclosure-frame edge adds exactly
    ``FW + 2T`` on that side; missing frame edges do not.
    """
    frame_span = float(frame_width) + 2.0 * float(thickness)
    gap_w = float(gap_w)
    gap_h = float(gap_h)

    def present(name: str) -> bool:
        return True if frame_edges is None else bool(getattr(frame_edges, name, True))

    return {
        "left": gap_w + (frame_span if present("left") else 0.0),
        "right": gap_w + (frame_span if present("right") else 0.0),
        "top": gap_h + (frame_span if present("top") else 0.0),
        "bottom": gap_h + (frame_span if present("bottom") else 0.0),
    }


def door_enclosure_reference_guide(
    finished_guide,
    frame_edges=None,
    *,
    frame_width: float,
    thickness: float,
    gap_w: float,
    gap_h: float,
):
    """Return the real enclosure measuring rectangle for a Door finished face.

    Each side is expanded independently.  Gap always remains; ``FW + 2T`` is
    added only where that enclosure-frame edge physically exists.
    """
    offsets = door_enclosure_reference_offsets(
        frame_edges, frame_width=frame_width, thickness=thickness,
        gap_w=gap_w, gap_h=gap_h,
    )
    return RectGuide(
        Vec2(finished_guide.min_point.x - offsets["left"],
             finished_guide.min_point.y - offsets["bottom"]),
        Vec2(finished_guide.max_point.x + offsets["right"],
             finished_guide.max_point.y + offsets["top"]),
        "door_enclosure_reference",
    )


def measure_door_indicator_position(
    layout: DoorIndicatorLayout,
    context: DoorIndicatorContext,
    *,
    frame_width: float,
    thickness: float,
    use_box_distance: bool,
    frame_edges=None,
    gap_w: float = 3.5,
    gap_h: float = 3.5,
) -> DoorIndicatorPosition:
    offsets = door_enclosure_reference_offsets(
        frame_edges, frame_width=frame_width, thickness=thickness,
        gap_w=gap_w, gap_h=gap_h,
    ) if use_box_distance else {"left": 0.0, "top": 0.0}
    reference_x = context.left_fold - offsets["left"]
    reference_y = context.bottom_fold + context.finished_height + offsets["top"]
    target_x = layout.left_lamp_center.x
    target_y = layout.top_lamp_center.y
    return DoorIndicatorPosition(
        reference_x=reference_x,
        reference_y=reference_y,
        target_x=target_x,
        target_y=target_y,
        distance_x=target_x - reference_x,
        distance_y=reference_y - target_y,
    )


def door_indicator_offset_for_position(
    context: DoorIndicatorContext,
    layer_groups: list[int] | tuple[int, ...],
    *,
    x_distance: float,
    y_distance: float,
    frame_width: float,
    thickness: float,
    use_box_distance: bool,
    frame_edges=None,
    gap_w: float = 3.5,
    gap_h: float = 3.5,
) -> Vec2:
    base_layout = resolve_door_indicator_layout(context, layer_groups, Vec2(0.0, 0.0))
    base_position = measure_door_indicator_position(
        base_layout,
        context,
        frame_width=frame_width,
        thickness=thickness,
        use_box_distance=use_box_distance,
        frame_edges=frame_edges, gap_w=gap_w, gap_h=gap_h,
    )
    desired = Vec2(
        float(x_distance) - base_position.distance_x,
        base_position.distance_y - float(y_distance),
    )
    return base_layout.clamp_offset(desired)


def resolve_features_in_finished_face(
    width: float,
    height: float,
    features: Iterable[Feature],
) -> list[ResolvedFeature]:
    resolved: list[ResolvedFeature] = []
    for feature in features:
        center = _anchor_point(feature.anchor, float(width), float(height)) + feature.offset
        if isinstance(feature, CircleFeature):
            resolved.append(
                ResolvedCircle(
                    center=center,
                    radius=feature.diameter / 2.0,
                    layer=feature.layer,
                    add_centerline=feature.add_centerline,
                    source_type=feature.source_type,
                )
            )
        elif isinstance(feature, RectFeature):
            resolved.append(
                ResolvedRect(
                    center=center,
                    width=feature.width,
                    height=feature.height,
                    layer=feature.layer,
                    source_type=feature.source_type,
                    rotation_deg=_normalize_rotation(feature.rotation_deg),
                )
            )
        else:
            resolved.append(ResolvedProfile(
                points=tuple(center + _rotate_local_point(p, feature.rotation_deg) for p in feature.points),
                layer=feature.layer, source_type=feature.source_type,
            ))
    return resolved


def hit_test_resolved_features(
    point: Vec2,
    features: Iterable[ResolvedFeature],
    tolerance: float = 0.0,
) -> int | None:
    tolerance = max(0.0, float(tolerance))
    for index, feature in enumerate(features):
        if isinstance(feature, ResolvedCircle):
            dx = point.x - feature.center.x
            dy = point.y - feature.center.y
            radius = feature.radius + tolerance
            if dx * dx + dy * dy <= radius * radius:
                return index
        elif isinstance(feature, ResolvedRect):
            poly = ShapelyPolygon([(p.x, p.y) for p in feature.points])
            if poly.buffer(tolerance).covers(ShapelyPoint(point.x, point.y)):
                return index
        else:
            poly = ShapelyPolygon([(p.x, p.y) for p in feature.points])
            if poly.buffer(tolerance).covers(ShapelyPoint(point.x, point.y)):
                return index
    return None


def resolve_base_plate_mounting_holes(
    width: float,
    height: float,
    *,
    bend: float,
    edge_clearance: float = 15.0,
    diameter: float = 10.0,
) -> list[ResolvedCircle]:
    inset = float(bend) + float(edge_clearance)
    xs = (inset, float(width) - inset)
    ys = (inset, float(height) - inset)
    return [
        ResolvedCircle(
            center=Vec2(x, y),
            radius=float(diameter) / 2.0,
            layer="CUTTING",
            source_type="base_plate_mount",
        )
        for x in xs
        for y in ys
    ]
