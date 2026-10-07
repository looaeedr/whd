# -*- coding: utf-8 -*-
"""Box-body seam, base-plate relief, and physical-piece feature projection."""
from __future__ import annotations

from phase6_box_body_structure import (
    BoxBodyStructureType,
    normalize_box_body_structure_state,
)
from .sheetmetal_geometry_core import BendLine, Vec2, CornerDirection
from .sheetmetal_strip_geometry import StripFoldChain
from .sheetmetal_corner_policy import box_body_vertical_offsets
from .sheetmetal_part_adapters import StructuralGeometryResult
from .box_body_structure_core import (
    ResolvedBoxBodyPiece,
    ResolvedBoxBodyStructure,
    _canonical_cross_retain_mm,
)

def _merge_intervals(intervals):
    merged = []
    for start, end in sorted((float(a), float(b)) for a, b in intervals if float(b) > float(a)):
        if not merged or start > merged[-1][1] + 1e-9:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return tuple((a, b) for a, b in merged)


def _split_horizontal_bend(bend: BendLine, gaps) -> tuple[BendLine, ...]:
    start = min(float(bend.p1.x), float(bend.p2.x))
    end = max(float(bend.p1.x), float(bend.p2.x))
    y = float(bend.p1.y)
    cursor = start
    result = []
    for gap_start, gap_end in _merge_intervals(gaps):
        a = max(start, gap_start)
        b = min(end, gap_end)
        if b <= a:
            continue
        if a > cursor + 1e-9:
            result.append(BendLine(bend.name, Vec2(cursor, y), Vec2(a, y)))
        cursor = max(cursor, b)
    if cursor < end - 1e-9:
        result.append(BendLine(bend.name, Vec2(cursor, y), Vec2(end, y)))
    return tuple(result)


def box_body_seam_positions(resolved: ResolvedBoxBodyStructure) -> tuple[float, ...]:
    """Return formed-W seam positions in enclosure coordinates."""
    if resolved.structure_type not in {BoxBodyStructureType.TWO_PIECE_W_SPLIT, BoxBodyStructureType.THREE_PIECE_W_SPLIT}:
        return ()
    if len(resolved.pieces) <= 1:
        return ()
    positions = []
    for piece in resolved.pieces[:-1]:
        value = float(piece.formed_w_end)
        if not positions or abs(value - positions[-1]) > 1e-9:
            positions.append(value)
    return tuple(positions)


