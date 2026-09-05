# -*- coding: utf-8 -*-
"""Pure drawing primitives for auxiliary sheet-metal output.

This module owns semantic CHECK/STOCK/DATUM primitives only.  It has no CAD,
GUI, or boolean-geometry dependency; callers serialize the returned data.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .sheetmetal_geometry import Vec2, EndCapGeometry, EndCapReliefDimensions
from .sheetmetal_features import DoorIndicatorPosition, ResolvedCircle, ResolvedRect, ResolvedProfile


def _fmt(value: float) -> str:
    val = round(float(value), 2)
    if val.is_integer():
        return str(int(val))
    text = f"{val:.2f}"
    return text[:-1] if text.endswith("0") else text


@dataclass(frozen=True)
class PolylinePrimitive:
    points: tuple[Vec2, ...]
    layer: str
    closed: bool = False
    color: int | None = None


@dataclass(frozen=True)
class LinePrimitive:
    p1: Vec2
    p2: Vec2
    layer: str
    color: int | None = None


@dataclass(frozen=True)
class CirclePrimitive:
    center: Vec2
    radius: float
    layer: str
    color: int | None = None
    source_type: str | None = None
    source_id: str | None = None


@dataclass(frozen=True)
class TextPrimitive:
    text: str
    insert: Vec2
    layer: str
    char_height: float
    attachment_point: int
    color: int | None = None


DrawingPrimitive = PolylinePrimitive | LinePrimitive | CirclePrimitive | TextPrimitive


@dataclass
class DrawingScene:
    primitives: list[DrawingPrimitive] = field(default_factory=list)

    def add(self, primitive: DrawingPrimitive) -> None:
        self.primitives.append(primitive)

    def extend(self, primitives) -> None:
        self.primitives.extend(primitives)

    def add_polyline(self, points, *, layer: str, closed: bool = False, color: int | None = None) -> None:
        if color is None:
            color = {"MARKING": 211, "BLIND_HOLE": 1, "DATUM": 6}.get(layer)
        self.add(PolylinePrimitive(
            tuple(p if isinstance(p, Vec2) else Vec2(float(p[0]), float(p[1])) for p in points),
            layer, bool(closed), color,
        ))

    def add_line(self, p1, p2, *, layer: str, color: int | None = None) -> None:
        if color is None:
            color = {"MARKING": 211, "BLIND_HOLE": 1, "DATUM": 6}.get(layer)
        v1 = p1 if isinstance(p1, Vec2) else Vec2(float(p1[0]), float(p1[1]))
        v2 = p2 if isinstance(p2, Vec2) else Vec2(float(p2[0]), float(p2[1]))
        self.add(LinePrimitive(v1, v2, layer, color))

    def add_circle(self, center, radius: float, *, layer: str, color: int | None = None,
                   source_type: str | None = None, source_id: str | None = None) -> None:
        if color is None:
            color = {"MARKING": 211, "BLIND_HOLE": 1, "DATUM": 6}.get(layer)
        c = center if isinstance(center, Vec2) else Vec2(float(center[0]), float(center[1]))
        self.add(CirclePrimitive(c, float(radius), layer, color, source_type, source_id))


def mirror_point_x(point: Vec2, min_x: float, max_x: float) -> Vec2:
    """Reflect one world-space point horizontally inside min_x..max_x."""
    return Vec2(float(min_x) + float(max_x) - float(point.x), float(point.y))


def drawing_scene_x_bounds(scene: DrawingScene) -> tuple[float, float]:
    """Return x bounds of positioned scene primitives for an export transform."""
    xs: list[float] = []
    for primitive in scene.primitives:
        if isinstance(primitive, PolylinePrimitive):
            xs.extend(float(point.x) for point in primitive.points)
        elif isinstance(primitive, LinePrimitive):
            xs.extend((float(primitive.p1.x), float(primitive.p2.x)))
        elif isinstance(primitive, CirclePrimitive):
            xs.extend((float(primitive.center.x) - primitive.radius, float(primitive.center.x) + primitive.radius))
        elif isinstance(primitive, TextPrimitive):
            xs.append(float(primitive.insert.x))
        else:
            raise TypeError(f"Unsupported drawing primitive: {type(primitive)!r}")
    if not xs:
        raise ValueError("DrawingScene has no positioned primitives")
    return min(xs), max(xs)


def mirror_drawing_scene_x(scene: DrawingScene, min_x: float, max_x: float) -> DrawingScene:
    """Return a horizontally mirrored copy of a DrawingScene."""
    mirrored = DrawingScene()
    for primitive in scene.primitives:
        if isinstance(primitive, PolylinePrimitive):
            mirrored.add(PolylinePrimitive(
                points=tuple(mirror_point_x(point, min_x, max_x) for point in primitive.points),
                layer=primitive.layer, closed=primitive.closed, color=primitive.color,
            ))
        elif isinstance(primitive, LinePrimitive):
            mirrored.add(LinePrimitive(
                p1=mirror_point_x(primitive.p1, min_x, max_x),
                p2=mirror_point_x(primitive.p2, min_x, max_x),
                layer=primitive.layer, color=primitive.color,
            ))
        elif isinstance(primitive, CirclePrimitive):
            mirrored.add(CirclePrimitive(
                center=mirror_point_x(primitive.center, min_x, max_x),
                radius=primitive.radius, layer=primitive.layer, color=primitive.color,
                source_type=primitive.source_type, source_id=primitive.source_id,
            ))
        elif isinstance(primitive, TextPrimitive):
            mirrored.add(TextPrimitive(
                text=primitive.text, insert=mirror_point_x(primitive.insert, min_x, max_x),
                layer=primitive.layer, char_height=primitive.char_height,
                attachment_point=primitive.attachment_point, color=primitive.color,
            ))
        else:
            raise TypeError(f"Unsupported drawing primitive: {type(primitive)!r}")
    return mirrored


def mirror_point_y(point: Vec2, height: float) -> Vec2:
    """Reflect one world-space point vertically inside a 0..height drawing extent."""
    return Vec2(float(point.x), float(height) - float(point.y))


def mirror_drawing_scene_y(scene: DrawingScene, height: float) -> DrawingScene:
    """Return a vertically mirrored copy of a DrawingScene (y' = height - y)."""
    mirrored = DrawingScene()
    for primitive in scene.primitives:
        if isinstance(primitive, PolylinePrimitive):
            mirrored.add(PolylinePrimitive(
                points=tuple(mirror_point_y(point, height) for point in primitive.points),
                layer=primitive.layer,
                closed=primitive.closed,
                color=primitive.color,
            ))
        elif isinstance(primitive, LinePrimitive):
            mirrored.add(LinePrimitive(
                p1=mirror_point_y(primitive.p1, height),
                p2=mirror_point_y(primitive.p2, height),
                layer=primitive.layer,
                color=primitive.color,
            ))
        elif isinstance(primitive, CirclePrimitive):
            mirrored.add(CirclePrimitive(
                center=mirror_point_y(primitive.center, height),
                radius=primitive.radius,
                layer=primitive.layer,
                color=primitive.color,
                source_type=primitive.source_type, source_id=primitive.source_id,
            ))
        elif isinstance(primitive, TextPrimitive):
            mirrored.add(TextPrimitive(
                text=primitive.text,
                insert=mirror_point_y(primitive.insert, height),
                layer=primitive.layer,
                char_height=primitive.char_height,
                attachment_point=primitive.attachment_point,
                color=primitive.color,
            ))
        else:
            raise TypeError(f"Unsupported drawing primitive: {type(primitive)!r}")
    return mirrored


@dataclass
class SceneData:
    scene: DrawingScene
    params: dict[str, object] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)



