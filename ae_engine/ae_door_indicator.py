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

from .ae_endcap import (
    baseline_expected_path,
    baseline_part_path,
    indicator_shared_baseline_model_name,
    indicator_shared_baseline_part_path,
)

def _make_door_geometry(W_val=None, H_val=None, T_val=None, FW_val=None,
                        gap_w=None, gap_h=None,
                        fold_left=None, fold_right=None,
                        fold_top=None, fold_bottom=None, frame_edges=None):
    t = T_val if T_val is not None else T
    fl = fold_left if fold_left is not None else door_fold_left_def
    fr = fold_right if fold_right is not None else door_fold_right_def
    ft = fold_top if fold_top is not None else door_fold_top_def
    fb = fold_bottom if fold_bottom is not None else door_fold_bottom_def
    result = build_door_result(
        w=W_val if W_val is not None else W,
        h=H_val if H_val is not None else H,
        t=t, fw=FW_val if FW_val is not None else FW,
        gap_w=gap_w if gap_w is not None else door_gap_w_def,
        gap_h=gap_h if gap_h is not None else door_gap_h_def,
        fold_left=fl, fold_right=fr, fold_top=ft, fold_bottom=fb,
        frame_edges=frame_edges,
    )
    return list(result.outline), list(result.bends), result.topology


def _append_surface_user_features(scene, result, features, surface_id):
    if not features:
        return
    surface = feature_surface_from_structural_result(surface_id, result)
    scene.extend(resolved_features_to_primitives(
        resolve_surface_features(surface, features, result.width, result.height)
    ))


def _surface_from_scene_primary_cutting(scene, surface_id):
    """Resolve the largest closed CUTTING outline from a DrawingScene.

    A manufacturing contour may arrive either as one closed PolylinePrimitive or
    as exploded LinePrimitive entities whose endpoints form a closed loop.  The
    latter is common in factory baseline DXFs and is geometrically just as valid.
    """
    tolerance = 1e-4

    def point_key(point):
        return (
            int(round(float(point.x) / tolerance)),
            int(round(float(point.y) / tolerance)),
        )

    def polygon_area(points):
        pts = tuple(points)
        if len(pts) < 3:
            return 0.0
        return abs(sum(
            float(pts[i].x) * float(pts[(i + 1) % len(pts)].y)
            - float(pts[(i + 1) % len(pts)].x) * float(pts[i].y)
            for i in range(len(pts))
        )) / 2.0

    candidates = []
    line_segments = []
    adjacency = {}

    for primitive in scene.primitives:
        if str(getattr(primitive, 'layer', '')).upper() != 'CUTTING':
            continue
        if isinstance(primitive, PolylinePrimitive) and primitive.closed and len(primitive.points) >= 3:
            candidates.append(tuple(primitive.points))
        elif isinstance(primitive, LinePrimitive):
            k1 = point_key(primitive.p1)
            k2 = point_key(primitive.p2)
            if k1 == k2:
                continue
            index = len(line_segments)
            line_segments.append((primitive.p1, primitive.p2, k1, k2))
            adjacency.setdefault(k1, []).append(index)
            adjacency.setdefault(k2, []).append(index)

    # Find connected LINE components.  A simple closed contour has degree 2 at
    # every endpoint; components with branches/gaps are deliberately rejected.
    seen_segments = set()
    for seed in range(len(line_segments)):
        if seed in seen_segments:
            continue

        component = set()
        stack = [seed]
        vertices = set()
        while stack:
            index = stack.pop()
            if index in component:
                continue
            component.add(index)
            _p1, _p2, k1, k2 = line_segments[index]
            vertices.update((k1, k2))
            for key in (k1, k2):
                stack.extend(i for i in adjacency.get(key, ()) if i not in component)
        seen_segments.update(component)

        if len(component) < 3 or any(len(adjacency.get(key, ())) != 2 for key in vertices):
            continue

        start_index = min(component)
        p1, _p2, start_key, _ = line_segments[start_index]
        points = [p1]
        current_key = start_key
        current_index = start_index
        used = set()
        closed = False

        while current_index not in used:
            used.add(current_index)
            a, b, k1, k2 = line_segments[current_index]
            if current_key == k1:
                next_point, next_key = b, k2
            elif current_key == k2:
                next_point, next_key = a, k1
            else:
                break

            if next_key == start_key:
                closed = True
                break

            points.append(next_point)
            current_key = next_key
            next_segments = [
                i for i in adjacency.get(current_key, ())
                if i in component and i not in used
            ]
            if len(next_segments) != 1:
                break
            current_index = next_segments[0]

        if closed and used == component and len(points) >= 3:
            candidates.append(tuple(points))

    candidates = [points for points in candidates if polygon_area(points) > 0.0]
    if not candidates:
        raise ValueError(f"no primary CUTTING outline for feature surface: {surface_id}")

    outline = max(candidates, key=polygon_area)
    return feature_surface_from_outline(surface_id, outline)


