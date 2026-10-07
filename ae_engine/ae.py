# -*- coding: utf-8 -*-
"""
箱身與封頭尾展開計算及 DXF 輸出主程式
"""

import os
import sys
import ezdxf
import configparser

from .sheetmetal_geometry import (
    Vec2,
    EndCapGeometry,
    ReliefConfig,
    build_endcap_bend_segments,
    build_endcap_outline,
    calculate_endcap_relief_dimensions,
    FourSideFlangeGeometry,
    RectCornerReliefPolicy,
    build_four_side_outline,
    build_four_side_bend_segments,
    FourSideBendExtentPolicy,
    FoldSegment,
    StripFoldChain,
    build_strip_outline,
    build_strip_bend_segments,
    FourCornerTypePolicy,
)


from .sheetmetal_part_adapters import (
    DoorFrameEdges,
    build_box_body_result,
    build_box_body_result_from_fold_profile,
    build_door_result,
    build_base_plate_result,
    build_indicator_box_result,
    build_endcap_result,
    calculate_door_finished_size as _calculate_door_finished_size_from_adapter,
    build_unknown_door_result,
    build_unknown_base_plate_result,
    build_unknown_indicator_box_result,
    build_unknown_endcap_result,
    build_finished_reference_guide,
)

from .sheetmetal_drawing import (
    PolylinePrimitive,
    LinePrimitive,
    CirclePrimitive,
    TextPrimitive,
    DrawingScene,
    SceneData,
    structural_result_to_primitives,
    resolved_features_to_primitives,
    build_stock_outline,
    build_base_plate_datum,
    build_base_plate_check,
    build_door_check,
    build_door_indicator_check,
    build_box_body_check,
    build_indicator_box_check,
    build_endcap_check,
    mirror_drawing_scene_y,
    mirror_drawing_scene_x,
)

from .dxf_serialization import (
    setup_dxf_layers,
    add_drawing_scene_to_dxf as _add_drawing_scene_to_dxf,
    save_scene_dxf as _save_scene_dxf,
)

from .baseline_source import (
    BASELINE_SOURCE_VERIFIED,
    BASELINE_SOURCE_UNVERIFIED,
    clear_baseline_dxf_source_cache,
    force_reload_baseline_dxf_sources,
    _baseline_dxf_fingerprint,
    baseline_source_fingerprint,
    load_baseline_dxf_source_with_status,
    load_baseline_dxf_source,
    iter_baseline_entities as _iter_baseline_entities,
    baseline_entity_layer as _baseline_entity_layer,
    baseline_cutting_bounds as _baseline_cutting_bounds,
)
from . import baseline_resources as _baseline_resources
from . import baseline_scene_adapters as _baseline_scene_adapters

from .sheetmetal_features import (
    box_body_face_contexts_from_strip,
    resolve_box_body_face_features,
    DoorIndicatorContext,
    EndCapFeatureContext,
    endcap_feature_context_from_geometry,
    ResolvedCircle,
    ResolvedRect,
    ResolvedProfile,
    legacy_hole_to_feature,
    resolve_endcap_features,
    resolve_door_indicator_features,
    resolve_door_indicator_layout,
    measure_door_indicator_position,
    resolve_base_plate_mounting_holes,
    resolved_circles_from_baseline,
    identify_door_baseline_nameplate_circles,
    resolve_vault_endcap_fixed_features,
    resolve_receiving_endcap_fixed_features,
    resolve_endcap_fixed_features_for_model,
    VaultEndCapFeaturePolicy,
    ReceivingEndCapFeaturePolicy,
    RECEIVING_ENDCAP_FEATURE_POLICY,
    endcap_finished_feature_surface,
    feature_is_within_surface,
    feature_surface_from_structural_result,
    feature_surface_from_outline,
    resolve_surface_features,
)

from .ae_config import (
    get_resource_path,
    INI_PATH,
    config,
    default_config,
    W,
    H,
    D,
    T,
    FW,
    DRAW_STOCK,
    hang_hole_r,
    hang_hole_x,
    hang_hole_y_up,
    sq_x_left,
    sq_width,
    sq_y_bottom,
    sq_height,
    bottom_hole_r,
    bottom_hole_y,
    VAULT_ENDCAP_FEATURE_POLICY,
    notch_bottom_gap,
    notch_sub_x_half,
    notch_sub_y_factor,
    RELIEF_CONFIG,
    door_gap_w_def,
    door_gap_h_def,
    door_fold_left_def,
    door_fold_right_def,
    door_fold_top_def,
    door_fold_bottom_def,
    indicator_box_fold_def,
    indicator_small_door_gap_def,
    base_plate_shrink_def,
    base_plate_bend_def,
    zl1_def,
    zl2_def,
    zr1_def,
    zr2_def,
    z_comp_def,
    yl1_def,
    yr1_def,
    ytop1_def,
    ybottom1_def,
)

