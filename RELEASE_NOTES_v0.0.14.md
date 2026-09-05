# WHD 板金展開自動化系統 Release Notes (v0.0.14)

**發布日期**：2026-08-11
**版本號**：`v0.0.14`
**Git 標籤**：`v0.0.14`
**分支**：`new-engine`

---

## 🌟 核心更新重點 (Highlights)

### 1. 幾何引擎與拓撲拆分 (`sheetmetal_geometry.py`)
- **全面淘汰硬編碼 12/16/17 點主外框**：轉為 Shapely 2D Polygon 布林運算（Base Polygon − Relief Polygon = Material CUTTING）。
- **Topology 與 Factory Policy 徹底分離**：
  - `FourSideFlange` 通用四折邊拓撲：適用於 Door、Indicator Box、Base Plate、End Cap / Tail。
  - `StripFoldChain` 單向連續折彎拓撲：適用於 Box Body。
  - 金庫型封頭尾裝配退讓（Assembly Insertion Relief）收斂為專用 Factory Policy，不污染宇宙通則。
- **幾何成為唯一真相來源**：GUI 預覽與 DXF 匯出統一存取同份 Geometry Result。

---

### 2. GUI 結構預覽與畫布繪圖重構 (`sheetmetal_drawing.py`, `gui.py`)
- **DrawingScene 繪圖語意層**：建構 `DrawingScene` 與 `SceneData`，將 `CUTTING`、`BEND`、`CHECK`、`STOCK`、`DATUM` 幾何圖元統一封裝。
- **完全同步**：畫布看到的 2D 展開形狀與最終輸出的 DXF 檔案 100% 精確對齊。
- **支援全螢幕模式**：新增 `F11` 鍵與 ToolBar 按鈕無縫切換原生全螢幕/視窗還原。

---

### 3. 統一開孔編輯器與圖冊升級 (`hole_catalog.py`, `sheetmetal_features.py`)
- **跨 7 大零件統一編輯器**：Box Body、Door、Base Plate、Indicator Box、Indicator Door、Head、Tail 統一採用此編輯器介面。
- **雙目錄載入**：同時支援 `一般開孔`（`開孔.csv`）與 `管孔清單`（`管孔尺寸清單.csv`，自動解析 `Ø` 圓形規格）。
- **九宮格參考基準點 (Crosshair Anchor)**：
  - 支援 `中心`、`中上`、`中下`、`中左`、`中右`、`左上`、`左下`、`右上`、`右下` 九位基準。
  - 右鍵選單精確定位，懸浮面板緊隨游標避讓外框。
- **成品邊界參考 (Finished Boundary)**：
  - 外框測量顯示真實成型/裝配尺寸（非純展開折彎線距），直覺提供工程師依據裝配邊界定位孔位。
- **圓孔陣列與對齊工具 (Round Hole Pattern)**：
  - 提供 6 方向延伸、`孔心距` 與 `間距` 動態雙向同步。
  - 支援多孔時 `孔心齊`、`管頂齊`、`管底齊` 等快速對齊功能。
- **復原與撤銷 (Undo/Redo)**：
  - 內建 `EditorUndoHistory` 支援最多 50 步撤銷 (`Ctrl+Z` / `↶ 回上一步`)。

---

### 4. 專案工程化與測試套件 (`tests/`)
- **測試架構遷移**：所有 `test_*.py` 單元測試檔收合至 `tests/` 目錄並建立 `conftest.py`。
- **測試全數通過**：全套 211 項測試通過驗證（`211 passed in 2.29s`）。
- **正式建立自動發布腳本**：新增 `deploy_release.bat`，內建單元測試自動驗證與發布。