def feature_surface_from_drawing_scene(surface_id, scene):
    """Public scene adapter shared by AE export and the GUI hole editor."""
    return _surface_from_scene_primary_cutting(scene, surface_id)


def _build_door_scene(*, w, h, t, fw, gw, gh, fl, fr, ft, fb,
                      draw_stock=False, indicator_hole=None, door_indicator=None,
                      door_indicator_offset=None, is_box_dist=False, user_features=None,
                      frame_edges=None, structural_result=None):
    """Build the complete Door DrawingScene without any DXF dependency."""
    result = structural_result or build_door_result(
        w=w, h=h, t=t, fw=fw, gap_w=gw, gap_h=gh,
        fold_left=fl, fold_right=fr, fold_top=ft, fold_bottom=fb,
        frame_edges=frame_edges,
    )
    finished_w, finished_h = calculate_door_finished_size(
        w, h, fw, gw, gh, t, frame_edges=frame_edges
    )
    scene = DrawingScene()
    if draw_stock:
        scene.add(build_stock_outline(result.width, result.height))
    scene.extend(structural_result_to_primitives(result))
    scene.extend(build_door_check(
        total_width=result.width, total_height=result.height,
        finished_w=finished_w, finished_h=finished_h, thickness=t,
        fold_left=fl, fold_right=fr, fold_top=ft, fold_bottom=fb,
    ))
    _append_surface_user_features(scene, result, user_features, "door")
    if indicator_hole is not None:
        hw, hh = indicator_hole
        hole_offset = Vec2(*(door_indicator_offset or (0.0, 0.0)))
        cx = fl + finished_w / 2.0 + hole_offset.x
        cy = fb + finished_h / 2.0 + hole_offset.y
        scene.add(PolylinePrimitive(
            points=(Vec2(cx-hw/2.0, cy-hh/2.0), Vec2(cx+hw/2.0, cy-hh/2.0),
                    Vec2(cx+hw/2.0, cy+hh/2.0), Vec2(cx-hw/2.0, cy+hh/2.0)),
            layer='CUTTING', closed=True, color=3,
        ))
    if door_indicator is not None:
        context = DoorIndicatorContext(
            finished_width=finished_w, finished_height=finished_h,
            left_fold=fl, bottom_fold=fb,
        )
        layout = resolve_door_indicator_layout(
            context, tuple(int(v) for v in door_indicator),
            Vec2(*(door_indicator_offset or (0.0, 0.0))),
        )
        scene.extend(resolved_features_to_primitives(layout.features))
        scene.extend(build_door_indicator_check(measure_door_indicator_position(
            layout, context, frame_width=fw, thickness=t, use_box_distance=is_box_dist,
            frame_edges=frame_edges, gap_w=gw, gap_h=gh,
        )))
    return scene


