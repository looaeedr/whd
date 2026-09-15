# 截角類型／裝配語意整合設計

## 目標

把截角類型從舊的 `C01~C04 + rotation` 截角代碼，升級成唯一的製造／裝配語意來源。GUI、3D 折彎設計器、AE 幾何引擎、製造 API 與箱身孔位映射都必須使用同一份截角 policy，不再另外建立會與截角狀態衝突的「裝配方式」旗標。

## 已確認的製造語意

### 1. 十字截角（內部代碼 `CROSS`）

十字截角有三種方式：

- `標準`：不做額外補償。
- `單邊留肉`：方向為 `寬` 或 `高`，留肉量為可調 `xT`，預設 `1T`。
- `多切`：方向為 `寬＋高` / `寬` / `高`，多切量為可調 `xT`，預設 `0.5T`；切換進多切方式時，預設方向必須是 `寬＋高`，不能沿用上一個方式留下的方向。

GUI 不再顯示 X/Y 或 0°/90° 旋轉來表達這些製造語意。

### 2. 貼外型（內部代碼 `OVERLAY`，此節描述封頭／封尾上方裝配截角）

- 上方裝配角為單級截角。
- **此處的 `OVERLAY` 上方裝配角**必定留肉，不能把它本身改成 `CROSS/EXTRA_CUT`；封頭／封尾下方截角是另一個獨立加工角，可使用既有 `CROSS` 多切能力。
- 留肉方向固定為 `高`，不讓使用者另外選方向。
- 留肉量可調，預設 `1T`。
- 此型代表該端具有貼外裝配關係，因此佔外部總高 `1T`。

### 3. 嵌入型（內部代碼 `INSERT`，此節描述封頭／封尾上方裝配截角）

- 單級截角。
- 禁止留肉；為了能塞進箱身，必定多切。
- 多切方向固定為 `高`。
- 多切量可調，通常預設 `1T`。
- 此型代表純嵌入裝配，因此該端不佔外部總高。

### 4. 嵌入貼外型（內部代碼 `INSERT_OVERLAY`，此節描述封頭／封尾上方裝配截角）

此型同時完成嵌入與貼外兩個作用，因此必定是二級截角。

- 第一級：貼外留肉，方向固定為高，預設 `1T`。
- 第二級：使用者輸入「嵌入留肉」，預設 `0.5T`；不得要求使用者換算成多切量。
- 第二級深度：預設 `2T`，可調。
- **正確二級 CUTTING = 側折 + 嵌入留肉量**。UI 的「嵌入留肉」不直接代表兩級之間剩餘寬度；兩級之間實際剩餘材料由程式推導為 `FW - 嵌入留肉量`。
- 此型仍具有貼外裝配關係，因此該端佔外部總高 `1T`。

例如 `FW=25, T=2, 側折=15, 嵌入留肉=0.5T`：`0.5T=1mm`，第二級位置為 `15 + 1 = 16 mm`；兩級之間剩餘材料寬度則為 `25 - 1 = 24 mm`。

## 舊資料相容

舊資料仍允許輸入 `C01~C04`，但進入引擎邊界後必須立即轉換成新的製造語意；新 GUI 不再顯示 `C01~C04`。

- `C01` → 十字截角／標準。
- `C02` → 十字截角／單邊留肉／`1T`；舊 rotation 僅在相容轉換時映射成寬或高。
- `C03` → 十字截角／多切／寬＋高／`0.5T`。
- `C04` → 嵌入貼外型／貼外留肉 `1T`／嵌入留肉 `0.5T`／深度 `2T`。

舊 `C04` 的實際二級 CUTTING 幾何必須保持 `側折 + 0.5T`、深度 `2T`。UI 可以把 `0.5T` 呈現為「嵌入留肉」，但不得再把 `FW - 0.5T` 當成第二級 CUTTING 座標。

## 截角類型就是裝配關係

不建立第二套 `assembly_type`、`is_insert`、`occupies_outer_t` 等可由使用者獨立修改的狀態。這些若存在只會造成「截角是嵌入、裝配卻是貼外」的矛盾。裝配關係必須直接由截角類型推導：

- 純嵌入型 → `0T` 外高占用。
- 貼外型／嵌入貼外型 → `1T` 外高占用。

資料流固定為：

`截角類型 → 截角算法 → 留肉/多切 → 裝配關係 → 板件尺寸 → 箱身高度 → CUTTING/BEND/3D/孔位基準`

## 箱身高度

箱身實際高度由封頭與封尾的截角 policy 直接推導：

`箱身高度 = H - 封頭外高占用 - 封尾外高占用`

其中每一端的占用只能由截角類型產生。

- 上下皆有貼外關係 → `H - 2T`
- 一端純嵌入、一端有貼外 → `H - T`
- 上下皆純嵌入 → `H`