def structural_result_to_primitives(result) -> tuple[DrawingPrimitive, ...]:
    primitives: list[DrawingPrimitive] = [
        PolylinePrimitive(points=tuple(result.outline), layer="CUTTING", closed=True)
    ]
    primitives.extend(
        LinePrimitive(segment.p1, segment.p2, "BEND") for segment in result.bends
    )
    return tuple(primitives)


def resolved_features_to_primitives(features) -> tuple[DrawingPrimitive, ...]:
    primitives: list[DrawingPrimitive] = []
    for feature in features:
        if isinstance(feature, ResolvedCircle):
            color = {"MARKING": 211, "BLIND_HOLE": 1, "DATUM": 6}.get(feature.layer, 3)
            primitives.append(CirclePrimitive(feature.center, feature.radius, feature.layer, color))
            if feature.add_centerline:
                center_layer = "DATUM" if feature.layer == "BLIND_HOLE" else feature.layer
                center_color = 6 if center_layer == "DATUM" else color
                primitives.append(LinePrimitive(
                    Vec2(feature.center.x - feature.radius, feature.center.y),
                    Vec2(feature.center.x + feature.radius, feature.center.y),
                    center_layer,
                    center_color,
                ))
        elif isinstance(feature, ResolvedRect):
            color = {"MARKING": 211, "BLIND_HOLE": 1, "DATUM": 6}.get(feature.layer, 3)
            primitives.append(PolylinePrimitive(
                points=tuple(feature.points), layer=feature.layer, closed=True, color=color
            ))
        elif isinstance(feature, ResolvedProfile):
            if getattr(feature, "layered_profiles", ()):
                for layer, points, closed in feature.layered_profiles:
                    color = {"MARKING": 211, "BLIND_HOLE": 1, "DATUM": 6}.get(layer, 3)
                    primitives.append(PolylinePrimitive(points=tuple(points), layer=layer, closed=closed, color=color))
            else:
                color = {"MARKING": 211, "BLIND_HOLE": 1, "DATUM": 6}.get(feature.layer, 3)
                primitives.append(PolylinePrimitive(
                    points=tuple(feature.points), layer=feature.layer, closed=True, color=color
                ))
        else:
            raise TypeError(f"Unsupported resolved feature: {type(feature)!r}")
    return tuple(primitives)