def apply_base_plate_structure_reliefs(
    base_result: StructuralGeometryResult,
    *,
    box_w: float,
    shrink_left: float,
    shrink_right: float,
    thickness: float,
    structure: ResolvedBoxBodyStructure | None = None,
    structure_state=None,
    seam_positions: tuple[float, ...] | None = None,
) -> StructuralGeometryResult:
    """Apply local cross-reliefs where box W seams cross Base Plate top/bottom folds.

    Seam positions outside the Base Plate finished-face span are ignored.  This
    is why the W-three-split default 50 mm seams naturally avoid a 55 mm shrink.
    """
    from shapely.geometry import Polygon, box as shapely_box

    state = normalize_box_body_structure_state(structure_state)
    type_id = BoxBodyStructureType(state["active_type"])
    configs = state.get("configs", {})
    cfg = configs.get(type_id.value, {}) if isinstance(configs, dict) else {}
    relief_length = float(cfg.get("baseplate_relief_length", 20.0))
    meat = _canonical_cross_retain_mm(
        amount_t=float(cfg.get("baseplate_single_side_meat_t", 0.5)),
        thickness=float(thickness),
        direction=CornerDirection.HEIGHT,
    )
    if relief_length <= 0:
        raise ValueError("底板十字避讓總長必須大於 0")

    geometry = base_result.topology
    for attr in ("left_fold", "right_fold", "top_fold", "bottom_fold"):
        if not hasattr(geometry, attr):
            raise ValueError("底板 resolved geometry 缺少四邊折彎資料")
    bottom_fold = float(geometry.bottom_fold)
    top_fold = float(geometry.top_fold)
    if meat < 0 or meat >= min(bottom_fold, top_fold):
        raise ValueError("底板單邊留肉必須小於底板折邊")

    if seam_positions is not None:
        raw_seams = tuple(float(s) for s in seam_positions)
    elif structure is not None:
        raw_seams = box_body_seam_positions(structure)
    else:
        raw_seams = ()

    finished_left = float(shrink_left)
    finished_right = float(box_w) - float(shrink_right)
    half = relief_length / 2.0
    centers = []
    gaps = []
    for seam in raw_seams:
        if seam < finished_left - 1e-9 or seam > finished_right + 1e-9:
            continue
        x = float(geometry.left_fold) + (seam - finished_left)
        centers.append(x)
        gaps.append((x - half, x + half))
    if not centers:
        return base_result

    material = Polygon([(float(p.x), float(p.y)) for p in base_result.outline])
    width = float(base_result.width)
    height = float(base_result.height)
    for x in centers:
        x1 = max(0.0, x - half)
        x2 = min(width, x + half)
        bottom_cut_top = max(0.0, bottom_fold - meat)
        top_cut_bottom = min(height, height - top_fold + meat)
        if bottom_cut_top > 0:
            material = material.difference(shapely_box(x1, 0.0, x2, bottom_cut_top))
        if top_cut_bottom < height:
            material = material.difference(shapely_box(x1, top_cut_bottom, x2, height))
    if material.geom_type != "Polygon" or material.is_empty:
        raise ValueError("底板十字避讓產生無效 CUTTING 幾何")
    outline = tuple(Vec2(float(x), float(y)) for x, y in material.exterior.coords)

    merged_gaps = _merge_intervals(gaps)
    bends = []
    for bend in base_result.bends:
        if bend.name in {"bottom", "top"}:
            bends.extend(_split_horizontal_bend(bend, merged_gaps))
        else:
            bends.append(bend)
    return StructuralGeometryResult(outline, tuple(bends), width, height, base_result.topology)


def _feature_finished_bounds(feature, face_w: float, face_h: float):
    from .sheetmetal_features import CircleFeature, RectFeature, ProfileFeature, feature_finished_point, _rotate_local_point
    center = feature_finished_point(feature, float(face_w), float(face_h))
    if isinstance(feature, CircleFeature):
        radius = float(feature.diameter) / 2.0
        return center.x - radius, center.x + radius
    if isinstance(feature, RectFeature):
        hw = float(feature.width) / 2.0
        hh = float(feature.height) / 2.0
        pts = (
            _rotate_local_point(Vec2(-hw, -hh), feature.rotation_deg),
            _rotate_local_point(Vec2(hw, -hh), feature.rotation_deg),
            _rotate_local_point(Vec2(hw, hh), feature.rotation_deg),
            _rotate_local_point(Vec2(-hw, hh), feature.rotation_deg),
        )
        xs = [center.x + p.x for p in pts]
        return min(xs), max(xs)
    if isinstance(feature, ProfileFeature):
        xs = []
        for point in feature.points:
            rotated = _rotate_local_point(point, feature.rotation_deg)
            xs.append(center.x + rotated.x)
        for _layer, points, _closed in feature.layered_profiles:
            for point in points:
                rotated = _rotate_local_point(point, feature.rotation_deg)
                xs.append(center.x + rotated.x)
        return (min(xs), max(xs)) if xs else (center.x, center.x)
    raise TypeError(f"Unsupported box body feature: {type(feature)!r}")


