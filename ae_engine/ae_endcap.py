# -*- coding: utf-8 -*-
"""AE EndCap and baseline-resource implementation owner."""
from __future__ import annotations

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

def _resolve_user_holes(holes, geometry, finished_width, finished_depth, *, normalized_head=False):
    """Resolve end-cap user features in the scene's final WYSIWYG orientation.

    Tail features use the normal finished-face mapping.  Head structural geometry is
    normalized by mirroring once, so head user features must be mapped directly into
    that final coordinate frame instead of being added first and mirrored afterward.
    """
    if not holes:
        return []
    context = endcap_feature_context_from_geometry(geometry, finished_width, finished_depth)
    if normalized_head:
        # The mirrored head's finished flat starts where the raw flat's top ends.
        # Keep +Y in the editor pointing +Y in the final scene so edits are WYSIWYG.
        context = EndCapFeatureContext(
            finished_width=context.finished_width,
            finished_depth=context.finished_depth,
            thickness=context.thickness,
            left_fold=context.left_fold,
            right_fold=context.right_fold,
            bottom_fold=float(geometry.total_depth) - context.unfolded_flat_top,
            unfolded_width=context.unfolded_width,
        )
    features = [legacy_hole_to_feature(hole) for hole in holes]
    surface = endcap_finished_feature_surface(
        finished_width, finished_depth, geometry.thickness, surface_id="endcap_finished_face"
    )
    for feature in features:
        if not feature_is_within_surface(surface, feature, finished_width, finished_depth):
            raise ValueError("user feature outside feature surface")
    return resolve_endcap_features(context, features)


def _build_end_cap_scene(*, w, d, t, fw, yl1, yr1, ytop1, ybottom1,
                         x_topology="folded", depth_comp_t=3.0, draw_stock=False, is_tail=False, holes=None,
                         model_name=None, feature_policy=None):
    """Build complete End Cap/Tail DrawingScene without DXF serialization."""
    result = build_endcap_result(
        w=w, d=d, t=t, fw=fw, yl1=yl1, yr1=yr1,
        ytop1=ytop1, ybottom1=ybottom1, x_topology=x_topology,
        relief_config=RELIEF_CONFIG, depth_comp_t=depth_comp_t,
    )
    geometry = result.topology
    relief = calculate_endcap_relief_dimensions(geometry, RELIEF_CONFIG)
    scene = DrawingScene()
    if draw_stock:
        scene.add(build_stock_outline(result.width, result.height))
    scene.extend(structural_result_to_primitives(result))
    fixed_features = resolve_endcap_fixed_features_for_model(
        geometry,
        model_name=model_name,
        relief_config=RELIEF_CONFIG,
        is_tail=is_tail,
        feature_policy=feature_policy,
    )
    scene.extend(resolved_features_to_primitives(fixed_features))
    scene.extend(build_endcap_check(
        geometry=geometry, relief=relief,
        finished_width=w, finished_depth=d, part_label='End Cap (Y)',
    ))
    if not is_tail:
        # Normalize the base head scene once before applying editor-owned features.
        scene = mirror_drawing_scene_y(scene, result.height)
    scene.extend(resolved_features_to_primitives(
        _resolve_user_holes(holes, geometry, w, d, normalized_head=not is_tail)
    ))
    return scene


def export_end_cap_dxf(filepath, W_val=None, H_val=None, D_val=None, T_val=None, FW_val=None,
                        yl1=None, yr1=None, ytop1=None, ybottom1=None, zl1=None, zr1=None,
                        draw_stock=None, is_tail=False, holes=None, model_name=None):
    """輸出封頭尾 Y 展開 DXF；parameter adaptation → scene builder → single save path。"""
    w = W_val if W_val is not None else W
    d = D_val if D_val is not None else D
    t = T_val if T_val is not None else T
    fw = FW_val if FW_val is not None else FW
    yl1 = yl1 if yl1 is not None else yl1_def
    yr1 = yr1 if yr1 is not None else yr1_def
    ytop1 = ytop1 if ytop1 is not None else ytop1_def
    ybottom1 = ybottom1 if ybottom1 is not None else ybottom1_def
    scene = _build_end_cap_scene(
        w=w, d=d, t=t, fw=fw, yl1=yl1, yr1=yr1, ytop1=ytop1, ybottom1=ybottom1,
        draw_stock=(draw_stock if draw_stock is not None else DRAW_STOCK),
        is_tail=is_tail, holes=holes, model_name=model_name,
    )
    _save_scene_dxf(filepath, scene)
    print(f"成功輸出封頭尾 DXF: {filepath}")