def export_door_dxf(filepath, W_val=None, H_val=None, T_val=None, FW_val=None,
                    gap_w=None, gap_h=None,
                    fold_left=None, fold_right=None,
                    fold_top=None, fold_bottom=None,
                    draw_stock=None, indicator_hole=None, door_indicator=None, door_indicator_offset=None,
                    is_box_dist=False, user_features=None, frame_edges=None):
    """輸出門展開 DXF；parameter adaptation → scene builder → single save path。"""
    w = W_val if W_val is not None else W
    h = H_val if H_val is not None else H
    t = T_val if T_val is not None else T
    fw = FW_val if FW_val is not None else FW
    gw = gap_w if gap_w is not None else door_gap_w_def
    gh = gap_h if gap_h is not None else door_gap_h_def
    fl = fold_left if fold_left is not None else door_fold_left_def
    fr = fold_right if fold_right is not None else door_fold_right_def
    ft = fold_top if fold_top is not None else door_fold_top_def
    fb = fold_bottom if fold_bottom is not None else door_fold_bottom_def
    scene = _build_door_scene(
        w=w, h=h, t=t, fw=fw, gw=gw, gh=gh, fl=fl, fr=fr, ft=ft, fb=fb,
        draw_stock=(draw_stock if draw_stock is not None else DRAW_STOCK),
        indicator_hole=indicator_hole, door_indicator=door_indicator,
        door_indicator_offset=door_indicator_offset, is_box_dist=is_box_dist,
        user_features=user_features, frame_edges=frame_edges,
    )
    blank_w, _blank_h = calculate_door_blank_size(
        w, h, t, fw, gw, gh, fl, fr, ft, fb, frame_edges=frame_edges,
    )
    export_scene = mirror_drawing_scene_x(scene, 0.0, blank_w)
    _save_scene_dxf(filepath, export_scene)
    print(f"成功輸出門 DXF: {filepath}")


def export_unknown_door_dxf(filepath, *, corner_policy, W_val=None, H_val=None, T_val=None, FW_val=None,
                            gap_w=None, gap_h=None, fold_left=None, fold_right=None,
                            fold_top=None, fold_bottom=None, draw_stock=None, indicator_hole=None,
                            door_indicator=None, door_indicator_offset=None, is_box_dist=False,
                            user_features=None, frame_edges=None):
    """Unknown/manual Door exporter. Existing Vault exporter never receives corner_policy."""
    w = W_val if W_val is not None else W
    h = H_val if H_val is not None else H
    t = T_val if T_val is not None else T
    fw = FW_val if FW_val is not None else FW
    gw = gap_w if gap_w is not None else door_gap_w_def
    gh = gap_h if gap_h is not None else door_gap_h_def
    fl = fold_left if fold_left is not None else door_fold_left_def
    fr = fold_right if fold_right is not None else door_fold_right_def
    ft = fold_top if fold_top is not None else door_fold_top_def
    fb = fold_bottom if fold_bottom is not None else door_fold_bottom_def
    result = build_unknown_door_result(
        w=w, h=h, t=t, fw=fw, gap_w=gw, gap_h=gh,
        fold_left=fl, fold_right=fr, fold_top=ft, fold_bottom=fb,
        corner_policy=corner_policy, frame_edges=frame_edges,
    )
    scene = _build_door_scene(
        w=w, h=h, t=t, fw=fw, gw=gw, gh=gh, fl=fl, fr=fr, ft=ft, fb=fb,
        draw_stock=(draw_stock if draw_stock is not None else DRAW_STOCK),
        indicator_hole=indicator_hole, door_indicator=door_indicator,
        door_indicator_offset=door_indicator_offset, is_box_dist=is_box_dist,
        user_features=user_features, frame_edges=frame_edges, structural_result=result,
    )
    blank_w, _blank_h = calculate_door_blank_size(
        w, h, t, fw, gw, gh, fl, fr, ft, fb, frame_edges=frame_edges,
    )
    export_scene = mirror_drawing_scene_x(scene, 0.0, blank_w)
    _save_scene_dxf(filepath, export_scene)
    print(f"成功輸出自訂門 DXF: {filepath}")