def _piece_w_context(piece: ResolvedBoxBodyPiece, *, h, t, head_corner_policy=None, tail_corner_policy=None):
    from .sheetmetal_features import BoxBodyFaceContext
    topology = piece.structural.topology
    if not isinstance(topology, StripFoldChain):
        return None
    cursor = 0.0
    target = None
    for segment in topology.segments:
        span = float(segment.length) + float(segment.compensation)
        if segment.name in {"w_left", "w_middle", "w_right"}:
            target = (cursor, cursor + span)
            break
        cursor += span
    if target is None:
        return None
    
    bottom, top = box_body_vertical_offsets(
        t, head_corner_policy=head_corner_policy, tail_corner_policy=tail_corner_policy,
    )
    return BoxBodyFaceContext(
        face_key="back",
        segment_name="back",
        outer_width=piece.formed_width,
        outer_height=float(h),
        thickness=float(t),
        unfolded_min_x=target[0],
        unfolded_max_x=target[1],
        unfolded_height=float(topology.height),
        bottom_outer_offset=bottom,
        top_outer_offset=top,
    )


def _resolve_feature_at_local_center(context, feature, local_center):
    from .sheetmetal_features import (
        CircleFeature, RectFeature, ProfileFeature,
        ResolvedCircle, ResolvedRect, ResolvedProfile, _rotate_local_point,
    )
    center = context.local_to_unfolded(local_center)
    if isinstance(feature, CircleFeature):
        return ResolvedCircle(
            center=center, radius=float(feature.diameter) / 2.0, layer=feature.layer,
            add_centerline=feature.add_centerline, source_type=feature.source_type,
        )
    if isinstance(feature, RectFeature):
        return ResolvedRect(
            center=center, width=float(feature.width), height=float(feature.height), layer=feature.layer,
            source_type=feature.source_type, rotation_deg=int(feature.rotation_deg),
        )
    if isinstance(feature, ProfileFeature):
        mapped = tuple(
            context.local_to_unfolded(local_center + _rotate_local_point(point, feature.rotation_deg))
            for point in feature.points
        )
        layered = []
        for layer, points, closed in feature.layered_profiles:
            layered.append((
                layer,
                tuple(context.local_to_unfolded(local_center + _rotate_local_point(point, feature.rotation_deg)) for point in points),
                closed,
            ))
        return ResolvedProfile(mapped, layer=feature.layer, source_type=feature.source_type, layered_profiles=tuple(layered))
    raise TypeError(f"Unsupported box body feature: {type(feature)!r}")



def _resolved_feature_shape(feature, *, filled: bool):
    """Return a Shapely geometry for one already-resolved feature.

    ``filled`` is used only for CUTTING closed contours, because only CUTTING
    participates in material subtraction.  Other processes are clipped as
    contour/linework so a seam can never manufacture a fake closing CUTTING edge.
    """
    from shapely.geometry import LineString, Point, Polygon
    from .sheetmetal_features import ResolvedCircle, ResolvedRect, ResolvedProfile

    if isinstance(feature, ResolvedCircle):
        circle = Point(float(feature.center.x), float(feature.center.y)).buffer(
            float(feature.radius), quad_segs=64
        )
        return circle if filled else circle.exterior
    if isinstance(feature, ResolvedRect):
        polygon = Polygon([(float(p.x), float(p.y)) for p in feature.points])
        return polygon if filled else polygon.exterior
    if isinstance(feature, ResolvedProfile):
        points = [(float(p.x), float(p.y)) for p in feature.points]
        if len(points) < 2:
            return LineString()
        if filled and len(points) >= 3:
            polygon = Polygon(points)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            return polygon
        if len(points) >= 3 and points[0] != points[-1]:
            points = points + [points[0]]
        return LineString(points)
    raise TypeError(f"Unsupported resolved feature: {type(feature)!r}")


def _polygon_parts(geometry):
    if geometry.is_empty:
        return ()
    if geometry.geom_type == "Polygon":
        return (geometry,)
    return tuple(
        item for item in getattr(geometry, "geoms", ())
        if getattr(item, "geom_type", "") == "Polygon" and float(item.area) > 1e-9
    )


def _line_parts(geometry):
    if geometry.is_empty:
        return ()
    if geometry.geom_type in {"LineString", "LinearRing"}:
        return (geometry,)
    parts = []
    for item in getattr(geometry, "geoms", ()):
        if getattr(item, "geom_type", "") in {"LineString", "LinearRing"} and float(item.length) > 1e-9:
            parts.append(item)
    return tuple(parts)


