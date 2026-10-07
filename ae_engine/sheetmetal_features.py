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


from .sheetmetal_feature_core import (
    FeatureAnchor,
    CircleFeature,
    RectFeature,
    ProfileFeature,
    ResolvedCircle,
    ResolvedRect,
    ResolvedProfile,
    ResolvedFeature,
    Feature,
    BOX_BODY_FACE_SEGMENTS,
    BoxBodyFaceContext,
    box_body_face_dimensions,
    box_body_face_contexts_from_strip,
    _resolve_box_body_face_feature,
    resolve_box_body_face_features,
    _normalize_rotation,
    _rotate_local_point,
    _anchor_point,
    feature_finished_point,
)
from .sheetmetal_feature_reference import (
    ReferenceAnchor,
    REFERENCE_ANCHOR_LABELS,
    REFERENCE_ANCHOR_BY_LABEL,
    ReferenceNeighbor,
    ReferenceDistances,
    feature_reference_anchor,
    feature_with_reference_anchor,
    feature_with_process,
    _feature_bounds,
    feature_reference_point,
    _surface_axis_edges,
    _reference_axis_edges,
    reference_edge_directions,
    find_reference_neighbor,
    reference_distances,
    move_feature_by_reference_distance,
    circle_center_distance_from_gap,
    circle_gap_from_center_distance,
    align_circle_to_neighbor,
    _round_pattern_pitch,
    _round_candidate,
    generate_round_fill,
    generate_round_refill,
)
from .sheetmetal_feature_surface import (
    FeatureSurface,
    _require_surface_geometry,
    feature_surface_from_outline,
    feature_surface_from_structural_result,
    feature_surface_from_rect,
    _feature_footprint,
    feature_is_within_surface,
    feature_is_strictly_within_surface,
    move_feature_within_surface,
    resolve_surface_features,
    RectGuide,
    DimensionGuide,
    FeaturePlacement,
    PlacementGuideSet,
    resolve_endcap_finished_face_guide,
    endcap_finished_feature_surface,
    choose_feature_anchor,
    placement_from_finished_point,
    reanchor_feature,
    move_feature_to_finished_point,
    feature_with_offset,
    build_feature_placement_guides,
)
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


DEFAULT_VAULT_ENDCAP_FEATURE_POLICY = VaultEndCapFeaturePolicy(
    hanging_hole_radius=3.2,
    hanging_hole_y_from_top_bend=6.0,
    square_hole_origin=Vec2(3.0, 18.0),
    square_hole_size=Vec2(4.0, 4.0),
    tail_bottom_hole_radius=2.5,
    tail_bottom_hole_y=5.0,
)


@dataclass(frozen=True)
class ReceivingEndCapFeaturePolicy:
    """Receiving (受電箱) 封頭/封尾特徵策略。

    依 T5 Provenance Trace 結果：
    - 左右吊掛孔、方孔與尾底圓孔皆為 Vault-only (DO_NOT_SHARE)。
    - Receiving 預設不具備上述固定特徵，避免在非金庫拓撲下破孔或錯位。
    """
    fixed_features_enabled: bool = False


RECEIVING_ENDCAP_FEATURE_POLICY = ReceivingEndCapFeaturePolicy()


def resolve_receiving_endcap_fixed_features(
    geometry: EndCapGeometry,
    *,
    relief_config: ReliefConfig | None = None,
    policy: ReceivingEndCapFeaturePolicy | None = None,
    is_tail: bool = False,
) -> tuple[ResolvedFeature, ...]:
    """Receiving 固定特徵解析器：預設回傳空 tuple，保證與 Vault 隔離。"""
    active_policy = policy or RECEIVING_ENDCAP_FEATURE_POLICY
    if not active_policy.fixed_features_enabled:
        return ()
    return ()


def resolve_endcap_fixed_features_for_model(
    geometry: EndCapGeometry,
    *,
    model_name: str | None = None,
    relief_config: ReliefConfig | None = None,
    is_tail: bool = False,
    feature_policy: VaultEndCapFeaturePolicy | ReceivingEndCapFeaturePolicy | None = None,
) -> tuple[ResolvedFeature, ...]:
    """根據箱體型態或明確 policy 解析封頭/尾固定特徵，杜絕盲目共用。"""
    if feature_policy is not None:
        if isinstance(feature_policy, ReceivingEndCapFeaturePolicy):
            return resolve_receiving_endcap_fixed_features(
                geometry, relief_config=relief_config, policy=feature_policy, is_tail=is_tail
            )
        if isinstance(feature_policy, VaultEndCapFeaturePolicy):
            return resolve_vault_endcap_fixed_features(
                geometry, relief_config=relief_config or ReliefConfig(), policy=feature_policy, is_tail=is_tail
            )
    name = str(model_name or "").strip()
    if name in {"受電箱", "RECEIVING"}:
        return resolve_receiving_endcap_fixed_features(
            geometry, relief_config=relief_config, is_tail=is_tail
        )
    return resolve_vault_endcap_fixed_features(
        geometry, relief_config=relief_config or ReliefConfig(), policy=DEFAULT_VAULT_ENDCAP_FEATURE_POLICY, is_tail=is_tail
    )



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
