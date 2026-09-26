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

def get_resource_path(relative_path):
    """
    獲取資源路徑，支援 PyInstaller 打包。
    優先在 EXE 執行檔同級目錄尋找，以便使用者可以自訂或修改。
    若找不到，則回退到打包的臨時目錄（__file__ 所在目錄）。
    """
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
        exe_path = os.path.join(exe_dir, relative_path)
        if os.path.exists(exe_path):
            return exe_path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Packaged core keeps editable resources (config.ini / 基準檔) beside
    # ae_engine/, so GUI and split hosts can replace the engine directory
    # without moving user-owned resources into the package.
    if os.path.basename(current_dir) == "ae_engine":
        current_dir = os.path.dirname(current_dir)
    return os.path.join(current_dir, relative_path)

# ==========================================
# 讀取 INI 設定檔
# ==========================================
INI_PATH = get_resource_path("config.ini")
config = configparser.ConfigParser()

# 建立預設 INI 字典，供檔案不存在時自動寫入
default_config = {
    'DEFAULT_SIZES': {
        'W': '400.0',
        'H': '600.0',
        'D': '250.0',
        'T': '2.0',
        'FW': '25.0'
    },
    'BOX_BODY_Z': {
        'zl1': '15.0',
        'zl2': '20.0',
        'zr1': '15.0',
        'zr2': '20.0',
        'z_comp': '2.0'
    },
    'END_CAP_Y': {
        'yl1': '15.0',
        'yr1': '15.0',
        'ytop1': '16.0',
        'ybottom1': '15.0'
    },
    'OUTPUT': {
        'draw_stock': 'false'   # 是否繪製 STOCK 母材外框，true/false
    },
    'UI': {
        # 現有 GUI 字級即為「小」；中、大只改文字，不改幾何。
        'text_size': 'small'
    },
    'HOLES': {
        # 左右掛孔: 距左/右折彎線的 X 偏移，Y 距頂折彎線往上
        'hang_hole_radius': '3.2',
        'hang_hole_x_offset': '35.5',
        'hang_hole_y_from_top_bend': '6.0',
        # 左下方孔 (兩者共有): X 距左邊總偏移、寬、Y 距底邊偏移、高
        'square_hole_x_from_left': '3.0',
        'square_hole_width': '4.0',
        'square_hole_y_from_bottom': '18.0',
        'square_hole_height': '4.0',
        # 底部中心圆孔 (僅封尾): X 置中，Y 距展開圖底邊
        'bottom_hole_radius': '2.5',
        'bottom_hole_y_from_bottom': '5.0'
    },
    'NOTCH': {
        # 舊版相容設定：保留讀取，但新 geometry engine 不再使用這些舊單位語意
        'bottom_gap': '0.5',
        'sub_x_half_t': '0.5',
        'sub_y_factor': '2.0'
    },
    'RELIEF': {
        # 新版：以板厚 T 的倍數表示
        'top_secondary_x_factor': '0.5',
        'top_secondary_depth_factor': '2.0',
        'bottom_x_factor': '0.5',
        'bottom_y_factor': '0.5'
    },
    'DOOR': {
        # 門與箱身邊框之間的間隙（左右各一、上下各一）
        'door_gap_w': '3.5',
        'door_gap_h': '3.5',
        # 門的四個折邊尺寸
        'door_fold_left':   '19.0',
        'door_fold_right':  '15.0',
        'door_fold_top':    '15.0',
        'door_fold_bottom': '15.0'
    },
    'INDICATOR_BOX': {
        'fold': '49.0',
        'shared_baseline_model': ''
    },
    'BASE_PLATE': {
        # 底板收縮與折邊預設值
        'shrink': '55.0',
        'bend': '15.0'
    }
}

if not os.path.exists(INI_PATH):
    config.read_dict(default_config)
    with open(INI_PATH, 'w', encoding='utf-8') as f:
        config.write(f)
else:
    config.read(INI_PATH, encoding='utf-8')

# 全域變數讀取
W = config.getfloat('DEFAULT_SIZES', 'W', fallback=400.0)
H = config.getfloat('DEFAULT_SIZES', 'H', fallback=600.0)
D = config.getfloat('DEFAULT_SIZES', 'D', fallback=250.0)
T = config.getfloat('DEFAULT_SIZES', 'T', fallback=2.0)
FW = config.getfloat('DEFAULT_SIZES', 'FW', fallback=25.0)

# STOCK 開關：是否繪製母材外框矩形
DRAW_STOCK = config.getboolean('OUTPUT', 'draw_stock', fallback=False)