def build_stock_outline(width: float, height: float) -> PolylinePrimitive:
    width = float(width)
    height = float(height)
    return PolylinePrimitive(
        points=(
            Vec2(0.0, 0.0), Vec2(width, 0.0), Vec2(width, height),
            Vec2(0.0, height), Vec2(0.0, 0.0),
        ),
        layer="STOCK",
    )


def build_base_plate_datum(
    *, w: float, h: float, shrink_left: float, shrink_bottom: float, bend: float
) -> PolylinePrimitive:
    left = -(float(shrink_left) - float(bend))
    bottom = -(float(shrink_bottom) - float(bend))
    w = float(w)
    h = float(h)
    return PolylinePrimitive(
        points=(
            Vec2(left, bottom), Vec2(left + w, bottom),
            Vec2(left + w, bottom + h), Vec2(left, bottom + h),
            Vec2(left, bottom),
        ),
        layer="DATUM",
        color=6,
    )


def _check_text(text: str, width: float, height: float) -> TextPrimitive:
    return TextPrimitive(
        text=text,
        insert=Vec2(float(width) / 2.0, float(height) + 50.0),
        layer="CHECK",
        char_height=30.0,
        attachment_point=8,
    )


def build_base_plate_check(
    *, total_width: float, total_height: float, bend: float,
    shrink_top: float, shrink_bottom: float, shrink_left: float, shrink_right: float,
) -> tuple[TextPrimitive, ...]:
    text = (
        f"W = {_fmt(total_width)} mm\n"
        f"H = {_fmt(total_height)} mm\n"
        "Part: Base Plate\n"
        f"折邊: {_fmt(bend)} mm\n"
        f"縮量: 上{_fmt(shrink_top)} 下{_fmt(shrink_bottom)} 左{_fmt(shrink_left)} 右{_fmt(shrink_right)} mm"
    )
    return (_check_text(text, total_width, total_height),)


def build_door_check(
    *, total_width: float, total_height: float, finished_w: float, finished_h: float,
    thickness: float, fold_left: float, fold_right: float, fold_top: float, fold_bottom: float,
    indicator_position: DoorIndicatorPosition | None = None,
) -> tuple[DrawingPrimitive, ...]:
    text = (
        f"W = {_fmt(total_width)} mm\n"
        f"H = {_fmt(total_height)} mm\n"
        "Part: Door\n"
        f"成品寬 = {_fmt(finished_w)} mm  成品高 = {_fmt(finished_h)} mm\n"
        f"折邊: 左{_fmt(fold_left)} 右{_fmt(fold_right)} 上{_fmt(fold_top)} 下{_fmt(fold_bottom)}\n"
        "截角:\n"
        f"  • 左下: {_fmt(fold_left-thickness)}*{_fmt(fold_bottom)} mm / 右下: {_fmt(fold_right-thickness)}*{_fmt(fold_bottom)} mm\n"
        f"  • 左上: {_fmt(fold_left-thickness)}*{_fmt(fold_top)} mm / 右上: {_fmt(fold_right-thickness)}*{_fmt(fold_top)} mm"
    )
    result: list[DrawingPrimitive] = [_check_text(text, total_width, total_height)]
    if indicator_position is not None:
        result.extend(build_door_indicator_check(indicator_position))
    return tuple(result)


def build_door_indicator_check(position: DoorIndicatorPosition) -> tuple[DrawingPrimitive, ...]:
    p = position
    return (
        LinePrimitive(Vec2(p.reference_x, p.target_y + 20.0), Vec2(p.target_x, p.target_y + 20.0), "CHECK", 2),
        TextPrimitive(f"X = {p.distance_x:.1f}", Vec2((p.reference_x+p.target_x)/2.0, p.target_y+35.0), "CHECK", 15.0, 5, 2),
        LinePrimitive(Vec2(p.target_x-20.0, p.reference_y), Vec2(p.target_x-20.0, p.target_y), "CHECK", 2),
        TextPrimitive(f"Y = {p.distance_y:.1f}", Vec2(p.target_x-35.0, (p.reference_y+p.target_y)/2.0), "CHECK", 15.0, 5, 2),
    )


