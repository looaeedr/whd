# Phase6 UI 狀態回歸防護

## 本輪症狀

1. 沒有新增「指示燈盒」時，主 GUI 仍顯示盒體／小門尺寸。
2. 進入 3D 並選擇板件後，沒有回首頁的導航。
3. 原本的「進階設定」名稱被 RELIEF / 舊 NOTCH 相容參數佔用，與正式 CornerType 混在一起。
4. 指示燈盒／小門的「存在狀態」曾和 export checkbox 綁在一起，存在但未勾輸出時可能從 3D 現有板件消失。

## 正確狀態規則

### 指示燈盒／小門

- 單門：只有 `is_indicator_box_var=True` 才存在盒體／小門尺寸。
- 直接指示燈模式不顯示盒體／小門尺寸。
- 多門：結果區只看目前選取 cell；該 cell 的 `mode=indicator_box` 才顯示尺寸。
- 沒有盒子時四個結果欄一律為 `-`。
- 盒體／小門 export 預設關閉。
- export 執行時再次以實際 `indicator_box` presence 做 gate，checkbox 不得憑空產生零件。
- 反方向也成立：零件是否存在不得由 export checkbox 決定；有盒子時 3D 仍能看到盒體／小門，即使 export 未勾。

### 3D 首頁

- `首頁` 按鈕永久存在於板件選擇列。
- 首頁 → 板件：收起全域設定，顯示板件折彎／設定／3D。
- 板件 → 首頁：保存目前 3D 工作草稿到本次 transaction，但不等於主 GUI「確定」。
- 回首頁後恢復全域設定，收起板件折彎、右側設定與 3D canvas。
- `取消` / `確定` 交易語意不變。

### 進階設定與截角參數

- 正式 CornerType 維持獨立的截角類型／參數 UI。
- 真正的板件「進階設定」包含原本製造參數群，例如：補償、固定孔、封尾固定孔、門縫、收縮。
- `Relief` 與舊 `NOTCH` 不再顯示在 3D 首頁；正式截角只由各板件每個角的 CornerType 參數提供操作入口。
- RELIEF／NOTCH 舊欄位只保留設定檔載入相容，不再形成第二套可編輯截角來源。
- 折彎欄位仍由左側 FoldChain 編輯器負責，不在右側重複。

## 永久 TEST

新增 `tests/test_phase6_ui_state_regressions.py`，鎖住：

- none / direct indicator 不得顯示盒／小門尺寸。
- indicator_box 才顯示真實尺寸；1 層 2 組、T=2 驗證為盒 `396×445`、小門 `323×372`。
- 多門只看 selected cell 的 mode / layer_groups。
- 盒／小門 export 預設關閉且實際 export 有 presence gate。
- 3D 現有零件不可被 export checkbox 決定。
- `首頁` 按鈕永久存在；板件→首頁不觸發 confirm/cancel。
- 「進階設定」保留真正板件製造參數；3D 首頁不得再顯示 RELIEF／舊 NOTCH 相容控制。
- 實際 Tk smoke 驗證主 GUI 預設尺寸、模式切換、首頁→門→首頁。

## 修改檔案

- `gui.py`
- `fold_designer_bridge.py`
- `tests/test_phase6_ui_state_regressions.py`
- `tests/test_phase6_3d_view_regressions.py`
- 本文件

## 驗證

完整套件測試：

```bash
xvfb-run -a env PYTHONPATH=. pytest -q
```

本輪工作目錄結果：`66 passed`。

## 3D 視覺與展開尺寸後續修正

- 取消畫面下方舊「CAD 展開標註圖」顯示；原始 renderer 檔案保持不修改，由 bridge 將舊 2D axes 隱藏並把 3D axes 擴展到原空間。
- 滑鼠游標位於 3D axes 時，滾輪向上放大、向下縮小；縮放只改 Matplotlib 視野，不寫入 W/H/D、折彎、截角或任何製造設定。
- 縮放倍率在同一 3D 編輯視窗內持續保留，任何重新繪製都會重新套回倍率。
- 板件設定標題列新增「展開尺寸：W × H mm」。尺寸由目前實際 material profile 計算；箱身寬度另包含 `z_comp`，高度優先依 head/tail CornerType 裝配語意計算。
- 新增 `tests/test_phase6_3d_view_regressions.py`，鎖住首頁無重複截角來源、3D-only 版面、滾輪縮放、尺寸顯示與縮放不污染製造設定。
