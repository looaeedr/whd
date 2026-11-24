# -*- coding: utf-8 -*-
"""#3412: manual MARKING on one already-resolved physical sheet.

The complete authored stroke is manufacturing intent.  Dash gaps do not
remove the material/hole clearance obligation.  Only existing DrawingScene
process primitives are exported; this module never writes DXF or changes CUTTING.
"""
from __future__ import annotations

from collections.abc import Mapping
from math import atan2, cos, hypot, isfinite, radians, sin
from shapely.geometry import LineString, Point, Polygon

from .sheetmetal_feature_core import CircleFeature, FeatureAnchor, ProfileFeature
from .sheetmetal_geometry import Vec2
from .sheetmetal_drawing import (
    CirclePrimitive, DrawingScene, LinePrimitive, PolylinePrimitive,
    resolved_features_to_primitives,
)

MANUAL_MARK_SOURCE = "WHD_MANUAL_MARKING_V1"
MANUAL_ROUND_MARK_SOURCE = "WHD_MANUAL_ROUND_MARKING_V1"
_EPS = 1e-7

def require_first_sheet_manual_marking_spec(spec):
    """The #3412 release is ONLY the real Receiving LEFT physical BasePlate.

    A generic Vault/unknown BasePlate with the same part key is not this
    source.  This is an *additional* marking gate, never DXF certification.
    """
    from .cabinet_types.policy import canonical_family_name
    from .contracts import BasePlatePartSpec
    from .sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_LEFT
    if (not isinstance(spec, BasePlatePartSpec)
            or canonical_family_name(spec.model_name) != "受電箱"
            or spec.physical_id != "base_plate"
            or spec.receiving_bend_pattern != RECEIVING_BASE_PATTERN_LEFT
            or spec.corner_policy is not None
            or bool(spec.seam_positions)
            or spec.receiving_nfb_depth_pair_mm is not None):
        raise ValueError("MANUAL_MARKING_V1_UNSUPPORTED_SOURCE")


def require_first_sheet_manual_marking_render(part_key, render):
    """Require source-labelled *real* material topology and finite BEND spans.

    Identity is not established by a caller's 'base_plate' string.  The
    original registered LEFT BasePlate PartSpec must supply this metadata,
    three Y material segments, and two full-span finite real BENDs.
    """
    from .manufacturing_render_data import fold_guides_from_final_scene
    from .sheetmetal_part_adapters import RECEIVING_BASE_PATTERN_LEFT

    if part_key != "base_plate" or render is None:
        raise ValueError("MANUAL_MARKING_V1_UNSUPPORTED_SOURCE")
    meta = getattr(render, "metadata", None) or {}
    topology = getattr(render, "unfolded_topology", None)
    if (meta.get("stable_id") != "base_plate"
            or meta.get("receiving_bend_pattern") != RECEIVING_BASE_PATTERN_LEFT
            or getattr(topology, "piece_id", None) != "base_plate"
            or getattr(topology, "source", None) != "RECEIVING_BASE_BEND"):
        raise ValueError("MANUAL_MARKING_V1_UNSUPPORTED_SOURCE")
    xs = tuple(getattr(topology, "x_segments", ()) or ())
    ys = tuple(getattr(topology, "y_segments", ()) or ())
    if len(xs) != 1 or len(ys) != 3 or any(
        not isfinite(float(row.length)) or float(row.length) <= 0
        for row in xs + ys
    ):
        raise ValueError("MANUAL_MARKING_V1_UNSUPPORTED_SOURCE")
    material = getattr(render, "material", None)
    if material is None or getattr(material, "is_empty", True):
        raise ValueError("MANUAL_MARKING_V1_UNSUPPORTED_SOURCE")
    minx, miny, maxx, maxy = material.bounds
    if (abs(minx) > _EPS or abs(miny) > _EPS
            or abs((maxx - minx) - float(xs[0].length)) > 1e-6
            or abs((maxy - miny) - sum(float(row.length) for row in ys)) > 1e-6):
        raise ValueError("MANUAL_MARKING_V1_UNSUPPORTED_SOURCE")
    guides = fold_guides_from_final_scene(render.scene)
    stations = (float(ys[0].length), float(ys[0].length + ys[1].length))
    if (len(guides) != 2 or any(
        guide.axis != "y"
        or abs(guide.position - station) > 1e-6
        or abs(guide.span_start - minx) > 1e-6
        or abs(guide.span_end - maxx) > 1e-6
        for guide, station in zip(sorted(guides, key=lambda row: row.position), stations)
    )):
        raise ValueError("MANUAL_MARKING_V1_UNSUPPORTED_SOURCE")
    return render