def _profile_from_coords(coords, *, layer: str, source_type, closed: bool):
    from .sheetmetal_features import ResolvedProfile
    points = tuple(Vec2(float(x), float(y)) for x, y in coords)
    if closed and len(points) >= 2 and points[0] == points[-1]:
        points = points[:-1]
    if len(points) < (3 if closed else 2):
        return None
    # Store the layer as one explicit sub-profile so DrawingScene preserves the
    # open/closed process contour exactly instead of applying ResolvedProfile's
    # legacy implicit-closed fallback.
    return ResolvedProfile(
        points=points,
        layer=str(layer),
        source_type=source_type,
        layered_profiles=((str(layer), points, bool(closed)),),
    )


def _clip_one_resolved_feature(feature, clip_geometry):
    """Clip one resolved feature without changing its manufacturing process."""
    from shapely.geometry import LineString
    from .sheetmetal_features import ResolvedCircle, ResolvedRect, ResolvedProfile

    layer = str(getattr(feature, "layer", "CUTTING") or "CUTTING").upper()
    source_type = getattr(feature, "source_type", None)
    is_cutting = layer == "CUTTING"
    shape = _resolved_feature_shape(feature, filled=is_cutting)
    if shape.is_empty:
        return []

    # Keep exact primitives when the entire feature belongs to the part. This
    # preserves true CIRCLE/rotated-RECT semantics away from split boundaries.
    if clip_geometry.covers(shape):
        return [feature]

    clipped = shape.intersection(clip_geometry)
    out = []
    if is_cutting:
        for polygon in _polygon_parts(clipped):
            profile = _profile_from_coords(
                polygon.exterior.coords,
                layer=layer,
                source_type=source_type,
                closed=True,
            )
            if profile is not None:
                out.append(profile)
    else:
        for line in _line_parts(clipped):
            profile = _profile_from_coords(
                line.coords,
                layer=layer,
                source_type=source_type,
                closed=False,
            )
            if profile is not None:
                out.append(profile)

    # Preserve semantic centerlines when a circle is clipped at a seam. They are
    # process linework, never CUTTING closure.
    if isinstance(feature, ResolvedCircle) and bool(feature.add_centerline):
        center_layer = "DATUM" if layer == "BLIND_HOLE" else layer
        cx, cy, radius = float(feature.center.x), float(feature.center.y), float(feature.radius)
        for coords in (
            ((cx - radius, cy), (cx + radius, cy)),
            ((cx, cy - radius), (cx, cy + radius)),
        ):
            clipped_line = LineString(coords).intersection(clip_geometry)
            for line in _line_parts(clipped_line):
                profile = _profile_from_coords(
                    line.coords,
                    layer=center_layer,
                    source_type=source_type,
                    closed=False,
                )
                if profile is not None:
                    out.append(profile)
    return out


def _clip_resolved_feature_to_piece(feature, piece, *, face_context=None):
    """Clip resolved feature to actual piece material and optional face span."""
    from shapely.geometry import Polygon, box as shapely_box

    material = Polygon([(float(p.x), float(p.y)) for p in piece.structural.outline])
    if not material.is_valid:
        material = material.buffer(0)
    clip_geometry = material
    if face_context is not None:
        clip_geometry = clip_geometry.intersection(shapely_box(
            float(face_context.unfolded_min_x),
            0.0,
            float(face_context.unfolded_max_x),
            float(piece.structural.height),
        ))
    return _clip_one_resolved_feature(feature, clip_geometry)


