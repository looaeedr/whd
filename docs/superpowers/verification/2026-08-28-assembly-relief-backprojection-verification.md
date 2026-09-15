# 3D 干涉反投影正式截角驗證 — 2026-08-28

## 結論

本輪已完成 Box Body ↔ Head/Tail 的 `3D physical interference → flat UV backprojection → 2D cut polygon → clearance A → rebuild CUTTING/BEND → refold verification` 閉環。只有回折後剩餘 material interior 無非共面實體穿透，solution 才標記 `verified=True`。

## Source of Truth / ownership

- Box Body = RETAIN；Head/Tail = CUT。
- `ae_engine/assembly_geometry.py`：保留 flat UV 的 folded geometry、physical skins、shared assembly world transform。
- `ae_engine/assembly_collision.py`：world crossing、barycentric backprojection、corner topology-band cut、迭代求解、clearance A、3D refold verification。
- `ae_engine/manufacturing_api.py`：verified cut 套回正式 CUTTING；從 authoritative Fold Profile 重建並依新 material 重新 clip BEND。
- GUI / renderer 只顯示 solver 結果，不得自行建立截角公式。

## 幾何證據

### 標準 regression：W500 × H600 × D200, T2, FW24

- A=0：Head/Tail 左右角皆 `39×38 + 14×4 mm`。
- legacy fixed relief 第二級為 `16×4`，因此該 regression 由真實 3D 干涉證明 legacy 第二級多切 2 mm；此數值只作 regression evidence，不得硬寫成通用公式。
- A=5：精確變為 `44×43 + 19×4 mm`；重新折回後仍零材料穿透。
- Head/Tail 原孔數保持不變。

### 真主 GUI 自檢

目前程式預設標準金庫型第一次進 3D 組合體、解鎖並 real update 後：

- `實際截角尺寸：封頭：40×39 + 14×4；封尾：40×39 + 14×4`
- `3D驗證：封頭✓ 封尾✓（零材料穿透）`
- A 預設為 0。

這再次證明尺寸依目前 W/D/FW/Fold Profile 動態求解，不是固定寫死 39/38/14/4。

## BEND re-clip 驗證

verified dynamic CUTTING 比 legacy fixed relief 少切材料時，BEND 必須跟著恢復：

- 標準 regression 左 X BEND：legacy `span_start=42` → dynamic `span_start=38`。
- FW 水平 BEND 左端：legacy `span_start=16` → dynamic `span_start=14`。
- BEND 來自 authoritative Fold Profile，並用新的 material intersection clip；不得沿用舊固定截角時截短的線。

## 數值穩定性

- 近似鏡像 corner cuts 只有在 canonical Hausdorff distance 落在嚴格容差內才 harmonize；以 canonical union 消除 triangle tessellation 微小噪音。
- 真非對稱幾何不會被強制對稱。
- clearance A 不使用一般 polygon buffer；改在已驗證正交級距上做精確軸向擴張，消除 `3.992` / `18.997` 類數值噪音。

## Fresh focused regression

執行：

```text
xvfb-run -a python -m pytest -q \
  tests/test_assembly_collision.py \
  tests/test_assembly_collision_integration.py \
  tests/test_phase6_assembly_3d_view.py \
  tests/test_phase6_latest_layout_contract.py \
  tests/test_phase6_final_scene_view_ownership.py \
  tests/test_phase6_shared_assembly_and_dimensions.py \
  tests/test_endcap_head_mirror.py \
  tests/test_endcap_regression_and_text_scale.py \
  tests/test_endcap_resolved_geometry_ownership.py \
  tests/test_original_fold_designer_gui_integration.py::test_committed_verified_assembly_relief_flows_into_endcap_partspec_and_invalidates_on_dimension_change
```

結果：`135 passed / 0 failed`。

## 廣泛 regression 的既有紅燈對照

較廣泛 suite 在工作樹為 `152 passed / 13 failed`；把完全未修改的 `PHASE6_ASSEMBLY_RELIEF_DELTA_DIAGNOSTIC_FULL_20260828_081810.zip` 跑同一批，結果為 `134 passed / 13 failed`，13 個失敗名稱與症狀相同。它們屬既有 legacy GUI contract、假 DXF fixture、Indicator baseline/adapter 測試問題，不是本輪 backprojection 造成。

## 交付防線

- `config.ini` SHA256 必須與 081810 基準相同。
- 所有文字 UTF-8 strict decode；不得有 U+FFFD。
- ZIP entry 不得出現 literal `#Uxxxx`。
- UPDATE archive root 直接是專案根目錄檔案，不得多包 `新WHD/`。
- UPDATE 實際套到 081810 FULL 副本後，必須重跑同一組 135 個 focused tests，並逐檔 SHA256 比對工作樹。

## 最終封裝驗證

- 基準：`PHASE6_ASSEMBLY_RELIEF_DELTA_DIAGNOSTIC_FULL_20260828_081810.zip`。
- 最終交付時間戳：`20260828_130705`（Asia/Taipei）。
- UPDATE 相對基準共有 19 個新增／修改檔，`config.ini` 不在 UPDATE 且 SHA256 與基準完全相同。
- FULL `testzip=None`；UPDATE `testzip=None`。
- UPDATE 實際解壓覆蓋到 081810 基準副本後，19 個檔案逐檔 SHA256 與工作樹一致：`0 mismatch`。
- FULL 實際解壓後逐檔 SHA256 與工作樹一致：`0 mismatch`。
- 套用 UPDATE 後再次執行本文件 focused regression：`135 passed / 0 failed`。
- UTF-8 strict 掃描 640 個文字檔：`0 decode error`、`0 U+FFFD`；路徑 literal `#U` = 0。
