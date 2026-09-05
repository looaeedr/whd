# FIX13 — 多門 / 指示燈盒 / 動態基準 / 越界防呆修改紀錄

日期：2026-08-20  
基準：FIX13  
目的：記錄本輪實際修改內容、原因、資料流與驗證結果，供後續維護與回溯。

## 1. 本輪需求整理

本輪不是建立新主頁籤，而是維持既有主 GUI 架構，強化 Door 多門與指示燈附屬件流程：

1. 多門配置需支援不同欄不同列數，例如 `2 / 3 / 2`。
2. 每一片門格 `C?-R?` 必須獨立保存：
   - 開孔資料
   - 指示燈模式
   - 指示燈層數 / 每層組數
   - 指示燈盒使用者開孔
   - 指示燈小門使用者開孔
3. Door 開孔編輯器內：
   - 第一頁維持「門板」。
   - 選「直接指示燈」時，不增加附屬頁。
   - 選「指示燈盒子」時，增加附屬頁，內含盒體與小門編輯。
   - 舊的「編輯盒子 / 編輯小門」獨立按鈕移除。
4. 指示燈盒不能只使用純公式外型：
   - 有基準型號時，盒體使用該型號的盒子基準檔。
   - 指示燈、名牌孔、MARKING 仍依目前 layer/groups 重新生成。
   - 使用者開孔再疊加。
5. 盒子基準來源不得寫死成 `指示燈` 型號；必須跟隨目前選擇的基準型號與既有 resource resolver。
6. 指示燈 / 指示燈盒不得超出該片 Door 的 finished-face；GUI 與實際 DXF export 都要有防呆。

## 2. 修改檔案

正式程式修改只有：

- `gui.py`
- `ae_engine/ae.py`
- `ae_engine/contracts.py`
- `ae_engine/manufacturing_api.py`

本文件是開發紀錄，不參與程式執行。

## 3. 多門 `2 / 3 / 2` 行為

原有資料結構本身已允許每一欄擁有不同的高度分割清單，因此本輪沒有把 Door layout 改成新的幾何架構。

保留的核心語意：

```text
Column 1 -> 2 rows
Column 2 -> 3 rows
Column 3 -> 2 rows
```

也就是橫向分隔只屬於該欄，不會因為中間欄多一條水平分隔而強迫左右欄一起切。

GUI 說明文字同步改成「各欄獨立分層」，讓使用方式與既有資料模型一致。

## 4. Door 指示燈編輯器整合

### 4.1 Door 內部頁籤

Door 統一開孔編輯器現在使用同一個交易視窗：

```text
門板
└─ 指示燈盒（僅 mode=indicator_box 時出現）
   ├─ 盒體（基準檔＋指示燈）
   └─ 小門（基準檔）
```

模式：

- `none`：不使用。
- `indicator`：直接在大門做指示燈排列。
- `indicator_box`：大門只做盒子安裝孔，並啟用盒體 + 小門附屬編輯。

### 4.2 同一交易提交 / 取消

Door、盒體、小門皆納入同一個 Confirm / Cancel transaction：

- 「確定全部」：提交 Door + 指示燈 state + 盒體 features + 小門 features。
- 「取消」：恢復開窗前所有上述資料。

切離 `indicator_box` 模式時，附屬頁可以隱藏，但該門格原有盒體 / 小門 feature list 不會因此被清除。

## 5. 指示燈盒基準檔流程

### 5.1 原始錯誤

曾錯誤把盒子當成純公式件，後來又一度把盒子來源寫死為：

```text
基準檔\指示燈\盒子.dxf
```

這會讓其他基準型號全部失去自己的盒子來源，因此已撤銷。

### 5.2 現在的正確資料流

GUI 不自行拼接固定型號路徑；使用既有基準型號來源：

```text
目前選擇的基準型號
    ↓
_baseline_source_model()
    ↓
IndicatorBoxPartSpec.model_name
    ↓
manufacturing_api baseline resolver
    ↓
ae.baseline_part_path(model_name, "盒子.dxf")
```

`manufacturing_api.expected_baseline_path_for()` 已支援 `IndicatorBoxPartSpec`，但實際路徑仍由既有 `ManufacturingContext.resource_root` / AE resource policy 決定，不在 GUI 寫死完整路徑。

### 5.3 AE 盒子基準拉伸

新增盒子基準處理入口：

- `get_stretched_indicator_box_data(...)`
- `_build_stretched_indicator_box_scene(...)`
- `export_stretched_indicator_box_dxf(...)`

盒子輸出行為：

1. 從目前基準型號解析盒子基準檔。
2. 以目前 `layer_groups` 算目標盒子尺寸。
3. 將基準盒體固定幾何 / 固定加工映射到目標尺寸。
4. 目前指示燈排列重新產生，不沿用基準檔內舊排列。
5. 疊加使用者 features。
6. 輸出 DXF。

若指定了基準型號但找不到盒子基準檔，製造 API 會回報 `AE_BASELINE_MISSING`，不偷偷假裝使用純公式件成功。

> 指示燈小門仍依既有共用規則使用 `指示燈` 的 `小門.dxf`；本輪沒有把小門改成隨目前箱體型號切換。

## 6. IndicatorBoxPartSpec 契約

`IndicatorBoxPartSpec` 新增：

```python
model_name: str | None = None
```

欄位放在既有欄位之後，避免破壞原本第三個 positional `features` 的相容性。

## 7. 越界防呆

### 7.1 為什麼必須放在 finished-face

Door layout 每一格的可用成品尺寸不同，尤其外框邊 `DoorFrameEdges` 不同時，即使起始 W/H 一樣，finished-face 也可能不同。

所以禁止用：