# ==========================================
# 數值格式化輔助函式
# ==========================================
from .ae_calculations import (
    fmt_val,
    calculate_z_length,
    calculate_y_width,
    calculate_y_depth,
    calculate_door_finished_size,
    calculate_door_blank_size,
)

from .ae_door_indicator import (
    _make_door_geometry,
    _append_surface_user_features,
    _surface_from_scene_primary_cutting,
    feature_surface_from_drawing_scene,
    _build_door_scene,
    export_door_dxf,
    export_unknown_door_dxf,
    indicator_small_door_window_geometry,
    get_stretched_door_data,
    export_stretched_door_dxf,
    _make_indicator_box_geometry,
    get_indicator_box_data,
    get_stretched_indicator_box_data,
    _build_stretched_indicator_box_scene,
    export_stretched_indicator_box_dxf,
    _build_indicator_box_scene,
    export_indicator_box_dxf,
)

def _box_body_baseline_mapping_context(model_name, total_length, total_height,
                                       zl1=15.0, zl2=20.0, zr1=15.0, zr2=20.0, z_comp=-10.0,
                                       w=500.0, d=150.0, t=2.0, fw=25.0):
    """Read Box Body baseline once and return its modelspace plus point mapper."""
    dxf_path = baseline_part_path(model_name, "箱身.dxf")
    if not dxf_path:
        return None, None

    doc = (globals().get("load_baseline_dxf_source") or ezdxf.readfile)(dxf_path)
    msp = doc.modelspace()
    all_x = []
    all_y = []
    for ent in msp:
        kind = ent.dxftype()
        if kind == 'LWPOLYLINE':
            for pt in ent.get_points():
                all_x.append(pt[0]); all_y.append(pt[1])
        elif kind == 'LINE':
            all_x.extend([ent.dxf.start.x, ent.dxf.end.x])
            all_y.extend([ent.dxf.start.y, ent.dxf.end.y])
        elif kind == 'CIRCLE':
            cx, cy = ent.dxf.center.x, ent.dxf.center.y
            r = ent.dxf.radius
            all_x.extend([cx-r, cx+r]); all_y.extend([cy-r, cy+r])
        elif kind == 'ARC':
            cx, cy = ent.dxf.center.x, ent.dxf.center.y
            r = ent.dxf.radius
            all_x.extend([cx-r, cx+r]); all_y.extend([cy-r, cy+r])
        elif kind == 'POLYLINE':
            for v in ent.vertices:
                all_x.append(v.dxf.location.x); all_y.append(v.dxf.location.y)
    if not all_x or not all_y:
        return msp, None

    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    W_base = max_x - min_x
    H_base = max_y - min_y

    box_chain = _make_box_body_chain(
        w, total_height + 2*t, d, t, fw,
        zl1, zl2, zr1, zr2, z_comp, True,
    )
    chain_bends = build_strip_bend_segments(box_chain)
    x1, x2, x3, x4, x5, x6 = [b.p1.x for b in chain_bends[:6]]

    Xb3 = 60.0
    Xb4 = 207.0
    Xb5 = 703.0
    Xb6 = 849.0

    def map_point(point):
        raw_x, raw_y = float(point.x), float(point.y)
        cx = raw_x - min_x
        d_top = max_y - raw_y
        d_bottom = raw_y - min_y

        if cx < Xb3:
            cx_new = (cx / Xb3) * x3
        elif cx < Xb4:
            cx_new = x4 - (Xb4 - cx)
        elif cx < Xb5:
            mid_w = (Xb4 + Xb5) / 2.0
            cx_new = x4 + (cx - Xb4) if cx < mid_w else x5 - (Xb5 - cx)
        elif cx < Xb6:
            mid_d = (Xb5 + Xb6) / 2.0
            cx_new = x5 + (cx - Xb5) if cx < mid_d else x6 - (Xb6 - cx)
        else:
            cx_new = total_length - (W_base - cx)

        cy_new = total_height - d_top if d_top < H_base/2.0 else d_bottom
        return Vec2(cx_new, cy_new)

    return msp, map_point



