# Phase6 3D 真實 CUTTING Mesh 與視野 Fit 計畫

## 目標

讓 3D 預覽直接使用既有製造引擎產生的 CUTTING 幾何，不再只畫完整矩形板面或浮動孔線；同時解除 Matplotlib 3D 強制正方形 viewport，讓長窄板件能真正利用左右畫面空間。

## 核心約束

- `fold_designer_original.py` 維持 byte-identical，不修改原 renderer。
- 不在 3D 重寫開孔或 CornerType 公式。
- 3D 的外框、截角、孔洞都來自現有 `DrawingScene` 的 `CUTTING` primitives。
- BEND 只負責把展開面分段映射到折彎後 3D，不改製造尺寸。
- 滾輪只調整視覺 zoom，不改 W/H/D、FoldChain、CornerType 或孔位。
- GUI 只補 3D preview 所需的 indicator mode/groups/offset snapshot，不建立第二套狀態。

## 實作資料流

```text
目前板件 runtime state
  + CornerType policy
  + surface_features / 固定孔
  + indicator mode/groups/offset
        ↓
既有 AE / manufacturing builder
        ↓
DrawingScene.CUTTING
        ↓
外輪廓 - CUTTING 內輪廓 - CUTTING circles
        ↓
Shapely material polygon
        ↓
依 FoldChain X/Y 分割 + triangulate
        ↓
每個三角面沿既有 fold profile 映射到 3D
        ↓
Poly3DCollection 真實板面
```

## 視野 Fit

舊 renderer 使用 `max_b` 把 X/Y/Z 綁成同一立方體範圍；此外 Matplotlib `Axes3D.apply_aspect()` 會再把實體 viewport 縮成正方形，造成長窄模型左右大量留白。

本次只對 Phase6 bridge 建立的 `Axes3D` 實例覆寫 aspect placement：

- X/Y/Z limits 各自依 mesh bbox + padding 計算。
- 3D axes 使用整個可用寬度，不再被 `apply_aspect()` 縮回正方形。
- 不修改 Matplotlib 全域行為。

## 永久 Regression TEST

新增 `tests/test_phase6_3d_cutting_mesh.py`：

- CUTTING Circle 會成為真洞。
- CUTTING closed profile 會成為真洞。
- 截角缺料會反映在 mesh 面積。
- 折彎後 mesh 保留展開 CUTTING 面積並產生真實 Z 深度。
- X/Y/Z fit 保留實際比例，不回到 `max_b` cube。
- 實際 Tk Door：使用 surface feature、CornerType 後 renderer 會更新真實 mesh。
- indicator box 固定孔、small door window 會成為真洞。
- 3D axes 實際寬度必須使用 >95% figure，防止 Matplotlib square viewport 回歸。

另以實際 Tk smoke 驗證 Door：

- 直接指示燈模式會產生實際 CUTTING 洞。
- 指示燈盒模式會產生實際盒開口。

## 修改檔案

- `gui.py`
- `fold_designer_bridge.py`
- `tests/test_phase6_3d_cutting_mesh.py`
- `docs/superpowers/plans/2026-08-21-phase6-3d-cutting-mesh-and-view-fit.md`
- `DELIVERY_README.md`
- `修改日誌/20260821.md`
