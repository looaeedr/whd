# -*- coding: utf-8 -*-
"""Reference-edge editing, neighbor spacing, and round-hole fill helpers."""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable

try:
    from shapely.geometry import LineString as ShapelyLineString
except Exception:  # pragma: no cover
    ShapelyLineString = None

from .sheetmetal_geometry import Vec2
from .sheetmetal_feature_core import (
    Feature,
    CircleFeature,
    ProfileFeature,
    feature_finished_point,
)
from .sheetmetal_feature_surface import (
    FeatureSurface,
    RectGuide,
    _require_surface_geometry,
    _feature_footprint,
    feature_is_within_surface,
    move_feature_within_surface,
    move_feature_to_finished_point,
)

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
