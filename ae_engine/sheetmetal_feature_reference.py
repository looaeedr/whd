# -*- coding: utf-8 -*-
# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Reference-edge editing, neighbor spacing, and round-hole fill helpers."""
from __future__ import annotations
import math

from dataclasses import dataclass, replace
from enum import Enum
from typing import Iterable

try:
    from shapely.geometry import LineString as ShapelyLineString, Point as ShapelyPoint
except Exception:  # pragma: no cover
    ShapelyLineString = None
    ShapelyPoint = None

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
    # Missing historic anchor means CENTER. An explicitly saved invalid
    # anchor must not silently relocate the reference point for hole edits.
    if "reference_anchor" not in params:
        return ReferenceAnchor.CENTER
    raw = params["reference_anchor"]
    if not isinstance(raw, str):
        raise ValueError("invalid feature reference_anchor")
    try:
        return ReferenceAnchor(raw)
    except ValueError as exc:
        raise ValueError("invalid feature reference_anchor") from exc


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
    # A cutout or disconnected contour can create multiple segments on a
    # single axis. Only the segment *containing the seed* defines the local
    # refill span; the union bounds would bridge empty material.
    center = ShapelyPoint(float(point.x), float(point.y))

    def local_component(geometry):
        def lines(item):
            if item.geom_type == "LineString" and item.length > 0:
                yield item
            else:
                for child in getattr(item, "geoms", ()):
                    yield from lines(child)
        candidates = [line for line in lines(geometry) if line.distance(center) <= 1e-7]
        if candidates:
            return max(candidates, key=lambda line: float(line.length)).bounds
        return geometry.bounds

    hminx, _, hmaxx, _ = local_component(hi)
    _, vminy, _, vmaxy = local_component(vi)
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
    # This is a public query as well as the downstream display helper. A
    # boolean/float GUI selection must not alias another physical hole.
    if type(current_index) is not int:
        raise ValueError("reference feature index must be an integer")
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
    # A negative GUI selection is not a request for the last physical hole.
    if type(current_index) is not int or not 0 <= current_index < len(items):
        raise ValueError("reference feature index is out of range")
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
    # A hole reference move is actual geometric positioning, not a Tk-only
    # display field: reject invalid values before reading or moving features.
    if type(current_index) is not int:
        raise ValueError("reference feature index must be an integer")
    if isinstance(value, bool):
        raise ValueError("reference distance must be finite and not boolean")
    try:
        measured = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("reference distance must be finite") from exc
    if not math.isfinite(measured):
        raise ValueError("reference distance must be finite")
    items = list(features)
    # Tk uses -1 for "no selection"; Python would otherwise select the last
    # physical hole, while neighboring UI paths already reject invalid IDs.
    if not 0 <= current_index < len(items):
        raise ValueError("reference feature index is out of range")
    feature = items[current_index]
    current_ref = feature_reference_point(feature, anchor, width, height)
    distances = reference_distances(surface, items, current_index, anchor, width, height, reference_guide)
    axis = axis.lower(); mode = mode.lower(); value = measured
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
    if isinstance(value, bool):
        raise ValueError("round-hole pitch must be a finite number")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("round-hole pitch must be a finite number") from exc
    if not math.isfinite(value):
        raise ValueError("round-hole pitch must be finite")
    if driver == "center":
        pitch = value
    elif driver == "gap":
        pitch = circle_center_distance_from_gap(value, feature.diameter, feature.diameter)
    else:
        raise ValueError("driver must be center or gap")
    if not math.isfinite(pitch) or pitch <= 0:
        raise ValueError("round-hole pitch must be finite and positive")
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
    minx, maxx, miny, maxy = _surface_axis_edges(surface, center)
    r = float(seed.diameter) / 2.0

    horizontal = direction in {"left", "right", "both_horizontal"}
    lo = (minx + r) if horizontal else (miny + r)
    hi = (maxx - r) if horizontal else (maxy - r)
    if hi < lo:
        return ()
    span = hi - lo
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