# 孔洞幾何參數（封頭/尾孔洞一律繪製，無開關）
hang_hole_r    = config.getfloat('HOLES', 'hang_hole_radius',          fallback=3.2)
hang_hole_x    = config.getfloat('HOLES', 'hang_hole_x_offset',        fallback=35.5)
hang_hole_y_up = config.getfloat('HOLES', 'hang_hole_y_from_top_bend', fallback=6.0)
sq_x_left      = config.getfloat('HOLES', 'square_hole_x_from_left',   fallback=3.0)
sq_width       = config.getfloat('HOLES', 'square_hole_width',          fallback=4.0)
sq_y_bottom    = config.getfloat('HOLES', 'square_hole_y_from_bottom',  fallback=18.0)
sq_height      = config.getfloat('HOLES', 'square_hole_height',         fallback=4.0)
bottom_hole_r  = config.getfloat('HOLES', 'bottom_hole_radius',         fallback=2.5)
bottom_hole_y  = config.getfloat('HOLES', 'bottom_hole_y_from_bottom',  fallback=5.0)

VAULT_ENDCAP_FEATURE_POLICY = VaultEndCapFeaturePolicy(
    hanging_hole_radius=hang_hole_r,
    hanging_hole_y_from_top_bend=hang_hole_y_up,
    square_hole_origin=Vec2(sq_x_left, sq_y_bottom),
    square_hole_size=Vec2(sq_width, sq_height),
    tail_bottom_hole_radius=bottom_hole_r,
    tail_bottom_hole_y=bottom_hole_y,
)

# 舊截角參數：保留給舊設定檔相容，不再作為新版外輪廓公式來源
notch_bottom_gap  = config.getfloat('NOTCH', 'bottom_gap',    fallback=0.5)
notch_sub_x_half  = config.getfloat('NOTCH', 'sub_x_half_t',  fallback=0.5)
notch_sub_y_factor = config.getfloat('NOTCH', 'sub_y_factor', fallback=2.0)

# 新版通用 relief 參數：以板厚 T 的倍數表示
RELIEF_CONFIG = ReliefConfig(
    top_secondary_x_factor=config.getfloat('RELIEF', 'top_secondary_x_factor', fallback=0.5),
    top_secondary_depth_factor=config.getfloat('RELIEF', 'top_secondary_depth_factor', fallback=2.0),
    bottom_x_factor=config.getfloat('RELIEF', 'bottom_x_factor', fallback=0.5),
    bottom_y_factor=config.getfloat('RELIEF', 'bottom_y_factor', fallback=0.5),
)

# 門 (Door) 參數
door_gap_w_def        = config.getfloat('DOOR', 'door_gap_w',        fallback=3.5)
door_gap_h_def        = config.getfloat('DOOR', 'door_gap_h',        fallback=3.5)
door_fold_left_def    = config.getfloat('DOOR', 'door_fold_left',    fallback=19.0)
door_fold_right_def   = config.getfloat('DOOR', 'door_fold_right',   fallback=15.0)
door_fold_top_def     = config.getfloat('DOOR', 'door_fold_top',     fallback=15.0)
door_fold_bottom_def  = config.getfloat('DOOR', 'door_fold_bottom',  fallback=15.0)

# 指示燈盒參數
indicator_box_fold_def = config.getfloat('INDICATOR_BOX', 'fold', fallback=49.0)
indicator_small_door_gap_def = config.getfloat('INDICATOR_BOX', 'small_door_gap', fallback=3.5)

# 底板 (Base Plate) 參數
base_plate_shrink_def = config.getfloat('BASE_PLATE', 'shrink', fallback=55.0)
base_plate_bend_def   = config.getfloat('BASE_PLATE', 'bend', fallback=15.0)

# 箱身 z 預設值
zl1_def = config.getfloat('BOX_BODY_Z', 'zl1', fallback=15.0)
zl2_def = config.getfloat('BOX_BODY_Z', 'zl2', fallback=20.0)
zr1_def = config.getfloat('BOX_BODY_Z', 'zr1', fallback=15.0)
zr2_def = config.getfloat('BOX_BODY_Z', 'zr2', fallback=20.0)
z_comp_def = config.getfloat('BOX_BODY_Z', 'z_comp', fallback=3.0)

# 封頭尾 y 預設值
yl1_def = config.getfloat('END_CAP_Y', 'yl1', fallback=15.0)
yr1_def = config.getfloat('END_CAP_Y', 'yr1', fallback=15.0)
ytop1_def = config.getfloat('END_CAP_Y', 'ytop1', fallback=16.0)
ybottom1_def = config.getfloat('END_CAP_Y', 'ybottom1', fallback=15.0)