def first_sheet_manual_marking_supported(part_key, render):
    """GUI capability projection, not an authorization or material builder."""
    try:
        require_first_sheet_manual_marking_render(part_key, render)
    except (ValueError, TypeError, AttributeError, OverflowError):
        return False
    return True


def _manual_marking_scene_primitives(scene):
    rows = tuple(getattr(scene, "primitives", ()) or ())
    return tuple(row for row in rows
                 if getattr(row, "semantic_id", None) == MANUAL_MARK_SOURCE
                 or getattr(row, "source_type", None) in (MANUAL_MARK_SOURCE, MANUAL_ROUND_MARK_SOURCE))


def verify_manual_marking_output(render):
    """Hard gate at the public DXF sink, independent of the editor/PartSpec.

    Validate complete authored strokes against the CURRENT scene CUTTING,
    including holes in dashed blank space.  Check exact real ink primitives:
    no dropped/reordered/stale segments and no unauthorised CustomFold export.
    """
    scene = getattr(render, "scene", None)
    marked = _manual_marking_scene_primitives(scene)
    metadata = dict(getattr(render, "metadata", None) or {})
    authored = tuple(metadata.get("manual_marking_v1_features") or ())
    if not marked and not authored:
        return
    part_id = metadata.get("stable_id")
    require_first_sheet_manual_marking_render(part_id, render)
    if not authored:
        raise ValueError("MANUAL_MARKING_V1_MISSING_AUTHORED_STROKE")
    if not all(is_manual_mark(f) for f in authored):
        raise ValueError("MANUAL_MARKING_V1_MISSING_AUTHORED_STROKE")
    validate_physical_manual_markings(part_id, render, authored)
    from .operator_manual_marking_groups import is_manual_group
    expected_rounds = tuple(_round_mark_primitive(f) for f in authored if is_manual_round_mark(f))
    actual_rounds = tuple(r for r in marked if isinstance(r, CirclePrimitive))
    if actual_rounds != expected_rounds:
        raise ValueError("ROUND_MARKING_SCENE_CHANGED")
    marked = tuple(r for r in marked if not isinstance(r, CirclePrimitive))
    expected = tuple((
        tuple(Vec2(point.x + mark.offset.x, point.y + mark.offset.y)
              for point in points) if is_manual_group(mark) else tuple(points),
        closed,
    ) for mark in authored if not is_manual_round_mark(mark) for layer, points, closed in mark.layered_profiles)
    actual = tuple((tuple(row.points), row.closed) for row in marked
                   if isinstance(row, PolylinePrimitive)
                   and row.semantic_id == MANUAL_MARK_SOURCE)
    if len(marked) != len(expected) or actual != expected:
        raise ValueError("MANUAL_MARKING_V1_SCENE_STROKES_CHANGED")



def is_manual_mark(feature):
    from .operator_manual_marking_groups import MANUAL_GROUP_SOURCE
    if is_manual_round_mark(feature):
        return True
    if isinstance(feature, Mapping):
        return feature.get("source_type") in (MANUAL_MARK_SOURCE, MANUAL_GROUP_SOURCE)
    return getattr(feature, "source_type", None) in (MANUAL_MARK_SOURCE, MANUAL_GROUP_SOURCE)