def _clip_layered_profile_feature(context, feature, local_center, piece):
    """Resolve and independently clip every ProfileFeature sub-layer."""
    from shapely.geometry import LineString, Polygon, box as shapely_box
    from .sheetmetal_features import ProfileFeature, ResolvedProfile, _rotate_local_point

    if not isinstance(feature, ProfileFeature) or not feature.layered_profiles:
        return None

    material = Polygon([(float(p.x), float(p.y)) for p in piece.structural.outline])
    if not material.is_valid:
        material = material.buffer(0)
    clip_geometry = material.intersection(shapely_box(
        float(context.unfolded_min_x), 0.0,
        float(context.unfolded_max_x), float(piece.structural.height),
    ))

    results = []
    for layer, points, closed in feature.layered_profiles:
        mapped = tuple(
            context.local_to_unfolded(local_center + _rotate_local_point(point, feature.rotation_deg))
            for point in points
        )
        layer = str(layer)
        closed = bool(closed)
        if len(mapped) < 2:
            continue

        if layer.upper() == "CUTTING" and closed and len(mapped) >= 3:
            polygon = Polygon([(float(p.x), float(p.y)) for p in mapped])
            if not polygon.is_valid:
                polygon = polygon.buffer(0)
            if clip_geometry.covers(polygon):
                results.append(ResolvedProfile(
                    points=mapped,
                    layer=layer,
                    source_type=feature.source_type,
                    layered_profiles=((layer, mapped, True),),
                ))
                continue
            for part in _polygon_parts(polygon.intersection(clip_geometry)):
                profile = _profile_from_coords(
                    part.exterior.coords, layer=layer, source_type=feature.source_type, closed=True,
                )
                if profile is not None:
                    results.append(profile)
            continue

        line_points = list(mapped)
        if closed and line_points[0] != line_points[-1]:
            line_points.append(line_points[0])
        line = LineString([(float(p.x), float(p.y)) for p in line_points])
        if clip_geometry.covers(line):
            results.append(ResolvedProfile(
                points=mapped,
                layer=layer,
                source_type=feature.source_type,
                layered_profiles=((layer, mapped, closed),),
            ))
            continue
        for part in _line_parts(line.intersection(clip_geometry)):
            profile = _profile_from_coords(
                part.coords, layer=layer, source_type=feature.source_type, closed=False,
            )
            if profile is not None:
                results.append(profile)
    return results