# ==========================================
# 數值格式化輔助函式
# ==========================================
def fmt_val(v):
    val = round(float(v), 2)
    if val.is_integer():
        return str(int(val))
    s = f"{val:.2f}"
    if s.endswith(".00"):
        return s[:-3]
    if s.endswith("0"):
        return s[:-1]
    return s


# ==========================================
# 箱身 (z) 公式定義區
# ==========================================
def calculate_z_length(zl1=None, zl2=None, zr1=None, zr2=None, z_comp=None, W_val=None, D_val=None, T_val=None, FW_val=None):
    """
    計算【箱身 z】總料長度
    """
    # 參數 None 判定
    zl1 = zl1 if zl1 is not None else zl1_def
    zl2 = zl2 if zl2 is not None else zl2_def
    zr1 = zr1 if zr1 is not None else zr1_def
    zr2 = zr2 if zr2 is not None else zr2_def
    z_comp = z_comp if z_comp is not None else z_comp_def
    
    global W, D, T, FW
    w = W_val if W_val is not None else W
    d = D_val if D_val is not None else D
    t = T_val if T_val is not None else T
    fw = FW_val if FW_val is not None else FW
    
    total_length = (
        abs(zl1) + 
        zl2 + 
        abs(zr1) + 
        zr2 + 
        (2 * fw) + 
        w + 
        (2 * d) - 
        (6 * t) + 
        z_comp
    )
    return total_length


# ==========================================
# 封頭尾 (y) 公式定義區
# ==========================================
def calculate_y_width(yl1=None, yr1=None, W_val=None, T_val=None):
    """
    計算【封頭尾 y - 寬度方向】展開長度
    """
    yl1 = yl1 if yl1 is not None else yl1_def
    yr1 = yr1 if yr1 is not None else yr1_def
    
    global W, T
    w = W_val if W_val is not None else W
    t = T_val if T_val is not None else T
    
    total_width = w - (4 * t) + abs(yl1) + abs(yr1)
    return total_width


def calculate_y_depth(ytop1=None, ybottom1=None, D_val=None, T_val=None, FW_val=None):
    """
    計算【封頭尾 y - 深度方向】展開長度
    """
    ytop1 = ytop1 if ytop1 is not None else ytop1_def
    ybottom1 = ybottom1 if ybottom1 is not None else ybottom1_def
    
    global D, T, FW
    d = D_val if D_val is not None else D
    t = T_val if T_val is not None else T
    fw = FW_val if FW_val is not None else FW
    
    total_depth = d - (3 * t) + ytop1 + fw + ybottom1
    return total_depth


# ==========================================
# 門 (door) 公式定義區
# ==========================================
def calculate_door_finished_size(W_val=None, H_val=None, FW_val=None,
                                  gap_w=None, gap_h=None, T_val=None, frame_edges=None):
    """
    計算【門】成品尺寸
    成品邊框寬度為 FW + 2T
    成品寬 = W - (FW + 2T)*2 - gap_w*2
    成品高 = H - (FW + 2T)*2 - gap_h*2
    """
    global W, H, FW, T
    w  = W_val  if W_val  is not None else W
    h  = H_val  if H_val  is not None else H
    fw = FW_val if FW_val is not None else FW
    gw = gap_w  if gap_w  is not None else door_gap_w_def
    gh = gap_h  if gap_h  is not None else door_gap_h_def
    t  = T_val  if T_val  is not None else T
    
    return _calculate_door_finished_size_from_adapter(
        w=w, h=h, t=t, fw=fw, gap_w=gw, gap_h=gh, frame_edges=frame_edges,
    )