既有金庫型預設仍維持 `H - 2T`，確保未指定新 policy 的既有流程不退化。

## 箱身孔位與特徵座標責任

箱身 CUTTING 高度改變時，孔位與面特徵映射不可仍寫死上下各 `1T`。`BoxBodyFaceContext` 必須接收由截角類型推導出的上／下外高偏移，並用同一份偏移處理：

- 成品面座標 → 展開座標。
- 展開座標 → 成品面座標。
- 基準箱身固定特徵。
- 使用者面特徵。

這可避免「外框高度正確，但孔位仍依 `H-2T` 舊基準偏移」的錯誤。

## 對外資料契約與製造 API

`BoxBodyPartSpec` 增加兩個內部欄位：

- `head_corner_policy`：封頭截角 policy。
- `tail_corner_policy`：封尾截角 policy。

`manufacturing_api` 必須原樣傳給 `ae.export_box_body_dxf()`；AE 場景建立、基準特徵映射與面座標建立都必須使用同一份 policy。

## GUI 狀態與保存

每一個截角選擇都必須完整保存以下內部欄位，而不是只保存 `type_id + rotation`：

- `type_id`
- `cross_mode`
- `direction`
- `amount_t`
- `secondary_retain_t`
- `secondary_depth_t`

必須同時保證：

1. 主 GUI 快照／還原不丟參數。
2. 3D 折彎設計器 Bridge 的原始狀態不丟參數。
3. `config.ini` 截角預設值來回保存不丟參數。
4. `apply_manual_corner_selection()` 在左右相同／分離切換時不洗掉參數。

## GUI／3D 折彎設計器呈現方式

正式可編輯類型只顯示繁體中文：

- 十字截角
- 貼外型
- 嵌入型
- 嵌入貼外型

禁止把以下內容當成使用者操作名稱：

- `C01/C02/C03/C04/C05`
- `0°/90°` 截角旋轉
- `CROSS / OVERLAY / INSERT / INSERT_OVERLAY`

十字型依方式動態顯示方向與 `xT`；貼外／嵌入顯示單一 `xT`；嵌入貼外顯示三個 T 參數。

已知固定板件仍需顯示所使用的截角類型，但為唯讀。`indicator_box` / `indicator_door` 是程式內部板件代碼，對應 GUI 的「指示燈盒／指示燈小門」；即使箱型為「自訂」也不得變成可編輯截角。

## 自訂模式資料繼承

GUI 的使用者名稱統一為 **「自訂」**；舊資料中的 `未知類型` 只保留相容讀取，不再顯示在新介面。

「自訂」不是另一套空白預設，也不是重新初始化板件。從已知基準型號切換到「自訂」時，必須以**切換當下目前有效資料**作為起點：

- W/H/D/T 與目前板件尺寸保持不動。
- 目前折彎尺寸與 3D 工作區保持不動。
- 目前已建立的使用者孔位／Feature 物件保持不動，不重建清單。
- 封頭、封尾、門、底板的固定截角規則複製成可編輯 `CornerTypeSelection`。
- 共享指示燈盒／指示燈小門仍是固定板件，不因切到「自訂」而解除截角限制。

目前金庫型固定截角複製關係：

- 封頭／封尾上方：嵌入貼外型，貼外留肉 `1T`、嵌入留肉 `0.5T`、深度 `2T`。
- 封頭／封尾下方：十字截角／多切／寬＋高／`0.5T`。
- 門：十字截角／單邊留肉／寬／`1T`。
- 底板：十字截角／標準。

3D 折彎設計器必須使用同一規則。若使用者從自訂切回已知型號，再從該已知型號重新切入自訂，應重新複製**目前已知型號**的固定規則，不得偷偷恢復上一份舊自訂截角草稿。

## 原始 3D Renderer 邊界

`fold_designer_original.py` 的 Renderer 製造幾何與原操作模型保持不動。Phase6 Bridge 只負責資料轉換與設定 UI，不把截角製造邏輯複製到 renderer。唯一允許的 UI 變更是讓 Renderer 的文字 `fontsize` 乘上全域字級倍率。

## 本次不處理

- 不重寫原 3D Renderer 的幾何／操作模型；只加入文字倍率。
- 不改 RO／落地盤尚未確認的箱型幾何。
- 不建立獨立裝配模式。
- 不把截角計算重新分散到 GUI、AE、Bridge 各算一份。

## 驗收條件