def indicator_small_door_window_geometry(layer_groups, *, total_width, total_height,
                                               fold_left, fold_right, fold_top, fold_bottom,
                                               thickness=2.0):
    """Return the shared small-door viewing-window geometry.

    The sample DXF coordinates are not treated as permanent placement rules.
    The window center follows the *actual generated indicator-lamp pattern* on
    the shared box.  Because the small door is centered in the box clear opening
    (the configured equal gap on every side), the lamp-pattern offset from the box center can
    be transferred directly to the small-door finished-face center.

    One-group vs multi-group keeps only the proven sample shape rules:
    one group uses a 100 mm wide / R50 window; multi-group uses 30 mm
    horizontal clearance around the lamp-center span / R70.  Vertical clearance
    is 30 mm above and below the lamp-center span for all layouts.
    """
    groups = tuple(int(v) for v in layer_groups)
    if not groups or any(v <= 0 for v in groups):
        raise ValueError("指示燈小門視窗需要至少一層且每層組數必須大於 0")

    box = get_indicator_box_data(groups, float(thickness))
    lamps = [
        primitive for primitive in box.scene.primitives
        if isinstance(primitive, CirclePrimitive)
        and primitive.layer == 'CUTTING'
        and abs(float(primitive.radius) - 15.5) <= 1e-6
    ]
    if not lamps:
        raise ValueError("指示燈盒沒有可用的指示燈孔，無法定位小門視窗")

    lamp_min_x = min(float(p.center.x) for p in lamps)
    lamp_max_x = max(float(p.center.x) for p in lamps)
    lamp_min_y = min(float(p.center.y) for p in lamps)
    lamp_max_y = max(float(p.center.y) for p in lamps)
    lamp_center_x = (lamp_min_x + lamp_max_x) / 2.0
    lamp_center_y = (lamp_min_y + lamp_max_y) / 2.0
    lamp_span_x = lamp_max_x - lamp_min_x
    lamp_span_y = lamp_max_y - lamp_min_y

    box_center_x = float(box.params['w']) / 2.0
    box_center_y = float(box.params['h']) / 2.0
    pattern_offset_x = lamp_center_x - box_center_x
    pattern_offset_y = lamp_center_y - box_center_y

    total_w = float(total_width)
    total_h = float(total_height)
    fl = float(fold_left)
    fr = float(fold_right)
    ft = float(fold_top)
    fb = float(fold_bottom)
    face_center_x = fl + (total_w - fl - fr) / 2.0
    face_center_y = fb + (total_h - fb - ft) / 2.0

    g_max = max(groups)
    width = 100.0 if g_max == 1 else lamp_span_x + 60.0
    height = lamp_span_y + 60.0
    radius = 50.0 if g_max == 1 else 70.0
    center_x = face_center_x + pattern_offset_x
    center_y = face_center_y + pattern_offset_y

    return {
        'center_x': center_x, 'center_y': center_y,
        'width': width, 'height': height, 'radius': radius,
        'x_min': center_x - width / 2.0, 'x_max': center_x + width / 2.0,
        'y_min': center_y - height / 2.0, 'y_max': center_y + height / 2.0,
        'pattern_offset_x': pattern_offset_x, 'pattern_offset_y': pattern_offset_y,
    }


def get_stretched_door_data(model_name, W_val, H_val, T_val, FW_val=None,
                            gap_w_val=None, gap_h_val=None,
                            fl_val=None, fr_val=None, ft_val=None, fb_val=None, indicator_hole=None, door_indicator=None, door_indicator_offset=None,
                            frame_edges=None, indicator_window_groups=None, corner_policy=None,
                            nameplate_center_datum_top=None):
    """Backward-compatible facade for baseline Door scene adaptation."""
    shared_baseline_resolver = None
    if indicator_window_groups is not None:
        shared_baseline_resolver = indicator_shared_baseline_part_path
    return _baseline_scene_adapters.get_stretched_door_data(
        model_name, W_val, H_val, T_val, FW_val,
        gap_w_val, gap_h_val, fl_val, fr_val, ft_val, fb_val,
        indicator_hole, door_indicator, door_indicator_offset,
        frame_edges, indicator_window_groups, corner_policy, nameplate_center_datum_top,
        deps={
            "CirclePrimitive": CirclePrimitive,
            "DoorIndicatorContext": DoorIndicatorContext,
            "DrawingScene": DrawingScene,
            "FW": FW,
            "SceneData": SceneData,
            "Vec2": Vec2,
            "_baseline_cutting_bounds": _baseline_cutting_bounds,
            "_baseline_entity_layer": _baseline_entity_layer,
            "_iter_baseline_entities": _iter_baseline_entities,
            "_make_door_geometry": _make_door_geometry,
            "baseline_expected_path": baseline_expected_path,
            "baseline_part_path": baseline_part_path,
            "build_door_result": build_door_result,
            "build_finished_reference_guide": build_finished_reference_guide,
            "build_unknown_door_result": build_unknown_door_result,
            "calculate_door_finished_size": calculate_door_finished_size,
            "door_fold_bottom_def": door_fold_bottom_def,
            "door_fold_left_def": door_fold_left_def,
            "door_fold_right_def": door_fold_right_def,
            "door_fold_top_def": door_fold_top_def,
            "door_gap_h_def": door_gap_h_def,
            "door_gap_w_def": door_gap_w_def,
            "identify_door_baseline_nameplate_circles": identify_door_baseline_nameplate_circles,
            "indicator_shared_baseline_part_path": shared_baseline_resolver,
            "indicator_small_door_window_geometry": indicator_small_door_window_geometry,
            "resolve_door_indicator_layout": resolve_door_indicator_layout,
            "source_loader": (globals().get("load_baseline_dxf_source") or ezdxf.readfile),
        },
    )