- 整櫃 W/H
- 展開 blank W/H
- 寫死門尺寸

判斷一律使用該片 Door 的 `finished_width / finished_height`。

### 7.2 直接指示燈

新增 `manufacturing_api.validate_door_indicator_fit(...)`。

`mode="indicator"` 時：

1. 使用既有 `resolve_door_indicator_layout(...)` 產生實際排列。
2. 量測所有生成圓孔的完整 bbox，包含圓半徑。
3. 因此實際檢查包含指示燈孔、名牌孔與 MARKING 圓等排列占用範圍。
4. 套用目前 X/Y offset。
5. bbox 任一邊超出 Door finished-face 即 `ValueError`。

### 7.3 指示燈盒

`mode="indicator_box"` 時：

1. 使用目前 layer/groups 算盒子展開總尺寸。
2. 轉成盒子 finished-face 尺寸：

```text
box_finished_w = total_w - 2*indicator_box_fold + T
box_finished_h = total_h - 2*indicator_box_fold + T
```

3. 使用 Door finished-face 中心 + X/Y offset 定位。
4. 盒子成品 bbox 超出該門即拒絕。

注意：比較的是盒子成品尺寸，不是盒子展開 blank 尺寸。

### 7.4 GUI + Export 雙層防呆

GUI：

- Door editor 即時驗證目前 indicator state。
- NG 時顯示錯誤。
- 「確定全部」停用，避免把無效狀態提交。

Headless / export：

- `_door_export()` 在真正輸出前再次呼叫安全驗證。
- 因此就算繞過 GUI 直接呼叫 manufacturing API，也不能輸出超界 Door 指示燈 / 盒子。

### 7.5 多門逐格驗證

多門不使用整櫃尺寸。

每一格都依：

```text
cell.start_width / start_height
+ cell.edges
+ FW / gap / T
→ 該格 finished-face
→ indicator fit validation
```

因此 `C1-R1` 與 `C2-R1` 即使起始尺寸相同，只要 frame edges 不同，也可能得到不同的合法結果。

## 8. 盒子安裝孔與 offset 一致化

本輪同時修正一個資料一致性問題：

- GUI 防呆使用 indicator X/Y offset。
- 實際大門上的盒子安裝孔也必須使用相同 offset。

避免出現「畫面顯示 / 防呆在某位置，但 DXF 安裝孔仍固定置中」的兩套結果。

## 9. 主要新增 / 修改入口

### `gui.py`

新增或重整的核心入口包括：

- `_validate_indicator_state_fit(...)`
- `_validate_single_door_indicator_fit(...)`
- `_validate_door_layout_indicator_fit(...)`
- `_indicator_component_editor_contexts(...)`
- Door editor `indicator_component_context_provider`
- 動態附屬 Notebook / context switching
- 多門各 cell 的盒體 / 小門 features 綁定

### `ae_engine/manufacturing_api.py`

新增或擴充：

- `expected_baseline_path_for(IndicatorBoxPartSpec)`
- `validate_door_indicator_fit(...)`
- `_validate_door_part_indicator_fit(...)`
- `_door_export(...)` export 前安全檢查
- `_indicator_box_export(...)` 支援基準盒輸出

### `ae_engine/ae.py`

新增：

- `get_stretched_indicator_box_data(...)`
- `_build_stretched_indicator_box_scene(...)`
- `export_stretched_indicator_box_dxf(...)`

### `ae_engine/contracts.py`

`IndicatorBoxPartSpec` 新增 `model_name`。

## 10. 驗證紀錄

本輪採 TDD / 回歸方式驗證，涵蓋：

- 2 / 3 / 2 非對稱多門配置。
- Door 內部指示燈盒動態頁籤。
- 每門格獨立盒體 / 小門 feature ownership。
- 同一 editor Cancel rollback。
- 小門使用既有 manufacturing API 規格。
- 盒子基準檔可由不同 model 動態解析，不固定指示燈型號。
- 盒子基準固定加工保留。
- 目前 layer/groups 指示燈排列重新生成。
- 指示燈排列過大拒絕。
- 指示燈 X/Y offset 越界拒絕。
- 盒子成品過大拒絕。
- 盒子 X/Y offset 越界拒絕。
- 多門依各格 finished-face 個別判定。
- 正常尺寸的指示燈 / 盒子仍可輸出。
- 無效 Door 在 export 前被 API 擋下，不建立錯誤 DXF。

最後針對交付 ZIP 解壓後重新執行選定回歸集，結果：

```text
60 passed
```

並檢查交付程式碼不再包含固定 `基準檔/指示燈/盒子.dxf` 的 production 路徑。

## 11. 本輪刻意不做的事情

- 不新增主 Notebook 的「指示燈盒」第一層頁籤。
- 不改箱身 / 封頭 / 封尾既有基準 resolver。
- 不把小門改成每個箱體型號各自一份；小門仍是既有 `指示燈/小門.dxf` 共用規則。
- 不把多門重構成新的 layout engine；保留既有每欄獨立 heights 資料模型。
- 不在程式內寫死使用者的磁碟絕對路徑。

## 12. 後續維護注意

後續若再改指示燈 / 指示燈盒：

1. GUI preview、Door editor、manufacturing API、DXF export 必須走同一份尺寸 / offset 語意。
2. 基準檔來源只能經既有 resolver；不可在 GUI 寫死型號或絕對路徑。
3. Door-owned 附屬件必須以該格 finished-face 驗證，不得用整櫃尺寸代替。
4. 新增任何可調位置後，要同時驗證「預覽位置 = 安裝孔位置 = export 位置」。
5. 修改交易式 editor 時，要保留 Confirm commit / Cancel rollback 對所有 component context 的一致性。