1. 四個正式截角語意與參數均可由引擎解析。
2. `C01~C04` 可相容讀取，但新 GUI 不顯示舊代碼。
3. `C04`／嵌入貼外第二級 CUTTING 維持 `側折 + 0.5T` 相容幾何；UI 仍以「嵌入留肉」呈現。
4. 箱身高度依封頭／封尾 policy 得到 `H-2T / H-T / H`。
5. 箱身孔位與面特徵使用相同的上／下偏移。
6. GUI、Bridge、INI 來回保存均保留全部截角參數。
7. 已知板件顯示固定截角摘要；共享指示燈板件不可編輯。
8. `fold_designer_original.py` 只允許文字縮放相關變更，不得改製造幾何。
9. 既有金庫型預設與封頭尾 5 條 BEND 拓撲保持相容。
10. 使用者可見的新增截角 UI 與交付文件使用繁體中文。
11. 型號清單顯示「自訂」，不顯示舊「未知類型」；舊字串仍可相容讀取。
12. 已知型號切入自訂時，尺寸／折彎／使用者孔位保持不動，固定截角複製成可編輯狀態。

## 全域文字大小

- 使用者可選 **文字大小：小 / 中 / 大**。
- 「小」就是本次修改前的既有字級，倍率 `1.0×`。
- 「中」倍率 `1.2×`；「大」倍率 `1.4×`。
- 選擇為全域 UI 偏好，保存於 `config.ini` 的 `[UI] text_size`，下次啟動沿用。
- 主 GUI、設定區、截角區、輸入框、按鈕、分頁、Tk Canvas 文字、3D/2D Matplotlib 標註都必須使用同一倍率。
- 字級變化不得改變任何 CAD 幾何、展開尺寸、BEND/CUTTING 座標、DXF 或加工參數。
## 2026-08-23 補充：截角資料層級與貼外型封頭尾

### A. 現有截角系統的四個資料層級

不得再把「截角類型」「十字模式」「方向」「倍率」混成同一件事。現有資料模型分成：

1. `type_id` / `CornerTypeId`：正式截角類型。
   - `CROSS`：十字截角。
   - `OVERLAY`：貼外型。
   - `INSERT`：嵌入型。
   - `INSERT_OVERLAY`：嵌入貼外型。
2. `cross_mode`：只在 `CROSS` 有製造意義。
   - `STANDARD`：標準，不做額外留肉／多切補償。
   - `RETAIN`：單邊留肉。
   - `EXTRA_CUT`：多切。
3. `direction`：`RETAIN` / `EXTRA_CUT` 的作用方向。
   - `WIDTH`：寬方向。
   - `HEIGHT`：高方向。
   - `BOTH`：寬＋高；只有模式允許時才使用。
4. `amount_t`：以板厚 T 為單位的留肉／多切倍率，例如 `0.5T`、`1T`、`1.5T`。它不是新的 CornerType。

因此 `CROSS + EXTRA_CUT + WIDTH + 1.5T` 已能由既有資料模型完整表示，不得為相同幾何再新增新的截角類型。

### B. `CROSS + EXTRA_CUT` 的機械語意

`EXTRA_CUT` 是「產生額外避讓切除」的幾何工具，機械目的不只一種。

- 一般十字角：可用來避讓**同一片板金**折起後的折邊干涉。
- 組裝角：也可用來避讓**另一片板金**的板厚或折起後實際占用。

因此「本板沒有 X 折彎」不代表 WIDTH 多切必然無效。若組裝後另一板金會占據該區域，`X fold = 0 + extra cut` 仍可形成正確的避讓缺口。判斷依據是實際折後／組裝形態，不是只看本板是否有同方向折線。

### C. 封頭／封尾上、下截角責任分離

- 封頭／封尾**上方 CornerType**是與箱身組合方式的裝配語意真值。
- 下方截角是另一個加工角，可使用 `CROSS` 的標準／留肉／多切等既有能力。
- `assembly_type` 若保留，只能當 UI／舊檔相容 mirror；載入時不得反向覆寫已存在的 Head/Tail 上方 CornerType。

### D. 貼外型（`OVERLAY`）封頭／封尾的已確認形態

當使用者明確把箱體組合方式選成貼外型：

1. Head / Tail **左右 X 向折彎不存在**。
   - X 向 Fold profile 不得生成可折角度。
   - Final 2D 不得生成左右 X BEND。
   - 3D 不得折出左右 X 面。
   - Fold Designer 的 Head/Tail 不顯示 X 軸折彎編輯頁，只保留實際存在的 Y 向折彎。
   - X 向 structural blank / CUTTING 外框也必須使用 flat topology：總寬直接等於 `W`，`left_fold=right_fold=0`。不得用 `W-4T+yl1+yr1` 保留舊 INSERT 型材料寬。
   - 例：`W=400, T=2, yl1=yr1=15` 時，OVERLAY Head/Tail X span = `400`，不是 `422`。