def build_box_body_check(
    *, total_length: float, total_height: float,
    panel_width: float, panel_depth: float, thickness: float,
    fold_values: tuple[float, ...] | None = None,
    left_outer: float | None = None, left_inner: float | None = None,
    right_inner: float | None = None, right_outer: float | None = None,
    frame_width: float | None = None,
) -> tuple[TextPrimitive, ...]:
    if fold_values is None:
        if None in (left_outer, left_inner, right_inner, right_outer, frame_width):
            raise ValueError("fold_values or all box-body fold inputs are required")
        fold_values = (
            abs(float(left_outer)), float(left_inner), float(frame_width),
            float(panel_depth) - 2.0 * float(thickness),
            float(panel_width) - 2.0 * float(thickness),
            float(panel_depth) - 2.0 * float(thickness),
            float(frame_width), float(right_inner), abs(float(right_outer)),
        )
    folds = " ".join(_fmt(v) for v in fold_values)
    text = (
        f"W = {_fmt(total_length)} mm\n"
        f"H = {_fmt(total_height)} mm\n"
        "Part: Box Body (Z)\n"
        f"折彎尺寸: {_fmt(panel_width - 2*thickness)}*{_fmt(total_height)} / {_fmt(panel_depth - 2*thickness)}*{_fmt(total_height)}\n"
        f"折彎: {folds}"
    )
    return (_check_text(text, total_length, total_height),)


def build_indicator_box_check(
    width: float, height: float, *, group_count: int, fold: float
) -> tuple[TextPrimitive, ...]:
    text = (
        f"W = {_fmt(width)} mm\n"
        f"H = {_fmt(height)} mm\n"
        f"Part: Indicator Box ({int(group_count)} groups)\n"
        f"折邊: 上下左右各折 {_fmt(fold)} mm"
    )
    return (_check_text(text, width, height),)


def _relief_strings(relief: EndCapReliefDimensions) -> tuple[str, str, str]:
    if relief.bottom_left == relief.bottom_right:
        bottom = f"下方截角: {_fmt(relief.bottom_left)}*{_fmt(relief.bottom_height)}"
    else:
        bottom = (
            f"下方截角: 左{_fmt(relief.bottom_left)}*{_fmt(relief.bottom_height)} / "
            f"右{_fmt(relief.bottom_right)}*{_fmt(relief.bottom_height)}"
        )
    if relief.top_primary_left == relief.top_primary_right:
        primary = f"上方大截角: {_fmt(relief.top_primary_left)}*{_fmt(relief.top_primary_height)}"
    else:
        primary = (
            f"上方大截角: 左{_fmt(relief.top_primary_left)}*{_fmt(relief.top_primary_height)} / "
            f"右{_fmt(relief.top_primary_right)}*{_fmt(relief.top_primary_height)}"
        )
    if (
        relief.top_secondary_left == relief.top_secondary_right
        and relief.top_secondary_depth_left == relief.top_secondary_depth_right
    ):
        secondary = f"二級截角: {_fmt(relief.top_secondary_left)}*{_fmt(relief.top_secondary_depth_left)}"
    else:
        secondary = (
            f"二級截角: 左{_fmt(relief.top_secondary_left)}*{_fmt(relief.top_secondary_depth_left)} / "
            f"右{_fmt(relief.top_secondary_right)}*{_fmt(relief.top_secondary_depth_right)}"
        )
    return primary, secondary, bottom


def build_endcap_check(
    *, geometry: EndCapGeometry, relief: EndCapReliefDimensions,
    finished_width: float, finished_depth: float, part_label: str,
) -> tuple[TextPrimitive, ...]:
    primary, secondary, bottom = _relief_strings(relief)
    text = (
        f"W = {_fmt(geometry.total_width)} mm\n"
        f"H = {_fmt(geometry.total_depth)} mm\n"
        f"Part: {part_label}\n"
        f"{primary}\n{secondary}\n{bottom}\n"
        f"折彎尺寸: {_fmt(finished_width - 4*geometry.thickness)}*{_fmt(finished_depth - 3*geometry.thickness)}\n"
        f"折彎(寬): {_fmt(abs(geometry.left_fold))} {_fmt(finished_width - 4*geometry.thickness)} {_fmt(abs(geometry.right_fold))}\n"
        f"折彎(深): {_fmt(geometry.top_first_fold)} {_fmt(geometry.fw)} {_fmt(finished_depth - 3*geometry.thickness)} {_fmt(geometry.bottom_fold)}"
    )
    return (_check_text(text, geometry.total_width, geometry.total_depth),)