def export_stretched_door_dxf(filepath, model_name, W_val=None, H_val=None, T_val=None, FW_val=None,
                              gap_w_val=None, gap_h_val=None,
                              fl_val=None, fr_val=None, ft_val=None, fb_val=None, draw_stock=None, indicator_hole=None, door_indicator=None, door_indicator_offset=None,
                              is_box_dist=False, user_features=None, frame_edges=None, indicator_window_groups=None, corner_policy=None):
    """基於基準檔拉伸門；baseline mapper 直接產生 DrawingScene。"""
    w = W_val if W_val is not None else W
    h = H_val if H_val is not None else H
    t = T_val if T_val is not None else T
    fw = FW_val if FW_val is not None else FW
    gw = gap_w_val if gap_w_val is not None else door_gap_w_def
    gh = gap_h_val if gap_h_val is not None else door_gap_h_def
    scene_data = get_stretched_door_data(
        model_name, w, h, t, fw, gap_w_val, gap_h_val,
        fl_val, fr_val, ft_val, fb_val, indicator_hole, door_indicator, door_indicator_offset,
        frame_edges=frame_edges, indicator_window_groups=indicator_window_groups, corner_policy=corner_policy,
    )
    p = scene_data.params
    total_width, total_height = p['total_width'], p['total_depth']
    finished_w, finished_h = p['finished_w'], p['finished_h']
    fl_n, fr_n = p['door_fold_l'], p['door_fold_r']
    ft_n, fb_n = p['door_fold_t'], p['door_fold_b']

    scene = DrawingScene()
    if draw_stock if draw_stock is not None else DRAW_STOCK:
        scene.add(build_stock_outline(total_width, total_height))
    scene.extend(scene_data.scene.primitives)
    if user_features:
        surface = _surface_from_scene_primary_cutting(scene_data.scene, "stretched_door")
        scene.extend(resolved_features_to_primitives(
            resolve_surface_features(surface, user_features, total_width, total_height)
        ))
    scene.extend(build_door_check(
        total_width=total_width, total_height=total_height,
        finished_w=finished_w, finished_h=finished_h, thickness=t,
        fold_left=fl_n, fold_right=fr_n, fold_top=ft_n, fold_bottom=fb_n,
    ))
    if door_indicator is not None:
        layout = scene_data.metadata.get('door_indicator_layout')
        if layout is not None:
            position = measure_door_indicator_position(
                layout, layout.context, frame_width=fw, thickness=t,
                use_box_distance=is_box_dist, frame_edges=frame_edges, gap_w=gw, gap_h=gh,
            )
            scene.extend(build_door_indicator_check(position))

    export_scene = mirror_drawing_scene_x(scene, 0.0, total_width)
    _save_scene_dxf(filepath, export_scene)
    print(f"成功輸出基準拉伸門 DXF: {filepath}")


def _make_indicator_box_geometry(total_width, total_height, T_val=2.0, fold=None):
    result = build_indicator_box_result(
        total_width=total_width, total_height=total_height,
        t=T_val, fold=indicator_box_fold_def if fold is None else fold,
    )
    return list(result.outline), list(result.bends), result.topology