2. 下方截角在這次**明確選擇 OVERLAY**時，自動帶入既有十字多切預設：
   - `type_id = CROSS`
   - `cross_mode = EXTRA_CUT`
   - `direction = WIDTH`
   - `amount_t = 1.5`
3. 上述 `WIDTH + 1.5T` 是「選擇貼外型時的初始預設」，不是 `CROSS` 的全域預設，也不是不可修改的固定規則。
   - 使用者之後可改 `HEIGHT`、`BOTH`、倍率或其他既有下方截角設定。
   - 普通 redraw、page rebuild、load、cache refresh 不得再次把人工修改洗回 `WIDTH + 1.5T`。
   - 只有使用者再次**明確選擇 OVERLAY**時，才可視為重新套用此預設。

### E. 與舊規則的相容邊界

- `CROSS` 的一般 `EXTRA_CUT` 預設仍是既有 `0.5T`；本輪不改全域預設。
- 既有金庫型／基準檔若保存自己的下方 `CROSS + EXTRA_CUT + BOTH + 0.5T`，載入時照原資料，不因 `OVERLAY` 文字存在就自動重設。
- `INSERT_OVERLAY` 上方第二級「嵌入留肉 0.5T」是另一個參數，與本節下方 `CROSS` 多切量無關。

### F. UI／交易一致性補充

- 自訂模式不載基準 DXF，基準檔開孔／固定孔專屬欄位不得顯示，也不得混入進階設定。
- 箱身「對稱折彎」放在 Fold/BEND 編輯區；對稱開啟時，刪除一側可刪折段必須同步刪除鏡像段，任一側受保護時整筆不動。
- 3D Fold Designer 開啟期間主 2D 必須被 modal 鎖住，避免 2D 與 3D 草稿同時寫入造成資料競爭。
- 2D 截角類型小圖的方向依 active corner target：上方／左上／右上維持垂直翻轉；下方／左下／右下恢復原始方向。小圖與大型預覽一起切換。此轉換只屬 UI，禁止改變 CornerType 或製造幾何。
- UI 顯示值若只含二進位浮點尾差（例如 `400.0000000000006`）要顯示為 `400`；近整數容差只存在 formatter，合法小數與製造幾何不得被 round。


## 2026-08-23 補充：Physical Part Presence 全鏈契約

`existing_parts` 是物理板件存在狀態的唯一集合；DXF checkbox 只是輸出選擇，禁止反向決定板件存在。

對任何非 `box_body` 板件，`present=False` 必須同時代表：

```text
3D selector/editor        不存在
Main 2D result row        隱藏、零佔位
Main 2D preview tab       hidden
FinalScene / RenderData   不建立
DXF / NC / batch export   不輸出
.p6fold round-trip        維持不存在
stashed part_profiles     可保留，但不得當存在證據
```

重新新增板件後，才恢復 UI、Scene 與輸出資格。Head/Tail 尺寸列為共用列，任一端存在就顯示，兩端皆刪除才隱藏。

Export 層必須有第二層 presence guard：即使舊 checkbox 意外保持 True，也不得輸出已刪除板件。這不是單純 UI hiding，而是製造輸出安全邊界。


## 2026-08-23 補充：CornerType 細參數鎖與已知盤型覆寫鏈

### A. UI 鎖的責任
- 截角細參數預設鎖定並隱藏，只顯示截角摘要；解鎖後才顯示 `cross_mode / direction / amount_t / secondary_*` 等適用欄位。
- 鎖定／解鎖只改 UI 的 visible/editable state，**不得修改 CornerTypeSelection**，也不得成為製造或 `.p6fold` 的 source of truth。
- 專案讀入後 UI 鎖一律回到 locked，避免一開檔就攤開全部進階參數。

### B. 自訂、已知、固定板件
- 自訂盤型：CornerType 類型依既有權限可選，細參數需先解鎖。
- 已知盤型：factory CornerType 類型固定；解鎖只允許調整**同一 CornerType 的細參數**。任何載入／切換企圖帶入不同 type_id，都必須拉回 factory type。
- 同 type 的已知盤型人工參數是有效專案資料，必須 Save/Load round-trip 並送到主 2D、3D payload 與製造 API。
- `indicator_box / indicator_door` 固定共享板件不提供解鎖。

### C. Baseline manufacturing 不得丟資料
- 已知盤型帶 corner policy 時仍以 baseline DXF 為主，不能改走 unknown/custom builder 後丟掉固定孔、MARKING 或其他 secondary entities。
- Corner policy 只覆蓋 structural outer outline / BEND / corner relief；baseline mapper 繼續提供原始 holes/features/marking。
- 因此「已知盤型解鎖細參數」必須同時通過：UI → snapshot → save/load → PartSpec/payload → baseline stretched scene/export。
