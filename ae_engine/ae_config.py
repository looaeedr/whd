# -*- coding: utf-8 -*-
"""AE runtime configuration/defaults shared by part-family implementations."""
from __future__ import annotations

import os
import sys
import configparser

from .sheetmetal_geometry import Vec2, ReliefConfig
from .sheetmetal_features import VaultEndCapFeaturePolicy

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