def _finite(raw, label, *, positive=False):
    if isinstance(raw, bool):
        raise ValueError(f"手動打標 {label} 必須是有限數字")
    try:
        value = float(raw)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"手動打標 {label} 必須是有限數字") from exc
    if not isfinite(value) or (positive and value <= 0):
        raise ValueError(f"手動打標 {label} 必須是正有限數字" if positive else
                         f"手動打標 {label} 必須是有限數字")
    return value


def _segments(a, b, pattern, dash, gap):
    length = hypot(b.x - a.x, b.y - a.y)
    if not isfinite(length) or length <= _EPS:
        raise ValueError("手動打標不可為零長度")
    if pattern == "solid":
        return ((a, b),)
    if pattern != "dashed":
        raise ValueError("手動打標線型只能為實線或虛線")
    dash = _finite(dash, "實段長度", positive=True)
    gap = _finite(gap, "留白長度", positive=True)
    if dash + gap < 0.01 or length / (dash + gap) > 10000:
        raise ValueError("手動打標分段數量超出限制")
    rows = []
    distance = 0.0
    while distance < length - _EPS:
        stop = min(length, distance + dash)
        rows.append((
            Vec2(a.x + (b.x - a.x) * distance / length,
                 a.y + (b.y - a.y) * distance / length),
            Vec2(a.x + (b.x - a.x) * stop / length,
                 a.y + (b.y - a.y) * stop / length),
        ))
        distance += dash + gap
    return tuple(rows)


def _source_pattern(feature):
    if (not isinstance(feature, ProfileFeature)
            or feature.layer != "MARKING"
            or feature.anchor is not FeatureAnchor.ABSOLUTE_FINISHED_FACE
            or feature.rotation_deg != 0 or feature.offset != Vec2(0.0, 0.0)
            or len(feature.points) != 2):
        raise ValueError("手動打標已存的來源形狀不合法")
    params = tuple(feature.source_params)
    if len(params) != 3 or tuple(key for key, _ in params) != ("pattern", "dash", "gap"):
        raise ValueError("手動打標已存線型來源不完整")
    pattern, dash, gap = (item[1] for item in params)
    if not isinstance(pattern, str) or pattern not in ("solid", "dashed"):
        raise ValueError("手動打標已存線型不合法")
    a, b = feature.points
    for point in (a, b):
        _finite(point.x, "端點 X")
        _finite(point.y, "端點 Y")
    expected = _segments(a, b, pattern, dash, gap)
    saved = tuple(feature.layered_profiles)
    if len(saved) != len(expected):
        raise ValueError("手動打標已存實段與來源不符")
    for (layer, points, closed), (start, stop) in zip(saved, expected):
        if layer != "MARKING" or closed is not False or len(points) != 2:
            raise ValueError("手動打標實段必須是真實開放 MARKING 線")
        if any(hypot(actual.x - canonical.x, actual.y - canonical.y) > _EPS
               for actual, canonical in zip(points, (start, stop))):
            raise ValueError("手動打標實段不可與原完整筆畫漂移")
    return pattern, LineString(((a.x, a.y), (b.x, b.y)))


def _real_material_and_blind_holes(render, features, surface, width, height):
    from .manufacturing_render_data import material_polygon_from_final_scene
    from .sheetmetal_feature_surface import resolve_surface_features

    scene = DrawingScene(list(render.scene.primitives))
    ordinary = tuple(feature for feature in features if not is_manual_mark(feature))
    if ordinary:
        resolved = resolve_surface_features(surface, ordinary, width, height)
        scene.extend(resolved_features_to_primitives(resolved))
    material = material_polygon_from_final_scene(scene)
    if any(is_manual_round_mark(f) for f in features):
        live = material_polygon_from_final_scene(render.scene) if ordinary else material
        if (not isinstance(live, Polygon) or not live.is_valid
                or not live.equals(render.material)):
            raise ValueError("ROUND_MARKING_MATERIAL_SOURCE_MISMATCH")
    if material is None or material.is_empty:
        raise ValueError("手動打標沒有有效的真實材料")
    blind = []
    for row in scene.primitives:
        if str(getattr(row, "layer", "")).upper() != "BLIND_HOLE":
            continue
        if isinstance(row, CirclePrimitive):
            blind.append(Point(row.center.x, row.center.y).buffer(row.radius, quad_segs=32))
        elif isinstance(row, PolylinePrimitive) and row.closed and len(row.points) >= 3:
            blind.append(Polygon([(p.x, p.y) for p in row.points]))
        elif isinstance(row, LinePrimitive):
            blind.append(LineString(((row.p1.x, row.p1.y), (row.p2.x, row.p2.y))))
    return material, tuple(blind), scene


