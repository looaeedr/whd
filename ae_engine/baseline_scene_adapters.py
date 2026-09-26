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


def get_stretched_door_data(model_name, W_val, H_val, T_val, FW_val=None,
                            gap_w_val=None, gap_h_val=None,
                            fl_val=None, fr_val=None, ft_val=None, fb_val=None, indicator_hole=None, door_indicator=None, door_indicator_offset=None,
                            frame_edges=None, indicator_window_groups=None, corner_policy=None,
                            nameplate_center_datum_top=None, *, deps):
    """
    載入門基準檔 DXF (門.dxf)，進行拉伸，過濾孔洞，並回傳幾何資料與反推得到的參數
    """
    CirclePrimitive = deps["CirclePrimitive"]
    DoorIndicatorContext = deps["DoorIndicatorContext"]
    DrawingScene = deps["DrawingScene"]
    FW = deps["FW"]
    SceneData = deps["SceneData"]
    Vec2 = deps["Vec2"]
    _baseline_cutting_bounds = deps["_baseline_cutting_bounds"]
    _baseline_entity_layer = deps["_baseline_entity_layer"]
    _iter_baseline_entities = deps["_iter_baseline_entities"]
    _make_door_geometry = deps["_make_door_geometry"]
    baseline_expected_path = deps["baseline_expected_path"]
    baseline_part_path = deps["baseline_part_path"]
    build_door_result = deps["build_door_result"]
    build_finished_reference_guide = deps["build_finished_reference_guide"]
    build_unknown_door_result = deps["build_unknown_door_result"]
    calculate_door_finished_size = deps["calculate_door_finished_size"]
    door_fold_bottom_def = deps["door_fold_bottom_def"]
    door_fold_left_def = deps["door_fold_left_def"]
    door_fold_right_def = deps["door_fold_right_def"]
    door_fold_top_def = deps["door_fold_top_def"]
    door_gap_h_def = deps["door_gap_h_def"]
    door_gap_w_def = deps["door_gap_w_def"]
    identify_door_baseline_nameplate_circles = deps["identify_door_baseline_nameplate_circles"]
    indicator_shared_baseline_part_path = deps["indicator_shared_baseline_part_path"]
    indicator_small_door_window_geometry = deps["indicator_small_door_window_geometry"]
    resolve_door_indicator_layout = deps["resolve_door_indicator_layout"]
    source_loader = deps["source_loader"]

    is_indicator_small_door = indicator_window_groups is not None
    filename = "小門.dxf" if is_indicator_small_door else "門.dxf"
    if is_indicator_small_door:
        dxf_path = indicator_shared_baseline_part_path(filename)
        expected = indicator_shared_baseline_part_path(filename, require_exists=False)
    else:
        dxf_path = baseline_part_path(model_name, filename)
        expected = baseline_expected_path(model_name, filename)
    if not dxf_path:
        raise FileNotFoundError(f"找不到基準 DXF 檔案: {expected}")

    doc = source_loader(dxf_path)
    msp = doc.modelspace()

    # 1. 基準原點/尺寸只由 structural CUTTING 決定。MARKING / BLIND_HOLE /
    # DATUM 即使落在板外，也不得改變孔位映射的座標原點。
    bounds = _baseline_cutting_bounds(msp)
    if bounds is None:
        raise ValueError("門基準檔中無有效 CUTTING 幾何，無法分析尺寸。")
    min_x, min_y, max_x, max_y = bounds
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

    if len(vertical_bends) == 2 and len(horizontal_bends) == 2:
        X1, X2 = vertical_bends
        Y1, Y2 = horizontal_bends
        fl_b = X1
        fr_b = W_base_dxf - X2
        fb_b = Y1
        ft_b = H_base_dxf - Y2
    else:
        # 基準檔無折彎線 (例如門.dxf 在 layer '0')，採用預設值作為基準折邊
        fl_b = door_fold_left_def
        fr_b = door_fold_right_def
        fb_b = door_fold_bottom_def
        ft_b = door_fold_top_def
        X1 = fl_b
        X2 = W_base_dxf - fr_b
        Y1 = fb_b
        Y2 = H_base_dxf - ft_b

    # 新折邊沿用傳入值（若有）或基準值
    fl_n = fl_val if fl_val is not None else fl_b
    fr_n = fr_val if fr_val is not None else fr_b
    ft_n = ft_val if ft_val is not None else ft_b
    fb_n = fb_val if fb_val is not None else fb_b

    gw_n = gap_w_val if gap_w_val is not None else door_gap_w_def
    gh_n = gap_h_val if gap_h_val is not None else door_gap_h_def
    fw_n = FW_val if FW_val is not None else FW

    # 計算新尺寸
    finished_w, finished_h = calculate_door_finished_size(
        W_val, H_val, fw_n, gw_n, gh_n, T_val, frame_edges=frame_edges
    )
    new_W_dxf = finished_w - 2 * T_val + fl_n + fr_n
    new_H_dxf = finished_h - 2 * T_val + ft_n + fb_n

    X1_new = fl_n
    X2_new = new_W_dxf - fr_n
    Y1_new = fb_n
    Y2_new = new_H_dxf - ft_n

    # 建立映射參考線
    ref_x = [0.0, X1, W_base_dxf/2.0, X2, W_base_dxf]
    new_ref_x = [0.0, X1_new, new_W_dxf/2.0, X2_new, new_W_dxf]

    ref_y = [0.0, Y1, H_base_dxf/2.0, Y2, H_base_dxf]
    new_ref_y = [0.0, Y1_new, new_H_dxf/2.0, Y2_new, new_H_dxf]
    # 寬的部份(上下折邊)兩端留肉延伸一個 T_val
    pts_base = [
        (fl_b - 2.0,            0.0),
        (W_base_dxf - fr_b + 2.0, 0.0),
        (W_base_dxf - fr_b + 2.0, fb_b),
        (W_base_dxf,            fb_b),
        (W_base_dxf,            H_base_dxf - ft_b),
        (W_base_dxf - fr_b + 2.0, H_base_dxf - ft_b),
        (W_base_dxf - fr_b + 2.0, H_base_dxf),
        (fl_b - 2.0,            H_base_dxf),
        (fl_b - 2.0,            H_base_dxf - ft_b),
        (0.0,                   H_base_dxf - ft_b),
        (0.0,                   fb_b),
        (fl_b - 2.0,            fb_b),
        (fl_b - 2.0,            0.0)
    ]

    # 結構外框與 BEND 一律走同一 topology builder。已知基準盤若解鎖
    # 細參數，只替換結構截角；基準孔/標記仍由後續 mapper 保留。
    if corner_policy is None:
        door_outline, door_bends, _ = _make_door_geometry(
            W_val, H_val, T_val, fw_n, gw_n, gh_n, fl_n, fr_n, ft_n, fb_n,
            frame_edges=frame_edges,
        )
        pts_new = [(pt.x, pt.y) for pt in door_outline]
    else:
        door_result = build_unknown_door_result(
            w=W_val, h=H_val, t=T_val, fw=fw_n, gap_w=gw_n, gap_h=gh_n,
            fold_left=fl_n, fold_right=fr_n, fold_top=ft_n, fold_bottom=fb_n,
            corner_policy=corner_policy, frame_edges=frame_edges,
        )
        door_bends = list(door_result.bends)
        pts_new = [(pt.x, pt.y) for pt in door_result.outline]

    # 頂點映射
    for idx, (bx, by) in enumerate(pts_base):
        ref_x.append(bx)
        new_ref_x.append(pts_new[idx][0])
        ref_y.append(by)
        new_ref_y.append(pts_new[idx][1])

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
        'door_fold_l': fl_n, 'door_fold_r': fr_n, 'door_fold_t': ft_n, 'door_fold_b': fb_n,
        'finished_w': finished_w, 'finished_h': finished_h,
        'total_width': new_W_dxf, 'total_depth': new_H_dxf,
    }
    metadata = {}

    # 加入共用幾何引擎產生的主外輪廓與折彎線。
    scene.add_polyline(pts_new, layer='CUTTING', closed=True)
    for segment in door_bends:
        scene.add_line(segment.p1, segment.p2, layer='BEND')

    # Baseline feature identity is established once before coordinate mapping.
    # The DXF entity handle is only a parser key; downstream identity is the
    # stable ``door:nameplate_mount:*`` feature ID.
    nameplate_ids = identify_door_baseline_nameplate_circles([
        (getattr(ent.dxf, "handle", ""), _baseline_entity_layer(ent),
         float(ent.dxf.center.x - min_x), float(ent.dxf.center.y - min_y), float(ent.dxf.radius))
        for ent in _iter_baseline_entities(msp) if ent.dxftype() == "CIRCLE"
    ]) if not is_indicator_small_door else {}

    # Use the same finished-face guide as generic Door features. This is the
    # canonical local-coordinate contract; family datum overrides never alter
    # the Door origin or axis directions.
    reference_result = build_unknown_door_result(
        w=W_val, h=H_val, t=T_val, fw=fw_n, gap_w=gw_n, gap_h=gh_n,
        fold_left=fl_n, fold_right=fr_n, fold_top=ft_n, fold_bottom=fb_n,
        corner_policy=corner_policy, frame_edges=frame_edges,
    ) if corner_policy is not None else build_door_result(
        w=W_val, h=H_val, t=T_val, fw=fw_n, gap_w=gw_n, gap_h=gh_n,
        fold_left=fl_n, fold_right=fr_n, fold_top=ft_n, fold_bottom=fb_n,
        frame_edges=frame_edges,
    )
    finished_guide = build_finished_reference_guide(
        "door", reference_result, finished_width=float(finished_w), finished_height=float(finished_h)
    )

    # 載入基準檔內的其他圖元 (排除舊的外框與折彎線)
    def is_boundary(p1, p2):
        # 門板外廓基準點特徵座標 (容許誤差)
        x_vals = [0.0, W_base_dxf, fl_b - 2.0, W_base_dxf - fr_b + 2.0]
        y_vals = [0.0, H_base_dxf, fb_b, H_base_dxf - ft_b]
        # 直線垂直且在邊界 X 上
        if abs(p1[0] - p2[0]) < 0.5:
            if any(abs(p1[0] - xv) < 1.0 for xv in x_vals):
                return True
        # 直線水平且在邊界 Y 上
        if abs(p1[1] - p2[1]) < 0.5:
            if any(abs(p1[1] - yv) < 1.0 for yv in y_vals):
                return True
        return False

    for ent in _iter_baseline_entities(msp):
        # Operation ownership is authoritative. Explicit MARKING/BLIND_HOLE/DATUM
        # layers beat entity color; color 211 remains only as a legacy layer-0 fallback.
        tgt_layer = _baseline_entity_layer(ent)
        if tgt_layer in {'BEND', 'CHECK', 'STOCK'}:
            continue

        # 排除 3D 造型的面域 region 圖元
        if ent.dxftype() == 'REGION':
            continue

        # 進行控制點映射與邊界過濾
        if ent.dxftype() == 'LINE':
            start_pt = (ent.dxf.start.x - min_x, ent.dxf.start.y - min_y)
            end_pt = (ent.dxf.end.x - min_x, ent.dxf.end.y - min_y)
            # 如果是外廓邊界，過濾不畫 (避免跟公式化產生的外輪廓重疊)
            if is_boundary(start_pt, end_pt):
                continue
            p1 = (map_x(start_pt[0]), map_y(start_pt[1]))
            p2 = (map_x(end_pt[0]), map_y(end_pt[1]))
            scene.add_line(p1, p2, layer=tgt_layer)
        elif ent.dxftype() == 'LWPOLYLINE':
            pts = list(ent.get_points())
            local_pts = [(float(pt[0]) - min_x, float(pt[1]) - min_y) for pt in pts]
            if len(local_pts) == 2:
                # 兩點多段線，等同於 LINE 處理。
                if is_boundary(local_pts[0], local_pts[1]):
                    continue
            elif local_pts:
                # Never classify CUTTING by vertex count: rounded/slot/handle
                # profiles routinely contain >10 vertices.  Suppress only a
                # mapped legacy structural outline whose bounds span the sheet.
                xs = [p[0] for p in local_pts]; ys = [p[1] for p in local_pts]
                tol = 1.0
                spans_sheet = (
                    min(xs) <= tol and min(ys) <= tol
                    and max(xs) >= W_base_dxf - tol
                    and max(ys) >= H_base_dxf - tol
                )
                if bool(ent.closed) and spans_sheet:
                    continue
            pts_mapped = [(map_x(x), map_y(y)) for x, y in local_pts]
            scene.add_polyline(pts_mapped, layer=tgt_layer, closed=ent.closed)
        elif ent.dxftype() == 'CIRCLE':
            cx = ent.dxf.center.x - min_x
            cy = ent.dxf.center.y - min_y
            cx_new, cy_new = map_x(cx), map_y(cy)
            handle = str(getattr(ent.dxf, "handle", "") or "")
            source_id = nameplate_ids.get(handle)
            source_type = "nameplate_mount" if source_id else None
            if source_id and nameplate_center_datum_top is not None:
                datum = float(nameplate_center_datum_top)
                if datum < 0.0 or datum > float(finished_h):
                    raise ValueError("Door nameplate top datum must be inside finished face")
                cy_new = float(finished_guide.min_point.y) + float(finished_h) - datum
            scene.add_circle(
                (cx_new, cy_new), ent.dxf.radius, layer=tgt_layer,
                source_type=source_type, source_id=source_id,
            )
        elif ent.dxftype() == 'ARC':
            if ent.dxf.radius > 50:
                continue
            pts_flattened = []
            for pt in ent.flattening(0.5):
                pts_flattened.append((map_x(pt[0] - min_x), map_y(pt[1] - min_y)))
            scene.add_polyline(pts_flattened, layer=tgt_layer, closed=False)

    # === 指示燈小門視窗：由零件角色判斷，不依賴任何 shared folder/model 名稱 ===
    if indicator_window_groups is not None:
        window = indicator_small_door_window_geometry(
            indicator_window_groups,
            total_width=new_W_dxf, total_height=new_H_dxf,
            fold_left=fl_n, fold_right=fr_n, fold_top=ft_n, fold_bottom=fb_n,
            thickness=T_val,
        )
        win_x_min = window['x_min']
        win_x_max = window['x_max']
        win_y_min = window['y_min']
        win_y_max = window['y_max']
        r_win = window['radius']
        import math
        pts_window = []
        # 右下角
        cx, cy = win_x_max - r_win, win_y_min + r_win
        for ang in range(270, 361, 5):
            rad = math.radians(ang)
            pts_window.append((cx + r_win * math.cos(rad), cy + r_win * math.sin(rad)))
        # 右上角
        cx, cy = win_x_max - r_win, win_y_max - r_win
        for ang in range(0, 91, 5):
            rad = math.radians(ang)
            pts_window.append((cx + r_win * math.cos(rad), cy + r_win * math.sin(rad)))
        # 左上角
        cx, cy = win_x_min + r_win, win_y_max - r_win
        for ang in range(90, 181, 5):
            rad = math.radians(ang)
            pts_window.append((cx + r_win * math.cos(rad), cy + r_win * math.sin(rad)))
        # 左下角
        cx, cy = win_x_min + r_win, win_y_min + r_win
        for ang in range(180, 271, 5):
            rad = math.radians(ang)
            pts_window.append((cx + r_win * math.cos(rad), cy + r_win * math.sin(rad)))

        scene.add_polyline(pts_window, layer='CUTTING', closed=True)
        # ========================================


    if indicator_hole is not None:
        hw, hh = indicator_hole
        hole_offset = Vec2(*(door_indicator_offset or (0.0, 0.0)))
        cx_hole = fl_n + (new_W_dxf - fl_n - fr_n) / 2.0 + hole_offset.x
        # 先計算預設的垂直置中位置，再套用使用者偏移。
        cy_hole = fb_n + (new_H_dxf - fb_n - ft_n) / 2.0 + hole_offset.y

        # 找出名牌孔（小圓孔 R<=2）的最大 Y，確保開孔頂端至少留 20mm
        nameplate_y_max = None
        for primitive in scene.primitives:
            if isinstance(primitive, CirclePrimitive) and primitive.radius <= 2.0:
                ccy = primitive.center.y
                if nameplate_y_max is None or ccy > nameplate_y_max:
                    nameplate_y_max = ccy
        if nameplate_y_max is not None:
            clearance = 20.0
            hole_top = cy_hole + hh / 2.0
            if hole_top > nameplate_y_max - clearance:
                # 向下移動使頂端不超過名牌孔下方 20mm
                cy_hole = nameplate_y_max - clearance - hh / 2.0

        pts_hole = [
            (cx_hole - hw/2.0, cy_hole - hh/2.0),
            (cx_hole + hw/2.0, cy_hole - hh/2.0),
            (cx_hole + hw/2.0, cy_hole + hh/2.0),
            (cx_hole - hw/2.0, cy_hole + hh/2.0)
        ]
        scene.add_polyline(pts_hole, layer='CUTTING', closed=True)

    if door_indicator is not None:
        layer_groups = tuple(int(v) for v in door_indicator)
        finished_width_n = new_W_dxf - fl_n - fr_n
        finished_height_n = new_H_dxf - fb_n - ft_n
        base_context = DoorIndicatorContext(
            finished_width=finished_width_n,
            finished_height=finished_height_n,
            left_fold=fl_n,
            bottom_fold=fb_n,
        )
        center = base_context.group_center(layer_groups) + Vec2(*(door_indicator_offset or (0.0, 0.0)))
        indicator_context = DoorIndicatorContext(
            finished_width=finished_width_n,
            finished_height=finished_height_n,
            left_fold=fl_n,
            bottom_fold=fb_n,
            center_override=center,
        )
        indicator_layout = resolve_door_indicator_layout(indicator_context, layer_groups)

        # Preserve legacy nameplate avoidance, but use the resolved interaction envelope.
        nameplate_y_max = None
        for primitive in scene.primitives:
            if isinstance(primitive, CirclePrimitive) and primitive.radius <= 2.0:
                ccy = primitive.center.y
                if nameplate_y_max is None or ccy > nameplate_y_max:
                    nameplate_y_max = ccy
        if nameplate_y_max is not None:
            clearance = 20.0
            allowed_top = nameplate_y_max - clearance
            if indicator_layout.interaction_bounds.max_y > allowed_top:
                shift_y = allowed_top - indicator_layout.interaction_bounds.max_y
                center = Vec2(center.x, center.y + shift_y)
                indicator_context = DoorIndicatorContext(
                    finished_width=finished_width_n,
                    finished_height=finished_height_n,
                    left_fold=fl_n,
                    bottom_fold=fb_n,
                    center_override=center,
                )
                indicator_layout = resolve_door_indicator_layout(indicator_context, layer_groups)

        metadata['door_indicator_layout'] = indicator_layout
        for feature in indicator_layout.features:
            scene.add_circle(feature.center, feature.radius, layer=feature.layer)
            if feature.add_centerline:
                scene.add_line(
                    (feature.center.x - feature.radius, feature.center.y),
                    (feature.center.x + feature.radius, feature.center.y),
                    layer=feature.layer,
                )

    return SceneData(scene=scene, params=params, metadata=metadata)


def get_stretched_indicator_box_data(model_name, layer_groups, T_val=2.0, corner_policy=None, *, deps):
    """Load the globally shared indicator-box baseline and add the current indicator layout.

    ``model_name`` is retained only for backward call compatibility and is intentionally
    ignored: indicator boxes are global shared parts and never inherit PW/PSR/RF.
    The shared resource itself is resolved through ``indicator_shared_baseline_part_path``.
    """
    CirclePrimitive = deps["CirclePrimitive"]
    DrawingScene = deps["DrawingScene"]
    LinePrimitive = deps["LinePrimitive"]
    SceneData = deps["SceneData"]
    _surface_from_scene_primary_cutting = deps["_surface_from_scene_primary_cutting"]
    get_indicator_box_data = deps["get_indicator_box_data"]
    indicator_box_fold_def = deps["indicator_box_fold_def"]
    indicator_shared_baseline_model_name = deps["indicator_shared_baseline_model_name"]
    indicator_shared_baseline_part_path = deps["indicator_shared_baseline_part_path"]
    source_loader = deps["source_loader"]

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

    doc = source_loader(dxf_path)
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