def _build_unknown_end_cap_scene(*, w, d, t, fw, yl1, yr1, ytop1, ybottom1,
                                  corner_policy, x_topology="folded", depth_comp_t=3.0,
                                  nominal_yl1=None, nominal_yr1=None,
                                  box_body_formed_fw_left=None, box_body_formed_fw_right=None,
                                  draw_stock=False, is_tail=False, holes=None):
    """Unknown/manual EndCap scene. Vault fixed holes/policies are intentionally excluded."""
    result = build_unknown_endcap_result(
        w=w, d=d, t=t, fw=fw, yl1=yl1, yr1=yr1,
        ytop1=ytop1, ybottom1=ybottom1, corner_policy=corner_policy,
        x_topology=x_topology, depth_comp_t=depth_comp_t,
        nominal_yl1=nominal_yl1, nominal_yr1=nominal_yr1,
        box_body_formed_fw_left=box_body_formed_fw_left,
        box_body_formed_fw_right=box_body_formed_fw_right,
    )
    geometry = result.topology
    scene = DrawingScene()
    if draw_stock:
        scene.add(build_stock_outline(result.width, result.height))
    scene.extend(structural_result_to_primitives(result))
    if not is_tail:
        scene = mirror_drawing_scene_y(scene, result.height)
    scene.extend(resolved_features_to_primitives(
        _resolve_user_holes(holes, geometry, w, d, normalized_head=not is_tail)
    ))
    label = 'Unknown Tail' if is_tail else 'Unknown End Cap'
    scene.add(TextPrimitive(
        f"W = {result.width:.2f} mm\nH = {result.height:.2f} mm\nPart: {label}\nCornerType: manual",
        Vec2(result.width / 2.0, result.height / 2.0), 'CHECK', 12.0, 5, 2,
    ))
    return scene


def export_unknown_end_cap_dxf(filepath, *, corner_policy, W_val=None, H_val=None, D_val=None,
                               T_val=None, FW_val=None, yl1=None, yr1=None, ytop1=None, ybottom1=None,
                               draw_stock=None, is_tail=False, holes=None):
    w = W_val if W_val is not None else W
    d = D_val if D_val is not None else D
    t = T_val if T_val is not None else T
    fw = FW_val if FW_val is not None else FW
    yl1 = yl1 if yl1 is not None else yl1_def
    yr1 = yr1 if yr1 is not None else yr1_def
    ytop1 = ytop1 if ytop1 is not None else ytop1_def
    ybottom1 = ybottom1 if ybottom1 is not None else ybottom1_def
    scene = _build_unknown_end_cap_scene(
        w=w, d=d, t=t, fw=fw, yl1=yl1, yr1=yr1, ytop1=ytop1, ybottom1=ybottom1,
        corner_policy=corner_policy,
        draw_stock=(draw_stock if draw_stock is not None else DRAW_STOCK),
        is_tail=is_tail, holes=holes,
    )
    _save_scene_dxf(filepath, scene)
    print(f"成功輸出自訂封頭尾 DXF: {filepath}")


def get_baseline_list():
    """Backward-compatible facade for baseline model discovery."""
    return _baseline_resources.get_baseline_list(get_resource_path)


def baseline_root_path():
    """Backward-compatible facade for the baseline resource root."""
    return _baseline_resources.baseline_root_path(get_resource_path)


def baseline_expected_path(model_name, filename):
    """Backward-compatible facade for an expected baseline-part path."""
    return _baseline_resources.baseline_expected_path(
        get_resource_path, model_name, filename
    )


def baseline_part_path(model_name, filename):
    """Backward-compatible facade for an existing baseline-part path."""
    return _baseline_resources.baseline_part_path(
        get_resource_path, model_name, filename
    )


def baseline_hole_catalog_root_path():
    """Backward-compatible facade for the shared hole-catalog root."""
    return _baseline_resources.baseline_hole_catalog_root_path(get_resource_path)


def indicator_shared_baseline_model_name():
    """Backward-compatible facade for shared indicator baseline discovery."""
    return _baseline_resources.indicator_shared_baseline_model_name(
        config, get_resource_path
    )


def indicator_shared_baseline_part_path(filename, require_exists=True):
    """Backward-compatible facade for a shared indicator baseline part."""
    return _baseline_resources.indicator_shared_baseline_part_path(
        config, get_resource_path, filename, require_exists=require_exists
    )


def indicator_shared_baseline_source_label(filename):
    """Backward-compatible facade for shared indicator source status."""
    return _baseline_resources.indicator_shared_baseline_source_label(
        config, get_resource_path, filename
    )


def has_baseline_part(model_name, filename):
    return _baseline_resources.has_baseline_part(
        get_resource_path, model_name, filename
    )


def baseline_source_label(model_name, filename):
    return _baseline_resources.baseline_source_label(
        get_resource_path, model_name, filename
    )


def get_end_cap_contour_points(w, d, t, fw, yl1, yr1, ytop1, ybottom1, relief_config=None):
    """
    依通用 sheet-metal geometry engine 計算封頭尾展開外輪廓。
    回傳不重複閉合點，供基準檔拉伸映射與 closed polyline 使用。
    """
    y_w = calculate_y_width(yl1, yr1, w, t)
    y_d = calculate_y_depth(ytop1, ybottom1, d, t, fw)
    geometry = EndCapGeometry(
        total_width=y_w,
        total_depth=y_d,
        thickness=t,
        fw=fw,
        left_fold=yl1,
        right_fold=yr1,
        top_first_fold=ytop1,
        bottom_fold=ybottom1,
    )
    cfg = relief_config if relief_config is not None else RELIEF_CONFIG
    outline = build_endcap_outline(geometry, cfg)
    return [(pt.x, pt.y) for pt in outline[:-1]]