def validate_physical_manual_markings(part_key, render, features, *,
                                      surface=None, width=None, height=None):
    """Reject stale strokes against ALL current CUTTING/holes, not just dash ink.

    No existing stroke is silently shortened, moved, dropped or hidden.  A
    stale mark keeps its saved Feature, but blocks that sheet's manufacturing.
    """
    from .sheetmetal_features import legacy_hole_to_feature

    if not isinstance(part_key, str) or not part_key or render is None:
        raise ValueError("手動打標缺少唯一物理板件來源")
    if features is None or isinstance(features, (str, bytes, Mapping)):
        raise ValueError("手動打標需要完整板件 Features")
    normalized = tuple(legacy_hole_to_feature(dict(f)) if isinstance(f, Mapping) else f
                       for f in features)
    marks = tuple(f for f in normalized if is_manual_mark(f))
    if not marks:
        return ()
    require_first_sheet_manual_marking_render(part_key, render)
    if not any(isinstance(p, LinePrimitive) and str(p.layer).upper() == "BEND"
               and hypot(p.p2.x-p.p1.x, p.p2.y-p.p1.y) > _EPS
               for p in getattr(render.scene, "primitives", ())):
        raise ValueError("手動打標需要原板件有效的有限 BEND 折線")
    return _validate_manual_strokes(
        render, normalized, marks, surface=surface, width=width, height=height,
        part_key=part_key,
    )


def _validate_manual_strokes(render, normalized, marks, *, part_key, surface, width=None, height=None):
    from .physical_sheet_features import physical_sheet_feature_context

    if surface is None:
        surface, width, height, _ = physical_sheet_feature_context(part_key, render)
    material, blind, scene = _real_material_and_blind_holes(
        render, normalized, surface, width, height,
    )
    from .operator_manual_marking_groups import is_manual_group, source_group

    def same_stroke_multiset(left, right):
        """Count actual strokes without depending on source/member order."""
        if len(left) != len(right):
            return False
        unmatched = list(right)
        for stroke in left:
            index = next((i for i, other in enumerate(unmatched)
                          if stroke.equals(other)), None)
            if index is None:
                return False
            unmatched.pop(index)
        return not unmatched

    seen = []
    rings = []
    for mark in marks:
        if is_manual_round_mark(mark):
            circle = _round_mark_primitive(mark)
            _validate_round_marking(scene, material, circle)
            if any(hypot(circle.center.x-r.center.x, circle.center.y-r.center.y) <= _EPS
                   and abs(circle.radius-r.radius) <= _EPS for r in rings):
                raise ValueError("手動打標不可完全重複同線型")
            rings.append(circle)
            continue
        if is_manual_group(mark):
            _kind, pattern, full_strokes = source_group(mark)
        else:
            pattern, full = _source_pattern(mark)
            full_strokes = (full,)
        # Each full arm remains hazardous even where its dashed ink is absent.
        for full in full_strokes:
            if not material.covers(full):
                raise ValueError("手動打標完整筆畫穿過切孔、留白或無材料區")
            if float(material.boundary.intersection(full).length) > _EPS:
                raise ValueError("手動打標不可沿 CUTTING 邊界")
            if any(full.intersects(hole) for hole in blind):
                raise ValueError("手動打標完整筆畫碰觸孔位（含虛線留白）")
        # The complete stroke is the gate. Independently audit actual ink
        # including dashed visible-phase segments before duplicate comparison.
        ink_strokes = []
        for layer, points, _ in mark.layered_profiles:
            translated = tuple(Vec2(pt.x + mark.offset.x, pt.y + mark.offset.y)
                               for pt in points) if is_manual_group(mark) else points
            segment = LineString(((translated[0].x, translated[0].y),
                                  (translated[1].x, translated[1].y)))
            if not material.covers(segment) or float(material.boundary.intersection(segment).length) > _EPS:
                raise ValueError("手動打標有實段落在無材料區")
            if any(segment.intersects(hole) for hole in blind):
                raise ValueError("手動打標實段碰觸孔位")
            ink_strokes.append(segment)
        for prior_pattern, prior_full, prior_ink, prior_is_group in seen:
            if prior_pattern != pattern:
                continue
            if is_manual_group(mark) and prior_is_group:
                # Mirroring a symmetric quad L changes source ordering
                # without changing physical ink. For dashed groups compare
                # actual visible segments too: different dash phases must
                # remain distinguishable even if their full arms coincide.
                repeated = (same_stroke_multiset(full_strokes, prior_full)
                            and same_stroke_multiset(ink_strokes, prior_ink))
            else:
                # Retain the existing original V1 line matching contract.
                repeated = (len(prior_full) == len(full_strokes)
                            and all(one.equals(two) for one, two in
                                    zip(prior_full, full_strokes)))
            if repeated:
                raise ValueError("手動打標不可完全重複同線型")
        seen.append((pattern, full_strokes, tuple(ink_strokes),
                     is_manual_group(mark)))
    return marks