def resolve_box_body_piece_face_features(
    structure: ResolvedBoxBodyStructure,
    *,
    face_features,
    w: float,
    h: float,
    d: float,
    t: float,
    head_corner_policy=None,
    tail_corner_policy=None,
):
    """Resolve existing face features into independent physical box-body pieces.

    Back-face features are never moved.  A feature whose real geometry crosses a
    W seam is clipped against each physical piece's actual material boundary.
    Fully contained primitives remain exact; seam-crossing geometry becomes a
    process-preserving clipped profile instead of pretending the whole primitive
    belongs to both pieces.
    """
    from .sheetmetal_features import (
        box_body_face_contexts_from_strip, resolve_box_body_face_features,
        feature_finished_point,
    )
    stores = {piece.key: [] for piece in structure.pieces}
    face_features = dict(face_features or {})
    if structure.structure_type is BoxBodyStructureType.INTEGRAL:
        piece = structure.pieces[0]
        contexts = box_body_face_contexts_from_strip(
            piece.structural.topology, w=w, h=h, d=d, t=t,
            head_corner_policy=head_corner_policy, tail_corner_policy=tail_corner_policy,
        )
        stores[piece.key] = resolve_box_body_face_features(contexts, face_features)
        return stores

    # Side-face stores belong to the physical outer side pieces and retain the
    # existing face-context mapping.
    left_piece = next((p for p in structure.pieces if p.role in {"left", "left_side"}), None)
    right_piece = next((p for p in structure.pieces if p.role in {"right", "right_side"}), None)
    for piece, face_key in ((left_piece, "left"), (right_piece, "right")):
        if piece is None or not face_features.get(face_key):
            continue
        topology = piece.structural.topology
        if not isinstance(topology, StripFoldChain):
            continue
        # Build only the requested side context from the segment present in this piece.
        from .sheetmetal_features import BoxBodyFaceContext
        
        target_names = (
            {"depth_left", "d_left"}
            if face_key == "left"
            else {"depth_right", "d_right"}
        )
        target_name = "depth_left" if face_key == "left" else "depth_right"
        cursor = 0.0
        span = None
        resolved_segment_name = None
        for segment in topology.segments:
            width = float(segment.length) + float(segment.compensation)
            if segment.name in target_names:
                span = (cursor, cursor + width)
                resolved_segment_name = segment.name
                break
            cursor += width
        if span is None:
            continue
        bottom, top = box_body_vertical_offsets(
            t, head_corner_policy=head_corner_policy, tail_corner_policy=tail_corner_policy,
        )
        context = BoxBodyFaceContext(
            face_key=face_key, segment_name=str(resolved_segment_name or target_name), outer_width=float(d), outer_height=float(h),
            thickness=float(t), unfolded_min_x=span[0], unfolded_max_x=span[1],
            unfolded_height=float(topology.height), bottom_outer_offset=bottom, top_outer_offset=top,
        )
        for feature in face_features.get(face_key, ()):
            center = feature_finished_point(feature, float(d), float(h))
            stores[piece.key].append(_resolve_feature_at_local_center(context, feature, center))

    # Side-back mode owns one independent flat back panel.  Map back features
    # directly into its flat panel coordinate system using the same global WH face.
    if structure.structure_type is BoxBodyStructureType.THREE_PIECE_SIDE_BACK_SPLIT:
        back_piece = next(p for p in structure.pieces if p.role == "back")
        offset = float(back_piece.formed_w_start)
        panel_w = float(back_piece.formed_width)
        from .sheetmetal_features import BoxBodyFaceContext
        
        bottom, top = box_body_vertical_offsets(
            t, head_corner_policy=head_corner_policy, tail_corner_policy=tail_corner_policy,
        )
        # No left/right bends on the back panel: map finished x proportionally to
        # the actual compensated panel width and preserve global center alignment.
        context = BoxBodyFaceContext(
            face_key="back", segment_name="back_panel", outer_width=panel_w + 2.0 * float(t),
            outer_height=float(h), thickness=float(t), unfolded_min_x=0.0,
            unfolded_max_x=panel_w, unfolded_height=float(back_piece.structural.height),
            bottom_outer_offset=bottom, top_outer_offset=top,
        )
        for feature in face_features.get("back", ()):
            global_center = feature_finished_point(feature, float(w), float(h))
            local = Vec2(global_center.x - offset, global_center.y)
            layered = _clip_layered_profile_feature(context, feature, local, back_piece)
            if layered is not None:
                stores[back_piece.key].extend(layered)
                continue
            resolved_feature = _resolve_feature_at_local_center(context, feature, local)
            stores[back_piece.key].extend(
                _clip_resolved_feature_to_piece(resolved_feature, back_piece, face_context=context)
            )
        return stores

    # W-split modes: map every intersected back feature to every piece it crosses.
    for feature in face_features.get("back", ()):
        min_x, max_x = _feature_finished_bounds(feature, float(w), float(h))
        global_center = feature_finished_point(feature, float(w), float(h))
        for piece in structure.pieces:
            if max_x < piece.formed_w_start - 1e-9 or min_x > piece.formed_w_end + 1e-9:
                continue
            context = _piece_w_context(
                piece, h=h, t=t,
                head_corner_policy=head_corner_policy, tail_corner_policy=tail_corner_policy,
            )
            if context is None:
                continue
            local_center = Vec2(global_center.x - piece.formed_w_start, global_center.y)
            layered = _clip_layered_profile_feature(context, feature, local_center, piece)
            if layered is not None:
                stores[piece.key].extend(layered)
                continue
            resolved_feature = _resolve_feature_at_local_center(context, feature, local_center)
            stores[piece.key].extend(
                _clip_resolved_feature_to_piece(resolved_feature, piece, face_context=context)
            )
    return stores