def calculate_door_blank_size(W_val=None, H_val=None, T_val=None, FW_val=None,
                               gap_w=None, gap_h=None,
                               fold_left=None, fold_right=None,
                               fold_top=None, fold_bottom=None, frame_edges=None):
    """
    計算【門】展開總料尺寸
    門寬總料 = 成品寬 - 2T + 左折 + 右折
    門高總料 = 成品高 - 2T + 上折 + 下折
    """
    global T
    t  = T_val if T_val is not None else T
    fl = fold_left   if fold_left   is not None else door_fold_left_def
    fr = fold_right  if fold_right  is not None else door_fold_right_def
    ft = fold_top    if fold_top    is not None else door_fold_top_def
    fb = fold_bottom if fold_bottom is not None else door_fold_bottom_def
    finished_w, finished_h = calculate_door_finished_size(
        W_val, H_val, FW_val, gap_w, gap_h, t, frame_edges=frame_edges
    )
    blank_w = finished_w - 2 * t + fl + fr
    blank_h = finished_h - 2 * t + ft + fb
    return blank_w, blank_h


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
            "indicator_shared_baseline_part_path": indicator_shared_baseline_part_path,
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
    """Load the globally shared indicator-box baseline and add the current indicator layout.

    ``model_name`` is retained only for backward call compatibility and is intentionally
    ignored: indicator boxes are global shared parts and never inherit PW/PSR/RF.
    The shared resource itself is resolved through ``indicator_shared_baseline_part_path``.
    """
    groups = tuple(int(v) for v in layer_groups)
    if not groups:
        groups = (1,)
    formula_data = get_indicator_box_data(groups, T_val, corner_policy=corner_policy)
    target_w = float(formula_data.params['w'])
    target_h = float(formula_data.params['h'])
    fold = float(indicator_box_fold_def)

    dxf_path = indicator_shared_baseline_part_path("盒子.dxf")
    expected = indicator_shared_baseline_part_path("盒子.dxf", require_exists=False)
    if not dxf_path:
        raise FileNotFoundError(f"AE_BASELINE_MISSING: {expected}")

    doc = (globals().get("load_baseline_dxf_source") or ezdxf.readfile)(dxf_path)
    msp = doc.modelspace()

    all_x = []
    all_y = []
    closed_cutting_bounds = []
    for ent in msp:
        etype = ent.dxftype()
        if etype == 'LWPOLYLINE':
            points = [(float(point[0]), float(point[1])) for point in ent.get_points()]
            for x, y in points:
                all_x.append(x); all_y.append(y)
            raw_layer = str(getattr(ent.dxf, 'layer', '') or '').upper()
            if ent.closed and points and raw_layer in {'CUTTING', '0', ''}:
                xs = [x for x, _ in points]; ys = [y for _, y in points]
                closed_cutting_bounds.append((min(xs), max(xs), min(ys), max(ys)))
        elif etype == 'LINE':
            all_x.extend((float(ent.dxf.start.x), float(ent.dxf.end.x)))
            all_y.extend((float(ent.dxf.start.y), float(ent.dxf.end.y)))
        elif etype in {'CIRCLE', 'ARC'}:
            cx = float(ent.dxf.center.x); cy = float(ent.dxf.center.y); radius = float(ent.dxf.radius)
            all_x.extend((cx - radius, cx + radius)); all_y.extend((cy - radius, cy + radius))
    if not all_x or not all_y:
        raise ValueError(f"盒子基準檔沒有可用幾何: {dxf_path}")

    if closed_cutting_bounds:
        min_x, max_x, min_y, max_y = max(
            closed_cutting_bounds, key=lambda b: (b[1] - b[0]) * (b[3] - b[2])
        )
    else:
        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)
    base_w = max_x - min_x
    base_h = max_y - min_y
    if base_w <= 0 or base_h <= 0:
        raise ValueError(f"盒子基準檔尺寸無效: {dxf_path}")

    vertical_bends = []
    horizontal_bends = []
    for ent in msp.query('LINE[layer=="BEND"]'):
        x1 = float(ent.dxf.start.x) - min_x; x2 = float(ent.dxf.end.x) - min_x
        y1 = float(ent.dxf.start.y) - min_y; y2 = float(ent.dxf.end.y) - min_y
        if abs(x1 - x2) < 0.1:
            vertical_bends.append((x1 + x2) / 2.0)
        elif abs(y1 - y2) < 0.1:
            horizontal_bends.append((y1 + y2) / 2.0)
    vertical_bends = sorted(set(round(v, 4) for v in vertical_bends))
    horizontal_bends = sorted(set(round(v, 4) for v in horizontal_bends))
    if len(vertical_bends) >= 2:
        bx1, bx2 = vertical_bends[0], vertical_bends[-1]
    else:
        bx1, bx2 = fold, base_w - fold
    if len(horizontal_bends) >= 2:
        by1, by2 = horizontal_bends[0], horizontal_bends[-1]
    else:
        by1, by2 = fold, base_h - fold

    ref_x = (0.0, bx1, base_w / 2.0, bx2, base_w)
    new_ref_x = (0.0, fold, target_w / 2.0, target_w - fold, target_w)
    ref_y = (0.0, by1, base_h / 2.0, by2, base_h)
    new_ref_y = (0.0, fold, target_h / 2.0, target_h - fold, target_h)

    def map_axis(value, refs, targets):
        idx = min(range(len(refs)), key=lambda i: abs(value - refs[i]))
        return targets[idx] + (value - refs[idx])

    def map_x(value):
        return map_axis(float(value), ref_x, new_ref_x)

    def map_y(value):
        return map_axis(float(value), ref_y, new_ref_y)

    def entity_layer(ent):
        raw = str(getattr(ent.dxf, 'layer', '') or '').upper()
        if raw in {'CUTTING', 'BEND', 'MARKING', 'DATUM', 'BLIND_HOLE'}:
            return raw
        if raw in {'CHECK', 'STOCK'}:
            return None
        color = int(getattr(ent.dxf, 'color', 0) or 0) if ent.dxf.hasattr('color') else 0
        return 'MARKING' if color == 211 else 'CUTTING'

    def in_baseline_finished_area(cx, cy):
        return bx1 - 0.5 <= cx <= bx2 + 0.5 and by1 - 0.5 <= cy <= by2 + 0.5

    scene = DrawingScene()
    for ent in msp:
        etype = ent.dxftype()
        layer = entity_layer(ent)
        if layer is None or etype == 'REGION':
            continue
        if etype == 'LINE':
            sx = float(ent.dxf.start.x) - min_x; sy = float(ent.dxf.start.y) - min_y
            ex = float(ent.dxf.end.x) - min_x; ey = float(ent.dxf.end.y) - min_y
            cx = (sx + ex) / 2.0; cy = (sy + ey) / 2.0
            # Current layout owns interior MARKING; keep baseline flange/fixed marking only.
            if layer == 'MARKING' and in_baseline_finished_area(cx, cy):
                continue
            scene.add_line((map_x(sx), map_y(sy)), (map_x(ex), map_y(ey)), layer=layer)
        elif etype == 'LWPOLYLINE':
            pts = [(float(pt[0]) - min_x, float(pt[1]) - min_y) for pt in ent.get_points()]
            if not pts:
                continue
            cx = sum(x for x, _ in pts) / len(pts); cy = sum(y for _, y in pts) / len(pts)
            if layer == 'MARKING' and in_baseline_finished_area(cx, cy):
                continue
            scene.add_polyline([(map_x(x), map_y(y)) for x, y in pts], layer=layer, closed=bool(ent.closed))
        elif etype == 'CIRCLE':
            cx = float(ent.dxf.center.x) - min_x; cy = float(ent.dxf.center.y) - min_y
            radius = float(ent.dxf.radius)
            # Replace stale baseline indicator/nameplate/marking holes with the selected groups.
            if in_baseline_finished_area(cx, cy) and (
                (layer == 'CUTTING' and (abs(radius - 15.5) < 0.15 or abs(radius - 1.6) < 0.15))
                or layer == 'MARKING'
            ):
                continue
            scene.add_circle((map_x(cx), map_y(cy)), radius, layer=layer)
        elif etype == 'ARC':
            pts = [(float(pt[0]) - min_x, float(pt[1]) - min_y) for pt in ent.flattening(0.5)]
            if pts:
                scene.add_polyline([(map_x(x), map_y(y)) for x, y in pts], layer=layer, closed=False)

    # The selected layer/group configuration owns current indicator, nameplate and wire-duct marking layout.
    for primitive in formula_data.scene.primitives:
        if isinstance(primitive, CirclePrimitive):
            if primitive.layer == 'MARKING' or (
                primitive.layer == 'CUTTING' and (
                    abs(float(primitive.radius) - 15.5) < 0.15
                    or abs(float(primitive.radius) - 1.6) < 0.15
                )
            ):
                scene.add(primitive)
        elif isinstance(primitive, LinePrimitive) and primitive.layer == 'MARKING':
            scene.add(primitive)

    try:
        _surface_from_scene_primary_cutting(scene, 'indicator_box')
    except ValueError as exc:
        raise ValueError(f"盒子基準檔缺少封閉 CUTTING 外框: {dxf_path}") from exc

    params = dict(formula_data.params)
    params.update({
        'w': target_w, 'h': target_h,
        'baseline_width': base_w, 'baseline_height': base_h,
    })
    metadata = dict(getattr(formula_data, 'metadata', {}) or {})
    metadata.update({
        'baseline_model_name': indicator_shared_baseline_model_name(),
        'baseline_filename': '盒子.dxf',
        'baseline_path': str(dxf_path),
    })
    return SceneData(scene=scene, params=params, metadata=metadata)


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
