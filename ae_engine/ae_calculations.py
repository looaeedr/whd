# -*- coding: utf-8 -*-
"""Pure AE dimension calculations shared by part-family exporters."""
from __future__ import annotations

from .ae_config import (
    W, H, D, T, FW,
    zl1_def, zl2_def, zr1_def, zr2_def, z_comp_def,
    yl1_def, yr1_def, ytop1_def, ybottom1_def,
    door_gap_w_def, door_gap_h_def,
    door_fold_left_def, door_fold_right_def, door_fold_top_def, door_fold_bottom_def,
)
from .sheetmetal_part_adapters import calculate_door_finished_size as _calculate_door_finished_size_from_adapter

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
