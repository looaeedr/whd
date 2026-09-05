# FIX13 — 指示燈盒 / 小門全域共用與 Door 三分頁顯示修正

日期：2026-08-20

## 使用者確認規則

1. `門板` 是盤體 / 門格自己的零件：
   - 門板外形與門板基準檔跟目前盤體型號走。
   - 門板頁只顯示門板自己的固定開孔、使用者開孔與 Door-owned 開孔。
2. `指示燈盒` 是全域共用零件：
   - 不分 PW / PSR / RF / 未知類型。
   - 不繼承目前盤體型號。
   - 基準資源由共用 indicator baseline resolver 解析，不由 GUI 拼接實體路徑。
   - 盒體頁顯示盒體自己的外形、固定加工特徵、指示燈 / 名牌 / MARKING 與盒體使用者開孔。
3. `指示燈小門` 是全域共用零件：
   - 不分 PW / PSR / RF / 未知類型。
   - 一律載入共用小門基準。
   - 小門頁顯示小門自己的外形、基準開孔與小門使用者開孔。
4. 單門與多門使用相同 ownership 規則。

## 本次發現的根因

前一版有兩個互相疊加的錯誤：

- 盒子錯誤地使用 `_baseline_source_model()`，因此會嘗試讀取 `PW/盒子.dxf`、`PSR/盒子.dxf` 等型號專屬路徑；這違反「盒子全域共用」。
- 小門在主盤體為未知類型時，會跟著走未知類型 / 手動截角分支，造成小門自己的共用基準圖被捨棄。

此外，前一輪測試只驗 context 建立，沒有完整驗證實際 Tk Notebook 切換後畫布與開孔清單，因此「三頁看起來像同一張」沒有被完整鎖住。

## 實作修改

### `ae_engine/ae.py`

- 新增 `INDICATOR_SHARED_BASELINE_MODEL` 作為共用 indicator 資源 namespace。
- 新增：
  - `indicator_shared_baseline_model_name()`
  - `indicator_shared_baseline_part_path(filename)`
  - `indicator_shared_baseline_source_label(filename)`
- 共用 resolver 最終仍委派既有 `baseline_part_path()` / `get_resource_path()`；沒有在 GUI 或 exporter 寫死絕對資源路徑。
- `get_stretched_indicator_box_data()` 不再採用傳入的 PW/PSR/RF 型號；盒子固定解析全域共用盒體基準。
- `get_stretched_door_data()` 對共用 indicator 小門改走同一共用 resolver。

### `ae_engine/manufacturing_api.py`

- `IndicatorBoxPartSpec.model_name` 不再決定盒子基準來源。
- `expected_baseline_path_for(IndicatorBoxPartSpec)` 固定解析全域共用盒子資源。
- `_indicator_box_export()` 強制使用共用盒子基準；即使 caller 傳入 `model_name='PW'` 也不得變成 PW-owned box。
- `indicator_small_door_spec()` 與 Door exporter 的小門判斷統一使用共用 indicator namespace。

### `gui.py`

- `_indicator_box_part_spec()`：盒子不再帶 `_baseline_source_model()`，也不繼承盤體 unknown/manual corner 狀態。
- `_indicator_component_editor_contexts()`：
  - 門板維持門板 context。
  - 盒體固定建立共用盒體 scene / surface / W / H / feature list。
  - 小門固定建立共用小門 scene / surface / W / H / feature list。
- `draw_indicator_box()`：不再依主盤體型號切換盒子來源。
- `draw_indicator_door()`：主盤體即使是未知類型，小門仍載入自己的共用 baseline，不再退回 generic rectangle。
- 單門 `open_part_hole_editor()` 與多門 cell editor 都使用同一組 component context provider。

## 三分頁 ownership

同一個 Door 編輯交易中：

- `門板`：使用 `surface_features['door']`（多門為該 cell 的 `door_layout_features[key]`）
- `盒體`：使用 `surface_features['indicator_box']`（多門為 `door_layout_indicator_box_features[key]`）
- `小門`：使用 `surface_features['indicator_door']`（多門為 `door_layout_indicator_door_features[key]`）

切換頁籤時，畫布的 surface、baseline scene、W/H、reference guide、開孔 list 都跟著 active part context 切換；不允許三頁沿用同一個 Door context。

## 單門實際 GUI 驗證

測試條件：主盤體 `未知類型`、Door 1000×1000、指示燈盒 1 層 / 2 組。

實際 Tk Notebook 逐頁切換後顯示：

- 門板：`935 × 935 mm`
- 盒體：`300 × 349 mm`
- 小門：`290 × 340 mm`

另以 Ø11 / Ø22 / Ø33 三組不同使用者孔分別放在門板 / 盒體 / 小門；逐頁切換時開孔 list 僅顯示該零件自己的孔。

## 多門實際 GUI 驗證

使用 1000×1000、多門 cell `C1-R1` 實際打開同一 unified editor 並逐頁切換：

- C1-R1 門板：`464 × 464 mm`
- 共用盒體：`300 × 349 mm`
- 共用小門：`290 × 340 mm`

多門換 cell 時，只有門板依該 cell 的 `DoorFrameEdges` / 起始尺寸改變；盒體與小門仍維持同一套全域共用零件規則。

## 測試

本次新增 / 更新的核心回歸包含：

- 盒子 spec 不繼承 cabinet model。
- 即使 spec 夾帶 `model_name='PW'`，API expected path 仍指向共用盒子 baseline。
- PW → PSR → 未知類型切換不改變盒子 / 小門 context 尺寸與基準 ownership。
- 單門實際 Tk Notebook：門板 / 盒體 / 小門三頁尺寸互異，開孔清單各自獨立。
- 多門實際 Tk Notebook：同樣驗證三頁尺寸與各自開孔清單。
- 盒子 baseline 固定特徵保留，動態 indicator layout 依 layers / groups 更新。
- 既有 Door indicator fit guard、2/3/2、多門 transaction、factory reset、startup contract 回歸。

相關 targeted suite：`64 passed`。

完整歷史 suite 中仍存在先前版本即存在的 Fold Designer face-feature 測試失敗；已用本次修改前正式檔案重現相同失敗，因此本次沒有擴張修改該無關模組。

## 本次刻意未改

- 門板仍依目前盤體型號 / unknown policy 處理。
- 盒子與小門仍由 layers / groups 決定其尺寸公式與動態孔配置；「全域共用」是指基準零件 ownership，不是固定死尺寸。
- 既有指示燈 / 盒子 fit guard 保留。
- 2 / 3 / 2 各欄獨立分層資料模型保留。
- Confirm / Cancel transaction、真初始值 / factory reset、Fold Designer 其他板件不在本次修改範圍。