def create_physical_manual_marking(part_key, context, existing_features, *,
                                   midpoint, length, angle_deg,
                                   pattern="solid", dash=10.0, gap=5.0):
    """Engine-only candidate for a real sheet; GUI supplies raw operator input."""
    from .physical_sheet_editor_context import PhysicalSheetEditorContext

    if not isinstance(context, PhysicalSheetEditorContext) or context.part_key != part_key:
        raise ValueError("手動打標物理板件身分不一致")
    require_first_sheet_manual_marking_render(part_key, context.render_data)
    candidate = _build_manual_straight_feature(midpoint, length, angle_deg, pattern, dash, gap)
    validate_physical_manual_markings(
        part_key, context.render_data, tuple(existing_features) + (candidate,),
        surface=context.feature_surface, width=context.width, height=context.height,
    )
    return candidate


def _build_manual_straight_feature(midpoint, length, angle_deg, pattern, dash, gap):
    if not isinstance(midpoint, Vec2):
        raise ValueError("手動打標中點必須是物理座標")
    mx, my = _finite(midpoint.x, "中點 X"), _finite(midpoint.y, "中點 Y")
    length = _finite(length, "長度", positive=True)
    angle_deg = _finite(angle_deg, "方向")
    if not isinstance(pattern, str) or pattern not in ("solid", "dashed"):
        raise ValueError("手動打標線型不合法")
    dash = _finite(dash, "實段長度", positive=True)
    gap = _finite(gap, "留白長度", positive=True)
    axis = radians(angle_deg)
    if not isfinite(axis):
        raise ValueError("手動打標方向不合法")
    dx, dy = cos(axis) * length / 2.0, sin(axis) * length / 2.0
    p1, p2 = Vec2(mx - dx, my - dy), Vec2(mx + dx, my + dy)
    segments = _segments(p1, p2, pattern, dash, gap)
    return ProfileFeature(
        points=(p1, p2), anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(0.0, 0.0), layer="MARKING", source_type=MANUAL_MARK_SOURCE,
        source_params=(("pattern", pattern), ("dash", dash), ("gap", gap)),
        layered_profiles=tuple(("MARKING", pair, False) for pair in segments),
    )

def is_manual_round_mark(feature):
    source = feature.get("source_type", feature.get("type")) if isinstance(feature, Mapping) else getattr(feature, "source_type", None)
    return source == MANUAL_ROUND_MARK_SOURCE


