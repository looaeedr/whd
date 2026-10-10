# -*- coding: utf-8 -*-
"""Deterministic annotation-only layout/collision resolution.

This module is downstream of AnnotationPlan.  It may move annotation
primitives, but it never owns or mutates manufacturing CUTTING/BEND/material.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

from .sheetmetal_drawing import CirclePrimitive, LinePrimitive, PolylinePrimitive, TextPrimitive
from .sheetmetal_geometry import Vec2


@dataclass(frozen=True)
class AnnotationRegion:
    min_x: float
    min_y: float
    max_x: float
    max_y: float
    kind: str = "RESERVED"

    def __post_init__(self):
        if float(self.max_x) < float(self.min_x) or float(self.max_y) < float(self.min_y):
            raise ValueError("invalid annotation region bounds")

    def contains_point(self, point: Vec2) -> bool:
        return (
            float(self.min_x) <= float(point.x) <= float(self.max_x)
            and float(self.min_y) <= float(point.y) <= float(self.max_y)
        )

    def intersects(self, other: "AnnotationRegion") -> bool:
        return not (
            float(self.max_x) < float(other.min_x)
            or float(other.max_x) < float(self.min_x)
            or float(self.max_y) < float(other.min_y)
            or float(other.max_y) < float(self.min_y)
        )


@dataclass(frozen=True)
class AnnotationCollision:
    primitive_index: int
    category: str
    detail: str


@dataclass(frozen=True)
class AnnotationLayoutResult:
    primitives: tuple[object, ...]
    diagnostics: tuple[str, ...] = ()
    unresolved_collisions: tuple[AnnotationCollision, ...] = ()


def _text_region(text: TextPrimitive) -> AnnotationRegion:
    # Deterministic engineering-text approximation.  This is layout geometry,
    # not manufacturing geometry.  Attachment 5 is center/center in current
    # annotation planner; other attachments use insertion as lower-left.
    height = max(float(text.char_height), 1e-9)
    width = max(height * 0.6 * max(len(str(text.text)), 1), height * 0.6)
    x = float(text.insert.x)
    y = float(text.insert.y)
    if int(text.attachment_point) == 5:
        return AnnotationRegion(
            x - width / 2.0,
            y - height / 2.0,
            x + width / 2.0,
            y + height / 2.0,
            "ANNOTATION_TEXT",
        )
    return AnnotationRegion(x, y, x + width, y + height, "ANNOTATION_TEXT")


def _collides(text: TextPrimitive, regions: tuple[AnnotationRegion, ...]) -> bool:
    box = _text_region(text)
    return any(box.intersects(region) for region in regions)


def _line_region(p1: Vec2, p2: Vec2, padding: float, kind: str) -> AnnotationRegion:
    pad = max(float(padding), 0.0)
    return AnnotationRegion(
        min(float(p1.x), float(p2.x)) - pad,
        min(float(p1.y), float(p2.y)) - pad,
        max(float(p1.x), float(p2.x)) + pad,
        max(float(p1.y), float(p2.y)) + pad,
        kind,
    )


def _polyline_regions(primitive: PolylinePrimitive, padding: float):
    points = tuple(primitive.points)
    if len(points) < 2:
        return ()
    pairs = list(zip(points, points[1:]))
    if bool(primitive.closed) and points[-1] != points[0]:
        pairs.append((points[-1], points[0]))
    return tuple(
        _line_region(a, b, padding, str(primitive.layer).upper())
        for a, b in pairs
    )


def _manufacturing_obstacle_regions(scene, *, clearance: float):
    if scene is None:
        return ()
    rows = []
    for primitive in tuple(getattr(scene, "primitives", ()) or ()):
        layer = str(getattr(primitive, "layer", "") or "").upper()
        if isinstance(primitive, LinePrimitive) and layer in {"CUTTING", "BEND"}:
            rows.append(_line_region(
                primitive.p1, primitive.p2, clearance, layer
            ))
        elif isinstance(primitive, PolylinePrimitive) and layer == "CUTTING":
            rows.extend(_polyline_regions(primitive, clearance))
        elif isinstance(primitive, CirclePrimitive) and layer == "CUTTING":
            pad = max(float(clearance), 0.0)
            r = float(primitive.radius) + pad
            rows.append(AnnotationRegion(
                float(primitive.center.x) - r,
                float(primitive.center.y) - r,
                float(primitive.center.x) + r,
                float(primitive.center.y) + r,
                "HOLE",
            ))
    return tuple(rows)


def _dimension_line_orientation(line: LinePrimitive, tolerance: float = 1e-9) -> str | None:
    dx = abs(float(line.p2.x) - float(line.p1.x))
    dy = abs(float(line.p2.y) - float(line.p1.y))
    if dy <= tolerance and dx > tolerance:
        return "x"
    if dx <= tolerance and dy > tolerance:
        return "y"
    return None


def _own_dimension_line_index(primitives, text: TextPrimitive, axis: str) -> int | None:
    candidates = []
    for index, primitive in enumerate(tuple(primitives)):
        if not isinstance(primitive, LinePrimitive):
            continue
        if str(primitive.layer).upper() != "DIMENSION":
            continue
        if _dimension_line_orientation(primitive) != axis:
            continue
        mx = (float(primitive.p1.x) + float(primitive.p2.x)) / 2.0
        my = (float(primitive.p1.y) + float(primitive.p2.y)) / 2.0
        if axis == "x":
            normal = abs(float(text.insert.y) - my)
            along = abs(float(text.insert.x) - mx)
        else:
            normal = abs(float(text.insert.x) - mx)
            along = abs(float(text.insert.y) - my)
        candidates.append((normal, along, index))
    if not candidates:
        return None
    candidates.sort()
    return int(candidates[0][2])


def _annotation_dimension_line_regions(
    primitives,
    *,
    own_line_index: int | None,
    clearance: float,
):
    rows = []
    for index, primitive in enumerate(tuple(primitives)):
        if index == own_line_index:
            continue
        if not isinstance(primitive, LinePrimitive):
            continue
        if str(primitive.layer).upper() != "DIMENSION":
            continue
        rows.append(_line_region(
            primitive.p1,
            primitive.p2,
            max(float(clearance), 0.0),
            "DIMENSION",
        ))
    return tuple(rows)


def _annotation_text_regions(primitives, *, exclude_index: int):
    rows = []
    for index, primitive in enumerate(tuple(primitives)):
        if index == int(exclude_index):
            continue
        if isinstance(primitive, TextPrimitive):
            rows.append(_text_region(primitive))
    return tuple(rows)


def _callout_specs(plan):
    rows = []
    for item in tuple(getattr(plan, "feature_callouts", ()) or ()):
        identifier = str(getattr(item, "source_id", "") or getattr(item, "source_type", ""))
        rows.append((str(getattr(item, "semantic_id", "") or ""), "FEATURE", identifier, getattr(item, "anchor")))
    for item in tuple(getattr(plan, "corner_callouts", ()) or ()):
        rows.append((str(getattr(item, "semantic_id", "") or ""), "CORNER", str(getattr(item, "corner", "")), getattr(item, "anchor")))
    for item in tuple(getattr(plan, "radius_callouts", ()) or ()):
        rows.append((str(getattr(item, "semantic_id", "") or ""), "RADIUS", str(getattr(item, "semantic_id", "")), getattr(item, "anchor")))
    return tuple(rows)


def _callout_for_text(plan, primitive: TextPrimitive):
    semantic_id = str(getattr(primitive, "semantic_id", "") or "")
    if not semantic_id:
        return None
    matches = [item for item in _callout_specs(plan) if item[0] == semantic_id]
    if len(matches) != 1:
        return None
    _semantic_id, kind, identifier, anchor = matches[0]
    return kind, identifier, anchor


def _callout_candidate_offsets(step: float, max_steps: int):
    yield (0.0, 0.0)
    for index in range(1, int(max_steps) + 1):
        amount = float(step) * index
        for dx, dy in (
            (amount, 0.0), (-amount, 0.0),
            (0.0, amount), (0.0, -amount),
            (amount, amount), (amount, -amount),
            (-amount, amount), (-amount, -amount),
        ):
            yield (dx, dy)


def _candidate_callout_regions(primitives, *, exclude_index: int, reserved_and_manufacturing, clearance: float):
    return (
        tuple(reserved_and_manufacturing)
        + _annotation_text_regions(primitives, exclude_index=exclude_index)
        + _annotation_dimension_line_regions(
            primitives, own_line_index=None, clearance=float(clearance)
        )
    )


def _candidate_leader_is_clear(anchor: Vec2, target: Vec2, regions, *, clearance: float) -> bool:
    leader = _line_region(anchor, target, max(float(clearance), 0.0), "LEADER")
    for region in regions:
        if region.contains_point(anchor):
            continue
        if leader.intersects(region):
            return False
    return True


def _candidate_offsets(step: float, max_steps: int):
    yield 0.0
    for index in range(1, int(max_steps) + 1):
        amount = float(step) * index
        yield amount
        yield -amount


def _dimension_axis_for_text(plan, primitive: TextPrimitive) -> str | None:
    semantic_id = str(getattr(primitive, "semantic_id", "") or "")
    if not semantic_id:
        return None
    matches = [
        dim for dim in getattr(plan, "overall_dimensions", ())
        if str(getattr(dim, "semantic_id", "") or "") == semantic_id
    ]
    if len(matches) != 1:
        return None
    return str(matches[0].axis).lower()


def resolve_annotation_collisions(
    plan,
    *,
    reserved_regions=(),
    manufacturing_scene=None,
    clearance: float = 1.0,
    step: float = 5.0,
    max_steps: int = 40,
    strict: bool = False,
) -> AnnotationLayoutResult:
    """Resolve annotation collisions without moving manufacturing geometry."""
    regions = (
        tuple(reserved_regions or ())
        + _manufacturing_obstacle_regions(
            manufacturing_scene,
            clearance=float(clearance),
        )
    )
    primitives = list(tuple(getattr(plan, "primitives", ()) or ()))
    unresolved = []

    for index, primitive in enumerate(tuple(primitives)):
        if not isinstance(primitive, TextPrimitive):
            continue

        layer = str(primitive.layer).upper()
        if layer == "TEXT":
            callout = _callout_for_text(plan, primitive)
            if callout is None:
                continue
            kind, identifier, anchor = callout
            callout_regions = _candidate_callout_regions(
                primitives,
                exclude_index=index,
                reserved_and_manufacturing=regions,
                clearance=float(clearance),
            )
            if not _collides(primitive, callout_regions):
                continue

            moved = None
            for dx, dy in _callout_candidate_offsets(float(step), int(max_steps)):
                if dx == 0.0 and dy == 0.0:
                    continue
                candidate = replace(
                    primitive,
                    insert=Vec2(
                        float(primitive.insert.x) + dx,
                        float(primitive.insert.y) + dy,
                    ),
                )
                candidate_regions = _candidate_callout_regions(
                    primitives,
                    exclude_index=index,
                    reserved_and_manufacturing=regions,
                    clearance=float(clearance),
                )
                if _collides(candidate, candidate_regions):
                    continue
                if not _candidate_leader_is_clear(
                    anchor, candidate.insert, candidate_regions, clearance=float(clearance)
                ):
                    continue
                moved = candidate
                break

            if moved is None:
                unresolved.append(AnnotationCollision(
                    index,
                    "UNRESOLVED_LEADER",
                    f"no legal leader position for {kind.lower()} {identifier}: {primitive.text}",
                ))
            else:
                primitives[index] = moved
                primitives.append(LinePrimitive(
                    Vec2(float(anchor.x), float(anchor.y)),
                    moved.insert,
                    "TEXT",
                ))
            continue

        if layer != "DIMENSION":
            continue
        axis = _dimension_axis_for_text(plan, primitive)
        if axis not in {"x", "y"}:
            if _collides(
                primitive,
                regions + _annotation_text_regions(primitives, exclude_index=index),
            ):
                unresolved.append(AnnotationCollision(
                    index,
                    "UNRESOLVED_DIMENSION_AXIS",
                    f"cannot resolve dimension axis for text: {primitive.text}",
                ))
            continue

        own_line_index = _own_dimension_line_index(primitives, primitive, axis)
        annotation_line_regions = _annotation_dimension_line_regions(
            primitives,
            own_line_index=own_line_index,
            clearance=float(clearance),
        )
        active_regions = (
            regions
            + _annotation_text_regions(primitives, exclude_index=index)
            + annotation_line_regions
        )
        if not _collides(primitive, active_regions):
            continue

        moved = None
        for offset in _candidate_offsets(float(step), int(max_steps)):
            if offset == 0:
                continue
            if axis == "x":
                candidate = replace(
                    primitive,
                    insert=Vec2(float(primitive.insert.x) + offset, float(primitive.insert.y)),
                )
            else:
                candidate = replace(
                    primitive,
                    insert=Vec2(float(primitive.insert.x), float(primitive.insert.y) + offset),
                )
            candidate_regions = (
                regions
                + _annotation_text_regions(primitives, exclude_index=index)
                + annotation_line_regions
            )
            if not _collides(candidate, candidate_regions):
                moved = candidate
                break

        if moved is None:
            unresolved.append(AnnotationCollision(
                index,
                "UNRESOLVED_COLLISION",
                f"no legal axis-constrained position for dimension text: {primitive.text}",
            ))
        else:
            primitives[index] = moved

    result = AnnotationLayoutResult(
        primitives=tuple(primitives),
        diagnostics=tuple(c.detail for c in unresolved),
        unresolved_collisions=tuple(unresolved),
    )
    if strict and result.unresolved_collisions:
        raise ValueError(
            "unresolved annotation collisions: "
            + "; ".join(c.detail for c in result.unresolved_collisions)
        )
    return result


def _quantity_text_box(text):
    """Conservative MTEXT footprint, including multiline/attachment semantics."""
    from shapely.geometry import box
    lines = str(text.text).replace("\\P", "\n").splitlines() or [""]
    height = float(text.char_height)
    width = max(max(map(len, lines)), 1) * height * 0.8
    total_height = height * (1 + 1.5 * (len(lines) - 1))
    attachment = int(text.attachment_point)
    column = (attachment - 1) % 3
    row = (attachment - 1) // 3
    x = float(text.insert.x) - (0, width / 2, width)[column]
    y = float(text.insert.y) - (total_height, total_height / 2, 0)[row]
    return box(x, y, x + width, y + total_height)


def _quantity_obstacles(primitives, clearance):
    """Read final 2D primitives solely as annotation obstacles."""
    from shapely.geometry import LineString, Point
    rows = []
    for primitive in primitives:
        if str(primitive.layer).upper() == "STOCK":
            continue
        if isinstance(primitive, TextPrimitive):
            obstacle = _quantity_text_box(primitive)
        elif isinstance(primitive, CirclePrimitive):
            obstacle = Point(primitive.center.x, primitive.center.y).buffer(
                primitive.radius, quad_segs=32).boundary
        elif isinstance(primitive, LinePrimitive):
            obstacle = LineString(((primitive.p1.x, primitive.p1.y),
                                   (primitive.p2.x, primitive.p2.y)))
        elif isinstance(primitive, PolylinePrimitive):
            points = [(p.x, p.y) for p in primitive.points]
            if primitive.closed and points and points[-1] != points[0]:
                points.append(points[0])
            if len(points) < 2:
                raise ValueError("quantity CHECK cannot inspect degenerate polyline")
            obstacle = LineString(points)
        else:
            raise TypeError(f"unsupported quantity CHECK obstacle: {type(primitive).__name__}")
        rows.append(obstacle.buffer(clearance))
    return tuple(rows)


def _quantity_candidates(material, obstacles, width, height, clearance):
    """Center first; deterministic boundary-derived and bounded grid fallback."""
    minx, miny, maxx, maxy = map(float, material.bounds)
    center = ((minx + maxx) / 2, (miny + maxy) / 2)
    anchors = [center, (material.centroid.x, material.centroid.y)]
    point = material.representative_point()
    anchors.append((point.x, point.y))
    xs, ys = {p[0] for p in anchors}, {p[1] for p in anchors}
    boxes = [material.bounds] + [obstacle.bounds for obstacle in obstacles]
    for x1, y1, x2, y2 in boxes:
        for x in (x1, x2):
            xs.update((x - width / 2 - clearance, x + width / 2 + clearance))
        for y in (y1, y2):
            ys.update((y - height / 2 - clearance, y + height / 2 + clearance))
    # This is annotation search only; it never creates manufacturing coordinates.
    for i in range(1, 32):
        xs.add(minx + (maxx - minx) * i / 32)
        ys.add(miny + (maxy - miny) * i / 32)
    candidates = {(x, y) for x in xs for y in ys
                  if minx < x < maxx and miny < y < maxy}
    candidates.update(anchors)
    return sorted(candidates, key=lambda p:
                  ((p[0]-center[0])**2 + (p[1]-center[1])**2, p[0], p[1]))


def annotate_quantity_render_data(
    render_data, quantity, *, char_height=30.0, minimum_char_height=3.0,
    clearance=1.0,
):
    """Place exactly one CHECK Q after grouping, retaining all machining objects."""
    import math
    import re
    from shapely.prepared import prep
    from .sheetmetal_drawing import DrawingScene
    if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        raise ValueError("quantity CHECK requires a positive integer")
    if (not all(math.isfinite(float(v)) for v in
                (char_height, minimum_char_height, clearance))
            or minimum_char_height <= 0 or char_height < minimum_char_height
            or clearance <= 0):
        raise ValueError("invalid readable quantity CHECK layout settings")
    material = render_data.material
    if material is None or material.is_empty or not material.is_valid:
        raise ValueError("quantity CHECK requires valid final 2D material")
    # Replace only old CHECK quantity labels; manufacturing text is immutable.
    primitives = tuple(p for p in render_data.scene.primitives
        if not (isinstance(p, TextPrimitive) and str(p.layer).upper() == "CHECK"
                and re.fullmatch(r"[Qq][0-9]+", str(p.text).strip())))
    obstacles = _quantity_obstacles(primitives, float(clearance))
    prepared = prep(material)
    heights = []
    height = float(char_height)
    while height > minimum_char_height:
        heights.append(height)
        height /= 2
    heights.append(float(minimum_char_height))
    for height in heights:
        text = TextPrimitive(f"Q{quantity}", Vec2(0, 0), "CHECK", height, 5, 2,
                             "manufacturing_quantity")
        region = _quantity_text_box(text)
        width, text_height = region.bounds[2]-region.bounds[0], region.bounds[3]-region.bounds[1]
        for x, y in _quantity_candidates(material, obstacles, width, text_height, clearance):
            candidate = replace(text, insert=Vec2(x, y))
            footprint = _quantity_text_box(candidate)
            if not prepared.covers(footprint.buffer(clearance)):
                continue
            if any(footprint.intersects(obstacle) for obstacle in obstacles):
                continue
            return replace(render_data, scene=DrawingScene([*primitives, candidate]))
    raise ValueError(f"quantity CHECK Q{quantity}: no legal readable position inside final material")
