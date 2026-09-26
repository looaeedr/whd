# -*- coding: utf-8 -*-
"""Legacy baseline-to-scene adaptation without DXF serialization ownership."""
from __future__ import annotations

from .sheetmetal_drawing import DrawingScene, SceneData
from .sheetmetal_geometry import (
    EndCapGeometry,
    build_endcap_bend_segments,
    build_strip_bend_segments,
    build_strip_outline,
    calculate_endcap_relief_dimensions,
)
from .sheetmetal_part_adapters import build_unknown_endcap_result

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


def get_stretched_end_cap_data(
    model_name, W_val, H_val, D_val, T_val, FW_val=None, is_tail=False,
    corner_policy=None, x_topology="folded",
    box_body_formed_fw_left=None, box_body_formed_fw_right=None,
    depth_comp_t=3.0, target_fold_left=None, target_fold_right=None,
    target_fold_top=None, target_fold_bottom=None, *,
    baseline_part_path, baseline_expected_path, source_loader,
    get_end_cap_contour_points, relief_config,
):
    """
    載入基準檔 DXF，進行拉伸，過濾孔洞，並回傳幾何資料與反推得到的參數
    """
    dxf_path = baseline_part_path(model_name, "封頭尾.dxf")
    if not dxf_path:
        raise FileNotFoundError(f"找不到基準 DXF 檔案: {baseline_expected_path(model_name, '封頭尾.dxf')}")

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
        elif ent.dxftype() == 'CIRCLE':
            cx, cy = ent.dxf.center.x, ent.dxf.center.y
            r = ent.dxf.radius
            all_x.extend([cx - r, cx + r])
            all_y.extend([cy - r, cy + r])
        elif ent.dxftype() == 'LINE':
            all_x.extend([ent.dxf.start.x, ent.dxf.end.x])
            all_y.extend([ent.dxf.start.y, ent.dxf.end.y])

    if not all_x or not all_y:
        raise ValueError("基準檔中無 CUTTING 輪廓，無法分析尺寸。")

    min_x, max_x = min(all_x), max(all_x)
    min_y, max_y = min(all_y), max(all_y)

    W_base_dxf = max_x - min_x
    H_base_dxf = max_y - min_y

    # 2. 獲取基準折彎線 (BEND)
    bend_lines = msp.query('LINE[layer=="BEND"]')
    vertical_bends = []
    horizontal_bends = []

    for line in bend_lines:
        x1, y1 = line.dxf.start.x - min_x, line.dxf.start.y - min_y
        x2, y2 = line.dxf.end.x - min_x, line.dxf.end.y - min_y
        if abs(x1 - x2) < 0.1:
            vertical_bends.append((x1 + x2) / 2.0)
        elif abs(y1 - y2) < 0.1:
            horizontal_bends.append((y1 + y2) / 2.0)

    vertical_bends = sorted(list(set(round(x, 2) for x in vertical_bends)))
    horizontal_bends = sorted(list(set(round(y, 2) for y in horizontal_bends)))

    if len(vertical_bends) != 2 or len(horizontal_bends) != 3:
        raise ValueError(f"基準 DXF 折彎線數量不符！實際偵測到 垂直:{len(vertical_bends)}, 水平:{len(horizontal_bends)}")

    X1, X2 = vertical_bends
    Y1, Y2, Y3 = horizontal_bends

    # 反推基準折彎參數
    yl1_b = X1
    yr1_b = W_base_dxf - X2
    ybottom1_b = Y1
    FW_b = Y3 - Y2
    ytop1_b = H_base_dxf - Y3

    W_base = X2 - X1 + 4 * 2.0  # 基準板厚固定為 2.0
    D_base = Y2 - Y1 + 3 * 2.0

    # 計算基準外框 16 個頂點
    pts_base = get_end_cap_contour_points(W_base, D_base, 2.0, FW_b, yl1_b, yr1_b, ytop1_b, ybottom1_b)

    # 3. 計算新尺寸與新外框 16 個頂點 (折彎參數沿用基準，FW 沿用新設定或基準)
    yl1_n = float(target_fold_left) if target_fold_left is not None else yl1_b
    yr1_n = float(target_fold_right) if target_fold_right is not None else yr1_b
    ybottom1_n = float(target_fold_bottom) if target_fold_bottom is not None else ybottom1_b
    FW_n = FW_val if FW_val is not None else FW_b
    ytop1_n = float(target_fold_top) if target_fold_top is not None else ytop1_b

    if corner_policy is None:
        new_W_dxf = W_val - 4 * T_val + yl1_n + yr1_n
        new_H_dxf = D_val - 3 * T_val + ytop1_n + FW_n + ybottom1_n
        pts_new = get_end_cap_contour_points(
            W_val, D_val, T_val, FW_n, yl1_n, yr1_n, ytop1_n, ybottom1_n
        )
        structural_result = None
    else:
        structural_result = build_unknown_endcap_result(
            w=W_val, d=D_val, t=T_val, fw=FW_n, yl1=yl1_n, yr1=yr1_n,
            ytop1=ytop1_n, ybottom1=ybottom1_n, corner_policy=corner_policy,
            x_topology=x_topology, depth_comp_t=depth_comp_t,
            box_body_formed_fw_left=box_body_formed_fw_left,
            box_body_formed_fw_right=box_body_formed_fw_right,
        )
        new_W_dxf = float(structural_result.width)
        new_H_dxf = float(structural_result.height)
        pts_new = [(pt.x, pt.y) for pt in structural_result.outline[:-1]]
        # Structural result owns the effective folds after CornerType/topology
        # resolution.  Stretched feature mapping and metadata must use the same
        # values instead of retaining folds recovered from the legacy baseline.
        topology = structural_result.topology
        yl1_n = float(topology.left_fold)
        yr1_n = float(topology.right_fold)
        ytop1_n = float(topology.top_first_fold)
        ybottom1_n = float(topology.bottom_fold)
        FW_n = float(topology.fw)

    X1_new = yl1_n
    X2_new = new_W_dxf - yr1_n
    Y1_new = ybottom1_n
    Y2_new = Y1_new + D_val - float(depth_comp_t) * T_val
    Y3_new = Y2_new + FW_n
    new_relief_dims = calculate_endcap_relief_dimensions(
        EndCapGeometry(
            total_width=new_W_dxf,
            total_depth=new_H_dxf,
            thickness=T_val,
            fw=FW_n,
            left_fold=yl1_n,
            right_fold=yr1_n,
            top_first_fold=ytop1_n,
            bottom_fold=ybottom1_n,
        ),
        relief_config,
    )

    # 4. 建立映射參考對應
    ref_x = [0.0, X1, W_base_dxf/2.0, X2, W_base_dxf]
    new_ref_x = [0.0, X1_new, new_W_dxf/2.0, X2_new, new_W_dxf]

    ref_y = [0.0, Y1, H_base_dxf/2.0, Y2, Y3, H_base_dxf]
    new_ref_y = [0.0, Y1_new, new_H_dxf/2.0, Y2_new, Y3_new, new_H_dxf]

    # 加入截角座標層級作為映射參考。映射本身是 X/Y 各自的一維
    # 分段映射，因此不能再假設不同 CornerType 的 polygon vertex count
    # 或 vertex index 一致。只有該軸的座標層級數相同時才按單調順序
    # 配對；拓撲改變造成層級數不同時，保留上方已建立的穩定折線/邊界
    # 控制點，不製造錯誤的頂點對應。
    def extend_axis_levels(ref, new_ref, old_values, new_values):
        old_levels = sorted({round(float(value), 9) for value in old_values})
        new_levels = sorted({round(float(value), 9) for value in new_values})
        if len(old_levels) != len(new_levels):
            return
        ref.extend(old_levels)
        new_ref.extend(new_levels)

    extend_axis_levels(ref_x, new_ref_x, (p[0] for p in pts_base), (p[0] for p in pts_new))
    extend_axis_levels(ref_y, new_ref_y, (p[1] for p in pts_base), (p[1] for p in pts_new))

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
        'yl1': yl1_n, 'yr1': yr1_n, 'ytop1': ytop1_n, 'ybottom1': ybottom1_n, 'fw': FW_n,
        'total_width': new_W_dxf, 'total_depth': new_H_dxf,
    }

    # 5.1 手動加入公式化產生的新外輪廓與新折彎線
    scene.add_polyline(pts_new, layer='CUTTING', closed=True)

    # 新折彎線也由 geometry engine 產生，確保不穿過二級截角
    new_geometry = EndCapGeometry(
        total_width=new_W_dxf,
        total_depth=new_H_dxf,
        thickness=T_val,
        fw=FW_n,
        left_fold=yl1_n,
        right_fold=yr1_n,
        top_first_fold=ytop1_n,
        bottom_fold=ybottom1_n,
    )
    bend_segments = structural_result.bends if structural_result is not None else build_endcap_bend_segments(new_geometry, relief_config)
    for segment in bend_segments:
        scene.add_line(segment.p1, segment.p2, layer='BEND')

    # 5.2 載入並映射基準檔內的其他圖元 (排除舊的外框與折彎線)
    for ent in msp:
        layer = ent.dxf.layer
        if layer == 'BEND':
            continue # 忽略舊折彎線

        if layer == 'CHECK':
            continue # 忽略舊標註

        if layer == 'CUTTING' and ent.dxftype() == 'LWPOLYLINE':
            # 排除舊的外輪廓 (點數 > 10)
            if len(list(ent.get_points())) > 10:
                continue

        # 進行控制點映射
        if ent.dxftype() == 'LWPOLYLINE':
            pts = [(map_x(pt[0] - min_x), map_y(pt[1] - min_y)) for pt in ent.get_points()]
            scene.add_polyline(pts, layer=layer, closed=ent.closed)
        elif ent.dxftype() == 'LINE':
            p1 = (map_x(ent.dxf.start.x - min_x), map_y(ent.dxf.start.y - min_y))
            p2 = (map_x(ent.dxf.end.x - min_x), map_y(ent.dxf.end.y - min_y))
            scene.add_line(p1, p2, layer=layer)
        elif ent.dxftype() == 'CIRCLE':
            cx = ent.dxf.center.x - min_x
            cy = ent.dxf.center.y - min_y

            # 1. 特徵識別：若是上部翻邊的圓孔 (後鈕孔)，其 cy > Y3 (基準頂折線)
            # 這兩個孔需要隨避位截角動態偏置定位，避免寫死常數在基準檔被修改時出錯
            if cy > Y3:
                if cx < W_base_dxf / 2.0:
                    # 左後鈕孔：動態計算其相對於基準檔中公式截角 X 邊界的距離
                    notch_x_base = abs(yl1_b) + FW_b
                    d_offset = cx - notch_x_base

                    # 應用到新圖面的公式截角 X 邊界上
                    notch_x_new = abs(yl1_n) + FW_n
                    cx_new = notch_x_new + d_offset
                else:
                    # 右後鈕孔：動態計算其相對於基準檔中公式截角 X 邊界的距離
                    notch_x_base = W_base_dxf - (abs(yr1_b) + FW_b)
                    d_offset = notch_x_base - cx

                    # 應用到新圖面的公式截角 X 邊界上
                    notch_x_new = new_W_dxf - (abs(yr1_n) + FW_n)
                    cx_new = notch_x_new - d_offset
                cy_new = map_y(cy)

            # 2. 特徵識別：若是底部中央圓孔，其 cy < Y1 且 cx 接近基準圖面 X 的正中央
            elif cy < Y1 and abs(cx - W_base_dxf / 2.0) < 5.0:
                # X 座標永遠保持在新展開圖寬度的正中央
                cx_new = new_W_dxf / 2.0
                # Y 座標保持與底部邊緣的物理距離
                cy_new = cy

            # 3. 其他圓孔：使用通用映射
            else:
                cx_new = map_x(cx)
                cy_new = map_y(cy)

            source_type = None
            source_id = None
            if str(layer).upper() == 'CUTTING':
                handle = str(getattr(ent.dxf, 'handle', '') or '').strip().upper()
                if not handle:
                    handle = f"XYR:{cx:.6f}:{cy:.6f}:{float(ent.dxf.radius):.6f}"
                source_type = 'baseline_endcap_hole'
                source_id = f"endcap:baseline_hole:{handle}"
            scene.add_circle(
                (cx_new, cy_new), ent.dxf.radius, layer=layer,
                source_type=source_type, source_id=source_id,
            )


    return SceneData(scene=scene, params=params)