def _box_body_depth_placeholder_lines(msp):
    """Locate the compact Color-211 vector-number cluster used as the depth placeholder.

    The supplied Box Body baseline stores the sample value ``150`` as exploded LINE
    entities.  Nearby real MARKING locator lines must remain untouched, so we group
    Color-211 lines by endpoint proximity and select only the compact text-like group.
    """
    lines = [
        ent for ent in msp
        if ent.dxftype() == 'LINE'
        and (ent.dxf.color if ent.dxf.hasattr('color') else 256) == 211
    ]
    if not lines:
        return ()

    def endpoint_distance(a, b):
        a_pts = (a.dxf.start, a.dxf.end)
        b_pts = (b.dxf.start, b.dxf.end)
        return min(
            ((pa.x - pb.x) ** 2 + (pa.y - pb.y) ** 2) ** 0.5
            for pa in a_pts for pb in b_pts
        )

    remaining = set(range(len(lines)))
    components = []
    while remaining:
        component = {remaining.pop()}
        changed = True
        while changed:
            changed = False
            for idx in tuple(remaining):
                if any(endpoint_distance(lines[idx], lines[member]) <= 8.0 for member in component):
                    component.add(idx)
                    remaining.remove(idx)
                    changed = True
        components.append(tuple(lines[idx] for idx in sorted(component)))

    candidates = []
    for component in components:
        if len(component) < 6:
            continue
        xs = [float(v) for ent in component for v in (ent.dxf.start.x, ent.dxf.end.x)]
        ys = [float(v) for ent in component for v in (ent.dxf.start.y, ent.dxf.end.y)]
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        if height > 0.0 and width >= height * 1.5:
            candidates.append((len(component), width * height, component))
    if not candidates:
        return ()
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2]


def _box_body_width_bend_marking_lines(msp, excluded_ids=()):
    """Return the four 30 mm MARKING strokes that sit on the width-boundary BENDs.

    They are unfolded-sheet bend locators, not face-local features.  The baseline
    supplies their stroke shape/vertical placement; ``map_point`` keeps their X
    positions attached to the current ``depth_left`` and ``front`` BENDs.
    """
    excluded = set(excluded_ids)
    result = []
    for ent in msp:
        if id(ent) in excluded or ent.dxftype() != 'LINE':
            continue
        color = ent.dxf.color if ent.dxf.hasattr('color') else 256
        if color != 211:
            continue
        sx, sy = float(ent.dxf.start.x), float(ent.dxf.start.y)
        ex, ey = float(ent.dxf.end.x), float(ent.dxf.end.y)
        if abs(sx - ex) > 1e-6:
            continue
        if abs(abs(ey - sy) - 30.0) > 0.05:
            continue
        result.append(ent)
    return tuple(result)