def get_indicator_box_data(layer_groups, T_val=2.0, corner_policy=None):
    """
    計算指示燈盒子的幾何資料
    直的 3 個指示燈為一組 (每一層的高度為 3 個指示燈，層與層之間的燈孔跨距是 100)
    layer_groups: 列表，例如 [2, 3]，長度代表層數 L，每個元素代表該層的組數 g
    展開總尺寸公式：
    W = 171 + 90 * (g_max - 1) + 135
    H = 280.0 * (layers - 1) + 445.0 (一層高度固定 445.0，每多一層增加 280.0)
    上下左右使用同一折邊尺寸（預設 49 mm），角部 X 避位為 fold-T
    每一層、每一列的最上方那一顆指示燈孔的上方 48mm 處均有一對名牌安裝孔 (間距 44)
    每一層均有線槽打標孔，其 X 座標一律對齊最多組的那一層 (居中對稱分佈)，第一層的打標孔位於最上面位置 (Y=378.5)
    """
    layers = len(layer_groups)
    g_max = max(layer_groups) if layer_groups else 1
    
    if g_max == 1:
        W_val = 326.0
    else:
        W_val = 171.0 + 90.0 * (g_max - 1) + 135.0
    H_val = 280.0 * max(0, layers - 1) + 445.0
    
    scene = DrawingScene()
    params = {
        'w': W_val,
        'h': H_val,
        'layer_groups': layer_groups,
        't': T_val,
    }
    
    # 1-2. 主 CUTTING / BEND：既有模式固定 C02；自訂才接受手選 CornerType。
    if corner_policy is None:
        structural_result = build_indicator_box_result(
            total_width=W_val, total_height=H_val, t=T_val, fold=indicator_box_fold_def
        )
    else:
        structural_result = build_unknown_indicator_box_result(
            total_width=W_val, total_height=H_val, t=T_val, fold=indicator_box_fold_def,
            corner_policy=corner_policy,
        )
    scene.add_polyline([(p.x, p.y) for p in structural_result.outline], layer='CUTTING', closed=True)
    for segment in structural_result.bends:
        scene.add_line(segment.p1, segment.p2, layer='BEND')
    
    # 3. 逐層生成指示燈與名牌安裝孔 (ly=0 為最頂層，ly=layers-1 為最底層)
    for ly in range(layers):
        g_current = layer_groups[ly]
        if g_current <= 0:
            continue
        
        # ly=0 對應最頂層 (Y 最大)，ly=layers-1 對應最底層 (Y 最小)
        layer_y_start = 133.5 + 280.0 * (layers - 1 - ly)
            
        for i in range(g_current):
            if g_max == 1:
                cx = 191.0
            else:
                cx = 171.0 + 90.0 * i
            
            # 指示燈 (直的3個)
            for j in range(3):
                cy = layer_y_start + 90.0 * j
                scene.add_circle((cx, cy), 15.5, layer='CUTTING')
                
            # 每一組 (每一列) 的最上方那一顆指示燈 (j=2) 的上方 48mm 處生成一對名牌安裝孔
            y_top_light = layer_y_start + 180.0
            scene.add_circle((cx - 22.0, y_top_light + 48.0), 1.6, layer='CUTTING')
            scene.add_circle((cx + 22.0, y_top_light + 48.0), 1.6, layer='CUTTING')
            
    # 4. 計算統一對齊的線槽打標孔 X 座標 (使用最多組的 g_max 來計算)
    if g_max <= 1:
        hc = 1
    elif g_max <= 3:
        hc = 2
    elif g_max <= 5:
        hc = 3
    else:
        hc = 4
        
    x_left_light = 171.0
    x_right_light = 171.0 + 90.0 * max(0, g_max - 1)
    if hc > 1:
        max_pitch = (x_right_light - x_left_light) / (hc - 1)
        hp = max(50.0, float(int(max_pitch // 50) * 50))
    else:
        hp = 150.0
        
    marking_xs = []
    for k in range(hc):
        if hc > 1:
            x_mid = (x_left_light + x_right_light) / 2.0
            cx = x_mid - (hc - 1) * hp / 2.0 + hp * k
        else:
            cx = 191.0
        marking_xs.append(cx)
        
    # 5. 線槽打標孔 (帶水平一字線，每一層在對應的 Y=178.5+280*(layers-1-ly)，X 統一對齊 g_max)
    for ly in range(layers):
        hy = 178.5 + 280.0 * (layers - 1 - ly)
        for cx in marking_xs:
            if cx < W_val - 49.0:
                scene.add_circle((cx, hy), 2.0, layer='MARKING')
                scene.add_line((cx - 2.0, hy), (cx + 2.0, hy), layer='MARKING')
        
    # 6. 掛孔 (半徑 3.2，CUTTING) - 固定在右側邊緣內 60 處
    if W_val - 60.0 > 49.0:
        for cy in [5.5, H_val - 5.5]:
            scene.add_circle((W_val - 60.0, cy), 3.2, layer='CUTTING')
        

    return SceneData(scene=scene, params=params)


def get_stretched_indicator_box_data(model_name, layer_groups, T_val=2.0, corner_policy=None):
    """Backward-compatible facade for baseline Indicator Box scene adaptation."""
    return _baseline_scene_adapters.get_stretched_indicator_box_data(
        model_name, layer_groups, T_val, corner_policy,
        deps={
            "CirclePrimitive": CirclePrimitive,
            "DrawingScene": DrawingScene,
            "LinePrimitive": LinePrimitive,
            "SceneData": SceneData,
            "_surface_from_scene_primary_cutting": _surface_from_scene_primary_cutting,
            "get_indicator_box_data": get_indicator_box_data,
            "indicator_box_fold_def": indicator_box_fold_def,
            "indicator_shared_baseline_model_name": indicator_shared_baseline_model_name,
            "indicator_shared_baseline_part_path": indicator_shared_baseline_part_path,
            "source_loader": (globals().get("load_baseline_dxf_source") or ezdxf.readfile),
        },
    )


def _build_stretched_indicator_box_scene(model_name, layer_groups, T_val=2.0, draw_stock=False,
                                          user_features=None, corner_policy=None):
    data = get_stretched_indicator_box_data(
        model_name, layer_groups, T_val, corner_policy=corner_policy
    )
    width = float(data.params['w']); height = float(data.params['h'])
    scene = DrawingScene()
    if draw_stock:
        scene.add(build_stock_outline(width, height))
    scene.extend(data.scene.primitives)
    if user_features:
        surface = _surface_from_scene_primary_cutting(data.scene, 'indicator_box')
        scene.extend(resolved_features_to_primitives(
            resolve_surface_features(surface, user_features, width, height)
        ))
    scene.extend(build_indicator_box_check(
        width, height, group_count=len(tuple(layer_groups)), fold=indicator_box_fold_def,
    ))
    return SceneData(scene=scene, params=dict(data.params), metadata=dict(data.metadata))


def export_stretched_indicator_box_dxf(filepath, model_name, layer_groups, T_val=2.0,
                                        draw_stock=False, user_features=None, corner_policy=None):
    """Export the Indicator Box from baseline contour/fixed features plus current indicator layout."""
    data = _build_stretched_indicator_box_scene(
        model_name, layer_groups, T_val,
        draw_stock=draw_stock, user_features=user_features, corner_policy=corner_policy,
    )
    _save_scene_dxf(filepath, data.scene)
    print(f"成功輸出基準拉伸指示燈盒子 DXF: {filepath}")


def _build_indicator_box_scene(layer_groups, T_val=2.0, draw_stock=False, user_features=None, corner_policy=None):
    """Build complete Indicator Box DrawingScene from SceneData."""
    scene_data = get_indicator_box_data(layer_groups, T_val, corner_policy=corner_policy)
    width = scene_data.params['w']
    height = scene_data.params['h']
    scene = DrawingScene()
    if draw_stock:
        scene.add(build_stock_outline(width, height))
    scene.extend(scene_data.scene.primitives)
    result = (
        build_indicator_box_result(total_width=width, total_height=height, t=T_val, fold=indicator_box_fold_def)
        if corner_policy is None
        else build_unknown_indicator_box_result(
            total_width=width, total_height=height, t=T_val, fold=indicator_box_fold_def,
            corner_policy=corner_policy,
        )
    )
    _append_surface_user_features(scene, result, user_features, "indicator_box")
    scene.extend(build_indicator_box_check(
        width, height, group_count=len(layer_groups), fold=indicator_box_fold_def,
    ))
    return scene


def export_indicator_box_dxf(filepath, layer_groups, T_val=2.0, draw_stock=False, user_features=None, corner_policy=None):
    """輸出指示燈盒 DXF；parameter adaptation → scene builder → single save path。"""
    scene = _build_indicator_box_scene(layer_groups, T_val, draw_stock=draw_stock, user_features=user_features, corner_policy=corner_policy)
    _save_scene_dxf(filepath, scene)
    print(f"成功輸出指示燈盒子 DXF: {filepath}")
