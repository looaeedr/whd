# -*- coding: utf-8 -*-
"""Legacy baseline-to-scene adaptation without DXF serialization ownership."""
from __future__ import annotations

from .sheetmetal_drawing import DrawingScene, SceneData
from .sheetmetal_geometry import build_strip_bend_segments, build_strip_outline

def get_stretched_box_body_data(model_name, W_val, H_val, D_val, T_val, FW_val=None, z_comp_val=None, *, baseline_part_path, baseline_expected_path, source_loader, chain_builder):
    """
    載入箱身基準檔 DXF，進行拉伸，並回傳幾何資料與反推得到的參數
    """
    dxf_path = baseline_part_path(model_name, "箱身.dxf")
    if not dxf_path:
        raise FileNotFoundError(f"找不到箱身基準 DXF 檔案: {baseline_expected_path(model_name, '箱身.dxf')}")
        
    doc = source_loader(dxf_path)
    msp = doc.modelspace()
    
    # 1. 獲取基準邊界
    all_x = []
    all_y = []
    for ent in msp.query('*[layer=="CUTTING"]'):
        if ent.dxftype() == 'LWPOLYLINE':
            for pt in ent.get_points():
                all_x.append(pt[0])
                all_y.append(pt[1])
        elif ent.dxftype() == 'LINE':
            all_x.extend([ent.dxf.start.x, ent.dxf.end.x])
            all_y.extend([ent.dxf.start.y, ent.dxf.end.y])
            
    if not all_x or not all_y:
        raise ValueError("箱身基準檔中無 CUTTING 輪廓。")
        
    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)
    
    W_base_dxf = max_x - min_x
    H_base_dxf = max_y - min_y
    
    # 2. 獲取基準垂直折彎線
    bend_lines = msp.query('LINE[layer=="BEND"]')
    vertical_bends = []
    for line in bend_lines:
        x1 = line.dxf.start.x - min_x
        x2 = line.dxf.end.x - min_x
        if abs(x1 - x2) < 0.1:
            vertical_bends.append((x1 + x2) / 2.0)
            
    vertical_bends = sorted(list(set(round(x, 2) for x in vertical_bends)))
    num_bends = len(vertical_bends)
    if num_bends not in [7, 8]:
        raise ValueError(f"箱身基準 DXF 折彎線數量不符！需要 7 或 8 條垂直。實際偵測到 {num_bends} 條。")
        
    # 3. 反推基準參數 (假設板厚為 2.0)
    if num_bends == 7:
        X1, X2, X3, X4, X5, X6, X7 = vertical_bends
        zl1_design = round(X1 * 2.0) / 2.0
        c_est = X1 - zl1_design
        z_comp_b = c_est * 8.0
        if abs(z_comp_b) < 0.05:
            z_comp_b = 0.0
            c_est = 0.0
        zl1_b = zl1_design
        zl2_b = round((X2 - X1 - c_est) * 2.0) / 2.0
        FW_b = round((X3 - X2 - c_est) * 2.0) / 2.0
        D_b = round(((X4 - X3 - c_est) + 2 * 2.0) * 2.0) / 2.0
        W_b = round(((X5 - X4 - c_est) + 2 * 2.0) * 2.0) / 2.0
        zr2_b = round((X7 - X6 - c_est) * 2.0) / 2.0
        zr1_b = zl1_b
        
        zl1_n, zl2_n = zl1_b, zl2_b
        zr1_n, zr2_n = zr1_b, zr2_b
        z_comp_n = z_comp_val if z_comp_val is not None else z_comp_b
        FW_n = FW_val if FW_val is not None else FW_b
        
        # 7 條 BEND = 8 個 strip segments；結構位置由共用 chain builder 產生。
        box_chain = chain_builder(
            W_val, H_val, D_val, T_val, FW_n,
            zl1_n, zl2_n, zr1_n, zr2_n, z_comp_n, False
        )
        new_W_dxf = box_chain.total_width
        new_H_dxf = box_chain.height
        chain_bends = build_strip_bend_segments(box_chain)
        X1_new, X2_new, X3_new, X4_new, X5_new, X6_new, X7_new = [b.p1.x for b in chain_bends]
        X8_new = 0.0

        ref_x = [0.0, X1, X2, X3, X4, X5, X6, X7, W_base_dxf]
        new_ref_x = [0.0, X1_new, X2_new, X3_new, X4_new, X5_new, X6_new, X7_new, new_W_dxf]
    else:
        X1, X2, X3, X4, X5, X6, X7, X8 = vertical_bends
        zl1_design = round(X1 * 2.0) / 2.0
        c_est = X1 - zl1_design
        z_comp_b = c_est * 9.0
        if abs(z_comp_b) < 0.05:
            z_comp_b = 0.0
            c_est = 0.0
        zl1_b = zl1_design
        zl2_b = round((X2 - X1 - c_est) * 2.0) / 2.0
        FW_b = round((X3 - X2 - c_est) * 2.0) / 2.0
        D_b = round(((X4 - X3 - c_est) + 2 * 2.0) * 2.0) / 2.0
        W_b = round(((X5 - X4 - c_est) + 2 * 2.0) * 2.0) / 2.0
        zr2_b = round((X8 - X7 - c_est) * 2.0) / 2.0
        zr1_b = zl1_b
        
        zl1_n, zl2_n = zl1_b, zl2_b
        zr1_n, zr2_n = zr1_b, zr2_b
        z_comp_n = z_comp_val if z_comp_val is not None else z_comp_b
        FW_n = FW_val if FW_val is not None else FW_b
        
        # 8 條 BEND = 9 個 strip segments；與 direct exporter 共用同一 builder。
        box_chain = chain_builder(
            W_val, H_val, D_val, T_val, FW_n,
            zl1_n, zl2_n, zr1_n, zr2_n, z_comp_n, True
        )
        new_W_dxf = box_chain.total_width
        new_H_dxf = box_chain.height
        chain_bends = build_strip_bend_segments(box_chain)
        X1_new, X2_new, X3_new, X4_new, X5_new, X6_new, X7_new, X8_new = [b.p1.x for b in chain_bends]

        ref_x = [0.0, X1, X2, X3, X4, X5, X6, X7, X8, W_base_dxf]
        new_ref_x = [0.0, X1_new, X2_new, X3_new, X4_new, X5_new, X6_new, X7_new, X8_new, new_W_dxf]
        
    ref_y = [0.0, H_base_dxf/2.0, H_base_dxf]
    new_ref_y = [0.0, new_H_dxf/2.0, new_H_dxf]
    
    def map_x(x):
        dists = [abs(x - rx) for rx in ref_x]
        idx = dists.index(min(dists))
        return new_ref_x[idx] + (x - ref_x[idx])
        
    def map_y(y):
        dists = [abs(y - ry) for ry in ref_y]
        idx = dists.index(min(dists))
        return new_ref_y[idx] + (y - ref_y[idx])
        
    scene = DrawingScene()
    params = {
        'zl1': zl1_n, 'zl2': zl2_n, 'zr1': zr1_n, 'zr2': zr2_n, 'z_comp': z_comp_n, 'fw': FW_n,
        'total_width': new_W_dxf, 'total_depth': new_H_dxf,
    }
    
    # 5.1 主 CUTTING / BEND 由 StripFoldChain 統一產生。
    rect_pts = [(pt.x, pt.y) for pt in build_strip_outline(box_chain)]
    scene.add_polyline(rect_pts, layer='CUTTING', closed=True)
    for segment in chain_bends:
        scene.add_line(segment.p1, segment.p2, layer='BEND')
        
    # 5.2 載入並映射其餘圖元 (排除舊外輪廓與折彎線)
    for ent in msp:
        layer = ent.dxf.layer
        if layer == 'BEND' or layer == 'CHECK':
            continue
        if layer == 'CUTTING' and ent.dxftype() == 'LWPOLYLINE':
            # 排除外輪廓
            if len(list(ent.get_points())) >= 4:
                pts = list(ent.get_points())
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                if abs(max(xs) - min(xs) - W_base_dxf) < 1.0 and abs(max(ys) - min(ys) - H_base_dxf) < 1.0:
                    continue
                    
        # 進行映射
        if ent.dxftype() == 'LWPOLYLINE':
            pts = [(map_x(pt[0] - min_x), map_y(pt[1] - min_y)) for pt in ent.get_points()]
            scene.add_polyline(pts, layer=layer, closed=ent.closed)
        elif ent.dxftype() == 'LINE':
            p1 = (map_x(ent.dxf.start.x - min_x), map_y(ent.dxf.start.y - min_y))
            p2 = (map_x(ent.dxf.end.x - min_x), map_y(ent.dxf.end.y - min_y))
            scene.add_line(p1, p2, layer=layer)
        elif ent.dxftype() == 'CIRCLE':
            cx = map_x(ent.dxf.center.x - min_x)
            cy = map_y(ent.dxf.center.y - min_y)
            scene.add_circle((cx, cy), ent.dxf.radius, layer=layer)
            

    return SceneData(scene=scene, params=params)