def _stroke_number_marking(value, template_points):
    """Generate current depth as vector MARKING centred on the baseline placeholder."""
    if not template_points:
        return []
    text = fmt_val(value)
    xs = [float(p.x) for p in template_points]
    ys = [float(p.y) for p in template_points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    height = max_y - min_y
    if height <= 0.0:
        return []

    # Baseline contains a three-character sample (150). Keep that character size,
    # centre the current value on the same anchor, and let longer values grow equally
    # to both sides instead of scaling the engraving height.
    template_width = max_x - min_x
    cell_width = template_width / 3.0 if template_width > 0.0 else height * 0.75
    center_x = (min_x + max_x) / 2.0
    total_width = cell_width * max(1, len(text))
    start_x = center_x - total_width / 2.0

    # Seven-segment-like single-stroke CAD digits.  Zero keeps a diagonal slash,
    # matching the intent of the exploded sample glyph in the supplied baseline.
    seg = {
        'a': ((0.10, 1.00), (0.90, 1.00)),
        'b': ((0.90, 0.95), (0.90, 0.55)),
        'c': ((0.90, 0.45), (0.90, 0.05)),
        'd': ((0.10, 0.00), (0.90, 0.00)),
        'e': ((0.10, 0.05), (0.10, 0.45)),
        'f': ((0.10, 0.55), (0.10, 0.95)),
        'g': ((0.10, 0.50), (0.90, 0.50)),
        'z': ((0.20, 0.12), (0.80, 0.88)),
    }
    digit_segments = {
        '0': 'abcdefz',
        '1': 'bc',
        '2': 'abdeg',
        '3': 'abcdg',
        '4': 'bcfg',
        '5': 'acdfg',
        '6': 'acdefg',
        '7': 'abc',
        '8': 'abcdefg',
        '9': 'abcdfg',
        '-': 'g',
    }

    profiles = []
    for index, char in enumerate(text):
        cell_x = start_x + index * cell_width
        if char == '.':
            dot_x = cell_x + cell_width * 0.50
            p1 = Vec2(dot_x - cell_width * 0.05, min_y)
            p2 = Vec2(dot_x + cell_width * 0.05, min_y + height * 0.05)
            profiles.append(ResolvedProfile(
                points=(p1, p2), layer='MARKING', source_type='baseline_depth_value',
                layered_profiles=(('MARKING', (p1, p2), False),),
            ))
            continue
        for segment_name in digit_segments.get(char, ''):
            (x1, y1), (x2, y2) = seg[segment_name]
            p1 = Vec2(cell_x + x1 * cell_width, min_y + y1 * height)
            p2 = Vec2(cell_x + x2 * cell_width, min_y + y2 * height)
            profiles.append(ResolvedProfile(
                points=(p1, p2), layer='MARKING', source_type='baseline_depth_value',
                layered_profiles=(('MARKING', (p1, p2), False),),
            ))
    return profiles


def get_box_body_baseline_unfolded_features(model_name, total_length, total_height,
                                             zl1=15.0, zl2=20.0, zr1=15.0, zr2=20.0, z_comp=-10.0,
                                             w=500.0, d=150.0, t=2.0, fw=25.0):
    """Map baseline fixed processing into the current unfolded Box Body geometry."""
    try:
        msp, map_point = _box_body_baseline_mapping_context(
            model_name, total_length, total_height,
            zl1, zl2, zr1, zr2, z_comp, w, d, t, fw,
        )
        if msp is None or map_point is None:
            return []
        features = []
        depth_placeholder = _box_body_depth_placeholder_lines(msp)
        depth_placeholder_ids = {id(ent) for ent in depth_placeholder}
        width_bend_markings = _box_body_width_bend_marking_lines(
            msp, excluded_ids=depth_placeholder_ids,
        )
        width_bend_marking_ids = {id(ent) for ent in width_bend_markings}
        mapped_placeholder_points = [
            map_point(point)
            for ent in depth_placeholder
            for point in (ent.dxf.start, ent.dxf.end)
        ]
        for ent in msp:
            kind = ent.dxftype()
            color = ent.dxf.color if ent.dxf.hasattr('color') else 256
            if kind == 'LINE' and id(ent) in depth_placeholder_ids:
                continue
            if kind == 'LINE' and id(ent) in width_bend_marking_ids:
                p1 = map_point(ent.dxf.start)
                p2 = map_point(ent.dxf.end)
                features.append(ResolvedProfile(
                    points=(p1, p2), layer='MARKING', source_type='baseline_width_bend_mark',
                    layered_profiles=(('MARKING', (p1, p2), False),),
                ))
                continue
            if kind == 'CIRCLE':
                layer = 'MARKING' if color == 211 else 'CUTTING'
                features.append(ResolvedCircle(
                    center=map_point(ent.dxf.center), radius=float(ent.dxf.radius),
                    layer=layer, source_type='baseline',
                ))
            elif kind == 'LINE' and color == 211:
                p1 = map_point(ent.dxf.start)
                p2 = map_point(ent.dxf.end)
                features.append(ResolvedProfile(
                    points=(p1, p2), layer='MARKING', source_type='baseline',
                    layered_profiles=(('MARKING', (p1, p2), False),),
                ))
            elif kind == 'LWPOLYLINE' and color == 211:
                pts = tuple(map_point(Vec2(x, y)) for x, y in ent.get_points('xy'))
                if len(pts) >= 2:
                    closed = bool(ent.closed)
                    features.append(ResolvedProfile(
                        points=pts, layer='MARKING', source_type='baseline',
                        layered_profiles=(('MARKING', pts, closed),),
                    ))
        features.extend(_stroke_number_marking(d, mapped_placeholder_points))
        return features
    except Exception as e:
        print(f"警告：讀取箱身基準固定特徵失敗: {e}")
        return []


def get_mapped_circles_from_baseline(model_name, total_length, total_height,
                                     zl1=15.0, zl2=20.0, zr1=15.0, zr2=20.0, z_comp=-10.0,
                                     w=500.0, d=150.0, t=2.0, fw=25.0):
    """Backward-compatible circle-only view of Box Body baseline features."""
    return [
        (f.center.x, f.center.y, f.radius, f.layer)
        for f in get_box_body_baseline_unfolded_features(
            model_name, total_length, total_height,
            zl1, zl2, zr1, zr2, z_comp, w, d, t, fw,
        )
        if isinstance(f, ResolvedCircle)
    ]

def box_body_baseline_source_label(model_name):
    """Describe the real Box Body source without implying structural baseline stretching."""
    model = (model_name or "").strip()
    if model and has_baseline_part(model, "箱身.dxf"):
        return f"基準檔：{model}/箱身.dxf（固定特徵映射）"
    return "未使用基準檔（程式計算生成）"


def get_box_body_baseline_face_features(
    model_name,
    *,
    w,
    h,
    d,
    t,
    fw,
    zl1=15.0,
    zl2=20.0,
    zr1=15.0,
    zr2=20.0,
    z_comp=-10.0,
    head_corner_policy: FourCornerTypePolicy | None = None,
    tail_corner_policy: FourCornerTypePolicy | None = None,
):
    """Return fixed Box Body baseline circles in direct WHD face coordinates.

    The existing baseline parser remains authoritative for locating features in
    unfolded geometry.  This adapter only classifies those mapped circles into
    the three editable faces and projects them back to the user-facing WHD
    coordinate system used by the editors.
    """
    result = build_box_body_result(
        w=w, h=h, d=d, t=t, fw=fw,
        zl1=zl1, zl2=zl2, zr1=zr1, zr2=zr2, z_comp=z_comp,
        include_right_fw=True,
        head_corner_policy=head_corner_policy,
        tail_corner_policy=tail_corner_policy,
    )
    contexts = box_body_face_contexts_from_strip(
        result.topology, w=w, h=h, d=d, t=t,
        head_corner_policy=head_corner_policy,
        tail_corner_policy=tail_corner_policy,
    )
    mapped = get_box_body_baseline_unfolded_features(
        model_name, result.width, result.height,
        zl1, zl2, zr1, zr2, z_comp, w, d, t, fw,
    )
    face_features = {"left": [], "back": [], "right": []}
    for feature in mapped:
        if getattr(feature, "source_type", "") == "baseline_width_bend_mark":
            continue
        points = (feature.center,) if isinstance(feature, ResolvedCircle) else tuple(feature.points)
        for face_key in ("left", "back", "right"):
            ctx = contexts[face_key]
            if points and all(ctx.unfolded_min_x - 1e-7 <= p.x <= ctx.unfolded_max_x + 1e-7 for p in points):
                local_points = tuple(ctx.unfolded_to_local(p) for p in points)
                if isinstance(feature, ResolvedCircle):
                    face_features[face_key].append(ResolvedCircle(
                        center=local_points[0], radius=feature.radius,
                        layer=feature.layer, add_centerline=feature.add_centerline,
                        source_type="baseline",
                    ))
                else:
                    face_features[face_key].append(ResolvedProfile(
                        points=local_points, layer=feature.layer, source_type="baseline",
                        layered_profiles=((feature.layer, local_points, False),),
                    ))
                break
    return face_features



def _map_box_body_baseline_face_features_to_topology(contexts, face_features):
    """Map baseline features stored in face-local WHD coordinates to a new strip.

    ``get_box_body_baseline_face_features`` intentionally detaches fixed DXF
    features from the legacy 9-segment unfolded X positions. This mapper is the
    inverse boundary: it places those local features onto the current arbitrary
    D-W-D topology without rediscovering their semantics.
    """
    mapped = []
    for face_key in ("left", "back", "right"):
        ctx = contexts[face_key]
        for feature in (face_features or {}).get(face_key, ()): 
            if isinstance(feature, ResolvedCircle):
                mapped.append(ResolvedCircle(
                    center=ctx.local_to_unfolded(feature.center), radius=feature.radius,
                    layer=feature.layer, add_centerline=feature.add_centerline,
                    source_type=feature.source_type,
                ))
            elif isinstance(feature, ResolvedRect):
                mapped.append(ResolvedRect(
                    center=ctx.local_to_unfolded(feature.center),
                    width=feature.width, height=feature.height, layer=feature.layer,
                    source_type=feature.source_type, rotation_deg=feature.rotation_deg,
                ))
            elif isinstance(feature, ResolvedProfile):
                points = tuple(ctx.local_to_unfolded(point) for point in feature.points)
                layered = tuple(
                    (layer, tuple(ctx.local_to_unfolded(point) for point in pts), closed)
                    for layer, pts, closed in feature.layered_profiles
                )
                mapped.append(ResolvedProfile(
                    points=points, layer=feature.layer, source_type=feature.source_type,
                    layered_profiles=layered,
                ))
    return mapped

def _make_box_body_chain(
    w, h, d, t, fw, zl1, zl2, zr1, zr2, z_comp, include_right_fw=True,
    head_corner_policy=None, tail_corner_policy=None,
):
    return build_box_body_result(
        w=w, h=h, d=d, t=t, fw=fw,
        zl1=zl1, zl2=zl2, zr1=zr1, zr2=zr2, z_comp=z_comp,
        include_right_fw=include_right_fw,
        head_corner_policy=head_corner_policy,
        tail_corner_policy=tail_corner_policy,
    ).topology


def _build_box_body_scene(*, w, h, d, t, fw, zl1, zl2, zr1, zr2, z_comp,
                          draw_stock=False, model_name=None, user_features=None,
                          face_features=None, head_corner_policy=None, tail_corner_policy=None,
                          fold_profile=None, structural_result=None):
    """Build the complete Box Body DrawingScene from one authoritative Fold Chain."""
    result = structural_result
    if result is None and fold_profile:
        result = build_box_body_result_from_fold_profile(
            fold_profile, h=h, t=t,
            head_corner_policy=head_corner_policy,
            tail_corner_policy=tail_corner_policy,
        )
    elif result is None:
        result = build_box_body_result(
            w=w, h=h, d=d, t=t, fw=fw, zl1=zl1, zl2=zl2, zr1=zr1, zr2=zr2,
            z_comp=z_comp, include_right_fw=True,
            head_corner_policy=head_corner_policy,
            tail_corner_policy=tail_corner_policy,
        )
    scene = DrawingScene()
    if draw_stock:
        scene.add(build_stock_outline(result.width, result.height))
    scene.extend(structural_result_to_primitives(result))
    _append_surface_user_features(scene, result, user_features, "box_body")
    contexts = None
    if face_features or (model_name and fold_profile):
        contexts = box_body_face_contexts_from_strip(
            result.topology, w=w, h=h, d=d, t=t,
            head_corner_policy=head_corner_policy,
            tail_corner_policy=tail_corner_policy,
        )
    if face_features:
        scene.extend(resolved_features_to_primitives(
            resolve_box_body_face_features(contexts, face_features)
        ))
    if model_name:
        if fold_profile:
            baseline_faces = get_box_body_baseline_face_features(
                model_name, w=w, h=h, d=d, t=t, fw=fw,
                zl1=zl1, zl2=zl2, zr1=zr1, zr2=zr2, z_comp=z_comp,
                head_corner_policy=head_corner_policy, tail_corner_policy=tail_corner_policy,
            )
            scene.extend(resolved_features_to_primitives(
                _map_box_body_baseline_face_features_to_topology(contexts, baseline_faces)
            ))
        else:
            scene.extend(resolved_features_to_primitives(get_box_body_baseline_unfolded_features(
                model_name, result.width, result.height, zl1, zl2, zr1, zr2, z_comp, w, d, t, fw,
            )))
    check_fold_values = None
    if fold_profile:
        check_fold_values = tuple(float(getattr(row, "length", 0.0)) for row in fold_profile)
    scene.extend(build_box_body_check(
        total_length=result.width, total_height=result.height, panel_width=w, panel_depth=d,
        thickness=t, fold_values=check_fold_values,
        left_outer=zl1, left_inner=zl2, right_inner=zr2, right_outer=zr1,
        frame_width=fw,
    ))
    return scene


def export_box_body_dxf(filepath, W_val=None, H_val=None, D_val=None, T_val=None, FW_val=None,
                         zl1=None, zl2=None, zr1=None, zr2=None, z_comp=None, draw_stock=None,
                         model_name=None, user_features=None, face_features=None,
                         head_corner_policy=None, tail_corner_policy=None, fold_profile=None):
    """輸出箱身 Z 展開 DXF；parameter adaptation → scene builder → single save path。"""
    w = W_val if W_val is not None else W
    h = H_val if H_val is not None else H
    d = D_val if D_val is not None else D
    t = T_val if T_val is not None else T
    fw = FW_val if FW_val is not None else FW
    zl1 = zl1 if zl1 is not None else zl1_def
    zl2 = zl2 if zl2 is not None else zl2_def
    zr1 = zr1 if zr1 is not None else zr1_def
    zr2 = zr2 if zr2 is not None else zr2_def
    z_comp = z_comp if z_comp is not None else z_comp_def
    scene = _build_box_body_scene(
        w=w, h=h, d=d, t=t, fw=fw, zl1=zl1, zl2=zl2, zr1=zr1, zr2=zr2, z_comp=z_comp,
        draw_stock=(draw_stock if draw_stock is not None else DRAW_STOCK), model_name=model_name,
        user_features=user_features, face_features=face_features,
        head_corner_policy=head_corner_policy, tail_corner_policy=tail_corner_policy,
        fold_profile=fold_profile,
    )
    _save_scene_dxf(filepath, scene)
    print(f"成功輸出箱身 DXF: {filepath}")

from .ae_endcap import (
    _resolve_user_holes,
    _build_end_cap_scene,
    export_end_cap_dxf,
    _build_unknown_end_cap_scene,
    export_unknown_end_cap_dxf,
    get_baseline_list,
    baseline_root_path,
    baseline_expected_path,
    baseline_part_path,
    baseline_hole_catalog_root_path,
    indicator_shared_baseline_model_name,
    indicator_shared_baseline_part_path,
    indicator_shared_baseline_source_label,
    has_baseline_part,
    baseline_source_label,
    get_end_cap_contour_points,
    get_stretched_end_cap_data,
    _build_stretched_end_cap_scene,
    export_stretched_end_cap_dxf,
)

def get_stretched_box_body_data(model_name, W_val, H_val, D_val, T_val, FW_val=None, z_comp_val=None):
    """Compatibility facade for legacy Box Body baseline adaptation."""
    return _baseline_scene_adapters.get_stretched_box_body_data(
        model_name, W_val, H_val, D_val, T_val, FW_val, z_comp_val,
        baseline_part_path=baseline_part_path,
        baseline_expected_path=baseline_expected_path,
        source_loader=(globals().get("load_baseline_dxf_source") or ezdxf.readfile),
        chain_builder=_make_box_body_chain,
    )


def export_stretched_box_body_dxf(filepath, model_name, W_val=None, H_val=None, D_val=None, T_val=None, FW_val=None, z_comp_val=None, draw_stock=None, user_features=None, face_features=None, head_corner_policy=None, tail_corner_policy=None):
    """
    基於基準檔拉伸，輸出箱身的 DXF 檔案。
    由於箱身已全面公式化，不採用基準自適應拉伸，此處將自動調用公式化導出。
    """
    try:
        scene_data_z = get_stretched_box_body_data(model_name, W_val or 500, H_val or 500, D_val or 150, T_val or 2.0)
        pz = scene_data_z.params
        zl1 = pz.get('zl1', None)
        zl2 = pz.get('zl2', None)
        zr1 = pz.get('zr1', None)
        zr2 = pz.get('zr2', None)
        z_comp = pz.get('z_comp', None)
    except Exception:
        # 如果解析箱身基準檔失敗，使用合理的預設折彎值
        zl1, zl2, zr1, zr2, z_comp = 15.0, 20.0, 15.0, 20.0, -10.0
        
    export_box_body_dxf(
        filepath, W_val, H_val, D_val, T_val, FW_val,
        zl1, zl2, zr1, zr2, z_comp, draw_stock,
        model_name=model_name, user_features=user_features, face_features=face_features,
        head_corner_policy=head_corner_policy, tail_corner_policy=tail_corner_policy,
    )
    print(f"成功輸出公式化箱身 DXF: {filepath}")


def _make_base_plate_geometry(W_val, H_val, T_val, shrink_top, shrink_bottom, shrink_left, shrink_right, bend):
    result = build_base_plate_result(
        w=W_val, h=H_val, t=T_val,
        shrink_top=shrink_top, shrink_bottom=shrink_bottom,
        shrink_left=shrink_left, shrink_right=shrink_right, bend=bend,
    )
    return list(result.outline), list(result.bends), result.topology


def _build_base_plate_scene(*, w, h, t, st, sb, sl, sr, bend, draw_stock=False, user_features=None,
                            structural_result=None):
    """Build complete Base Plate DrawingScene without DXF serialization."""
    result = structural_result or build_base_plate_result(
        w=w, h=h, t=t, shrink_top=st, shrink_bottom=sb,
        shrink_left=sl, shrink_right=sr, bend=bend,
    )
    scene = DrawingScene()
    if draw_stock:
        scene.add(build_stock_outline(result.width, result.height))
    scene.extend(structural_result_to_primitives(result))
    _append_surface_user_features(scene, result, user_features, "base_plate")
    scene.extend(resolved_features_to_primitives(
        resolve_base_plate_mounting_holes(result.width, result.height, bend=bend)
    ))
    scene.add(build_base_plate_datum(
        w=w, h=h, shrink_left=sl, shrink_bottom=sb, bend=bend,
    ))
    scene.extend(build_base_plate_check(
        total_width=result.width, total_height=result.height, bend=bend,
        shrink_top=st, shrink_bottom=sb, shrink_left=sl, shrink_right=sr,
    ))
    return scene


def export_base_plate_dxf(filepath, W_val=None, H_val=None, T_val=None,
                          shrink_top=None, shrink_bottom=None, shrink_left=None, shrink_right=None,
                          bend=None, draw_stock=None, user_features=None):
    """輸出底板展開 DXF；parameter adaptation → scene builder → single save path。"""
    w = W_val if W_val is not None else W
    h = H_val if H_val is not None else H
    t = T_val if T_val is not None else T
    st = shrink_top if shrink_top is not None else base_plate_shrink_def
    sb = shrink_bottom if shrink_bottom is not None else base_plate_shrink_def
    sl = shrink_left if shrink_left is not None else base_plate_shrink_def
    sr = shrink_right if shrink_right is not None else base_plate_shrink_def
    bend = bend if bend is not None else base_plate_bend_def
    scene = _build_base_plate_scene(
        w=w, h=h, t=t, st=st, sb=sb, sl=sl, sr=sr, bend=bend,
        draw_stock=(draw_stock if draw_stock is not None else DRAW_STOCK),
        user_features=user_features,
    )
    _save_scene_dxf(filepath, scene)
    print(f"成功輸出底板 DXF: {filepath}")


def export_unknown_base_plate_dxf(filepath, *, corner_policy, W_val=None, H_val=None, T_val=None,
                                  shrink_top=None, shrink_bottom=None, shrink_left=None, shrink_right=None,
                                  bend=None, draw_stock=None, user_features=None):
    w = W_val if W_val is not None else W
    h = H_val if H_val is not None else H
    t = T_val if T_val is not None else T
    st = shrink_top if shrink_top is not None else base_plate_shrink_def
    sb = shrink_bottom if shrink_bottom is not None else base_plate_shrink_def
    sl = shrink_left if shrink_left is not None else base_plate_shrink_def
    sr = shrink_right if shrink_right is not None else base_plate_shrink_def
    bend = bend if bend is not None else base_plate_bend_def
    result = build_unknown_base_plate_result(
        w=w, h=h, t=t, shrink_top=st, shrink_bottom=sb,
        shrink_left=sl, shrink_right=sr, bend=bend, corner_policy=corner_policy,
    )
    scene = _build_base_plate_scene(
        w=w, h=h, t=t, st=st, sb=sb, sl=sl, sr=sr, bend=bend,
        draw_stock=(draw_stock if draw_stock is not None else DRAW_STOCK),
        user_features=user_features, structural_result=result,
    )
    _save_scene_dxf(filepath, scene)
    print(f"成功輸出自訂底板 DXF: {filepath}")


def export_part_dxf(part_type, filepath, **kwargs):
    """Canonical dispatcher for supported WHD part exporters."""
    key = str(part_type).strip().lower().replace('-', '_').replace(' ', '_')
    if key in {'tail', 'end_cap_tail', 'endcap_tail'}:
        kwargs = dict(kwargs)
        kwargs['is_tail'] = True
        return export_end_cap_dxf(filepath, **kwargs)

    aliases = {
        'door': export_door_dxf, 'door_panel': export_door_dxf,
        'box': export_box_body_dxf, 'box_body': export_box_body_dxf, 'body': export_box_body_dxf,
        'end_cap': export_end_cap_dxf, 'endcap': export_end_cap_dxf, 'head': export_end_cap_dxf,
        'base': export_base_plate_dxf, 'base_plate': export_base_plate_dxf,
        'indicator': export_indicator_box_dxf, 'indicator_box': export_indicator_box_dxf,
        'stretched_end_cap': export_stretched_end_cap_dxf,
        'stretched_door': export_stretched_door_dxf,
        'stretched_box_body': export_stretched_box_body_dxf,
    }
    exporter = aliases.get(key)
    if exporter is None:
        raise ValueError(f"Unsupported part type: {part_type}")
    return exporter(filepath, **kwargs)