def _round_mark_primitive(mark):
    if (not isinstance(mark, CircleFeature) or mark.layer != "MARKING"
            or mark.anchor is not FeatureAnchor.ABSOLUTE_FINISHED_FACE
            or mark.rotation_deg != 0 or mark.add_centerline is not False
            or mark.source_params != ()):
        raise ValueError("ROUND_MARKING_SAVED_SOURCE_INVALID")
    x, y = _finite(mark.offset.x, "圓心 X"), _finite(mark.offset.y, "圓心 Y")
    radius = _finite(mark.diameter, "直徑", positive=True) / 2
    if radius <= _EPS or not all(isfinite(n) for n in (x-radius, x+radius, y-radius, y+radius)):
        raise ValueError("ROUND_MARKING_DIAMETER_INVALID")
    return CirclePrimitive(Vec2(x, y), radius, "MARKING", 211,
                           source_type=MANUAL_ROUND_MARK_SOURCE)


def create_physical_manual_round_marking(part_key, context, existing_features, *, centre, diameter):
    """Build a typed solid circle; validate current holes before any edit."""
    from .physical_sheet_editor_context import PhysicalSheetEditorContext
    if not isinstance(context, PhysicalSheetEditorContext) or context.part_key != part_key:
        raise ValueError("ROUND_MARKING_PHYSICAL_OWNER_MISMATCH")
    if not isinstance(centre, Vec2):
        raise ValueError("ROUND_MARKING_CENTRE_INVALID")
    mark = CircleFeature(
        _finite(diameter, "直徑", positive=True), FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        Vec2(_finite(centre.x, "圓心 X"), _finite(centre.y, "圓心 Y")), "MARKING",
        source_type=MANUAL_ROUND_MARK_SOURCE,
    )
    validate_physical_manual_markings(
        part_key, context.render_data, tuple(existing_features) + (mark,),
        surface=context.feature_surface, width=context.width, height=context.height,
    )
    return mark


def _validate_round_marking(scene, material, circle):
    x, y, radius = circle.center.x, circle.center.y, circle.radius
    point = Point(x, y)
    witness = Point(x + radius, y)

    def crosses_path(path):
        # Segment distance takes its interior minimum, maximum is attained
        # at an endpoint. Continuity then proves if r occurs on the segment.
        rows = tuple(path.coords)
        for a, b in zip(rows, rows[1:]):
            low = point.distance(LineString((a, b))) if a != b else hypot(a[0]-x, a[1]-y)
            high = max(hypot(a[0]-x, a[1]-y), hypot(b[0]-x, b[1]-y))
            if low - _EPS <= radius <= high + _EPS:
                return True
        return False

    error = "ROUND_MARKING_CIRCUMFERENCE_OUTSIDE_RETAINED_MATERIAL"
    if (not isinstance(material, Polygon) or not material.is_valid
            or not material.contains(witness)
            or any(crosses_path(ring) for ring in (material.exterior, *material.interiors))):
        raise ValueError(error)

    for row in scene.primitives:
        layer = str(row.layer).upper()
        if layer in ("CUTTING", "BLIND_HOLE") and isinstance(row, CirclePrimitive):
            # Test precise original circles too: Final Material's chord
            # approximation otherwise leaves a small false-valid fringe.
            d = hypot(row.center.x - x, row.center.y - y)
            h = row.radius
            if not isfinite(d) or not isfinite(h) or h <= 0.0:
                raise ValueError(error)
            if abs(d - radius) <= h + _EPS:
                raise ValueError(error)
        elif layer == "BLIND_HOLE":
            if isinstance(row, PolylinePrimitive) and row.closed and len(row.points) >= 3:
                hole = Polygon([(p.x,p.y) for p in row.points])
                if not hole.is_valid or hole.covers(witness) or crosses_path(hole.exterior):
                    raise ValueError(error)
            elif isinstance(row, LinePrimitive):
                blind = LineString(((row.p1.x, row.p1.y), (row.p2.x, row.p2.y)))
                if crosses_path(blind):
                    raise ValueError(error)
            else:
                raise ValueError(error)