def get_stretched_end_cap_data(
    model_name, W_val, H_val, D_val, T_val, FW_val=None, is_tail=False,
    corner_policy=None, x_topology="folded",
    box_body_formed_fw_left=None, box_body_formed_fw_right=None,
    depth_comp_t=3.0, target_fold_left=None, target_fold_right=None,
    target_fold_top=None, target_fold_bottom=None,
):
    """Backward-compatible facade for baseline End Cap scene adaptation."""
    return _baseline_scene_adapters.get_stretched_end_cap_data(
        model_name, W_val, H_val, D_val, T_val, FW_val, is_tail,
        corner_policy, x_topology, box_body_formed_fw_left, box_body_formed_fw_right,
        depth_comp_t, target_fold_left, target_fold_right, target_fold_top, target_fold_bottom,
        baseline_part_path=baseline_part_path,
        baseline_expected_path=baseline_expected_path,
        source_loader=(globals().get("load_baseline_dxf_source") or ezdxf.readfile),
        get_end_cap_contour_points=get_end_cap_contour_points,
        relief_config=RELIEF_CONFIG,
    )


def _build_stretched_end_cap_scene(
    model_name, W_val, H_val, D_val, T_val, FW_val=None, *,
    x_topology="folded", draw_stock=False, is_tail=False, holes=None, corner_policy=None,
    box_body_formed_fw_left=None, box_body_formed_fw_right=None,
):
    """Assemble one complete stretched End Cap scene and normalize head orientation once.

    The returned SceneData is the authoritative WYSIWYG scene for both GUI preview and DXF
    serialization.  No renderer or exporter is allowed to mirror it again.
    """
    scene_data = get_stretched_end_cap_data(
        model_name, W_val, H_val, D_val, T_val, FW_val, is_tail, corner_policy, x_topology,
        box_body_formed_fw_left, box_body_formed_fw_right,
    )
    p = scene_data.params
    total_width = p['total_width']
    total_depth = p['total_depth']
    yl1_val, yr1_val = p['yl1'], p['yr1']
    ybottom1_val, ytop1_val, fw_val = p['ybottom1'], p['ytop1'], p['fw']

    scene = DrawingScene()
    if draw_stock:
        scene.add(build_stock_outline(total_width, total_depth))
    scene.extend(scene_data.scene.primitives)

    geometry = EndCapGeometry(
        total_width=total_width, total_depth=total_depth, thickness=T_val, fw=fw_val,
        left_fold=yl1_val, right_fold=yr1_val,
        top_first_fold=ytop1_val, bottom_fold=ybottom1_val,
    )
    relief = calculate_endcap_relief_dimensions(geometry, RELIEF_CONFIG)
    part_name = 'End Cap Tail (Y)' if is_tail else 'End Cap Head (Y)'
    scene.extend(build_endcap_check(
        geometry=geometry, relief=relief,
        finished_width=W_val, finished_depth=D_val,
        part_label=f'{part_name} (Stretched from {model_name})',
    ))

    if not is_tail:
        # Normalize the loaded/base head scene once.  Editor features are added later
        # directly in this final orientation, so closing the editor cannot flip them.
        scene = mirror_drawing_scene_y(scene, total_depth)

    scene.extend(resolved_features_to_primitives(
        _resolve_user_holes(holes, geometry, W_val, D_val, normalized_head=not is_tail)
    ))

    metadata = dict(getattr(scene_data, 'metadata', {}) or {})
    metadata['orientation_normalized'] = True
    metadata['head_mirrored'] = not is_tail
    return SceneData(scene=scene, params=dict(p), metadata=metadata)


def export_stretched_end_cap_dxf(filepath, model_name, W_val=None, H_val=None, D_val=None, T_val=None, FW_val=None, draw_stock=None, is_tail=False, holes=None, corner_policy=None):
    """基於基準檔拉伸封頭/尾；直接序列化已正規化的 WYSIWYG scene。"""
    w = W_val if W_val is not None else W
    d = D_val if D_val is not None else D
    t = T_val if T_val is not None else T
    part_name = 'End Cap Tail (Y)' if is_tail else 'End Cap Head (Y)'
    scene_data = _build_stretched_end_cap_scene(
        model_name, w, H_val, d, t, FW_val,
        draw_stock=(draw_stock if draw_stock is not None else DRAW_STOCK),
        is_tail=is_tail, holes=holes, corner_policy=corner_policy,
    )
    _save_scene_dxf(filepath, scene_data.scene)
    print(f"成功輸出基準拉伸 {part_name} DXF: {filepath}")
