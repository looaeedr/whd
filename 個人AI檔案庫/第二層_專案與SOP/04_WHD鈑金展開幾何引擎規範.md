# 🔩 04. WHD 鈑金展開幾何引擎規範 (ae_engine)

> 套件路徑：`Z:\Ollama-整合whd\ae_engine\`（研發基準庫：`Z:\whd-corner-new-engine-implemented\`）

---

「2D 是人與程式共同使用的真實製造圖，3D 是同一份 2D 的折後視覺化」

## 💡 布林展開核心公式
$$\text{Material Polygon} = \text{Base Polygon} - \text{Relief Polygon}$$
所有零件主外框透過 Shapely `difference / union / intersection` 計算，**禁止手工推導 12/16/17 點頂點陣列**。

---

## 🏗️ `ae_engine` 模組責任架構

```
ae_engine/
├── api.py / manufacturing_api.py   # 🚪 唯一對外穩定接口 (generate_cabinet / generate_part)
├── contracts.py                    # 📜 核心資料契約 (CabinetJob, PartSpec, Feature)
├── sheetmetal_geometry.py          # 📐 純 2D 結構幾何 (Shapely boolean / topology, 禁 import ezdxf/gui)
├── sheetmetal_features.py          # ⭕ 開孔、功能切口、Factory Policy、Finished Boundary
├── sheetmetal_part_adapters.py     # 🔌 參數轉接層 (舊參數 -> StructuralGeometryResult)
├── sheetmetal_drawing.py           # 🎨 DrawingScene / SceneData / 圖元封裝
├── hole_catalog.py                 # 📚 一般開孔與管孔 CSV 解析
└── ae.py                           # 📦 Dispatcher + _save_scene_dxf DXF 序列化
```

---

## 🏷️ 加工圖層標準
1. **CUTTING**：外輪廓切割、圓孔、方孔及所有需切斷材料之輪廓。顏色：綠色 (Color = 3 (Green))，線型：實線 (Linetype = CONTINUOUS)。圓孔優先保留為 CIRCLE 實體。
2. **BEND**：折彎線。顏色：藍色 (Color = 5 (Blue))，線型：實線 (Linetype = CONTINUOUS)。
3. **MARKING**：雕刻、刻字、定位記號及輔助線。顏色：211 (Color = 211)，線型：實線 (Linetype = CONTINUOUS)。
4. **STOCK**：母材外框（展開圖最大外接矩形）。顏色：青色 (Color = 4 (Cyan))，線型：實線 (Linetype = CONTINUOUS)。
5. **DATUM**：基準線、中心線、定位線。顏色：洋紅色 (Color = 6 (Magenta))，線型：點劃線 (Linetype = CENTER)。
6. **CHECK**：檢查資訊與修復日誌層，用於承載自動修復過程中產生的尺寸標注與診斷警告。大小：30 顏色：黃色 (Color = 2 (Yellow))，線型：實線 (Linetype = CONTINUOUS)。標準輸出內容包含：
   * 展開尺寸：`W = xxx.xx mm`、`H = xxx.xx mm`。
   * 修復警告：例如 `WARNING: 2 Dangles Repaired`、`WARNING: 1 Open Loop Detected`。
   * 零件編號與版本號（由使用者或上游系統傳入時自動寫入）。
7.BLIND_HOLE：盲孔（定義為較大的微接點，區別於一般防撞微接點，供程式獨立辨識）。顏色：紅色 (Color = 1 (Red))，線型：實線 (Linetype = CONTINUOUS)。

---

## 📐 CornerType 架構（現行正式模型，2026-08-23 使用者確認補強）

### A. 核心原則：Fold Geometry 與 CornerType 必須分工
截角最終尺寸 = **折彎幾何基底（Fold Geometry）＋ CornerType 的加工殘差／留肉／多切規則**。

CornerType **不儲存實際折彎尺寸**；實際折邊長度由 Fold Profile / PartSpec 提供。CornerType 只描述角落「要怎麼避讓、留肉或多切」。因此不能看到 `amount_t=1.5` 就把它誤解成一段 1.5T 的折邊；它只是截角相對於折幾何的加工量。

### B. 現行四種正式 CornerType

#### 1. `CROSS` — 十字截角
- 用途：兩個方向的角落加工基礎型；也是目前最通用的「留肉／多切」載體。
- `CROSS` 自己還有三個 `cross_mode`：
  - `STANDARD`（標準）：不額外留肉、不額外多切；殘差 `(0, 0)`。
  - `RETAIN`（單邊留肉）：在指定方向**少切** `amount_t × T`。
  - `EXTRA_CUT`（多切）：在指定方向**多切** `amount_t × T`。
- `RETAIN / EXTRA_CUT` 的方向由 `direction` 決定：
  - `WIDTH` = 寬方向；
  - `HEIGHT` = 高方向；
  - `BOTH` = 寬＋高（`RETAIN` 不允許 BOTH，`EXTRA_CUT` 可用 BOTH）。
- `amount_t` 是「幾倍板厚 T」，不是 mm。例：`amount_t=1.5, T=2` → 多切／留肉量 = `3 mm`。
- `EXTRA_CUT` 的幾何公式本質是：
  ```text
  實際切寬 = X 向 Fold 基底 + WIDTH 多切量
  實際切高 = Y 向 Fold 基底 + HEIGHT 多切量
  ```
  若某方向 Fold 基底為 0，該方向仍可單純用 `amount_t × T` 形成避讓缺口；這是合法能力，不等於演算法錯誤。
- **機械目的與幾何手段要分開理解**：同一個 `CROSS + EXTRA_CUT` 可用來避讓「自己這片板金的折邊」、另一片板金的板厚，或另一片板金折後形成的干涉。程式幾何可以共用，機械原因不可混為一談。

#### 2. `OVERLAY` — 貼外型
- 上方 CornerType 的機械語意：封頭／封尾貼在箱身外側；每一端對整箱外高占 `1T`。
- Corner residual 的既有一級語意：高方向留肉 `amount_t × T`，預設 `amount_t=1.0`。
- **EndCap 形態已確認**：`OVERLAY` 時封頭／封尾左右 X 向 Fold/BEND 不存在；2D/3D/DXF 都不得生成虛構 X BEND，3D Fold editor 也不顯示 X 軸折彎頁。
- **下方截角預設（2026-08-23 新確認）**：當使用者在箱身選擇 `OVERLAY` 時，封頭／封尾下方預設帶入：
  ```text
  CornerType = CROSS
  cross_mode = EXTRA_CUT
  direction  = WIDTH
  amount_t   = 1.5
  ```
  這代表寬方向預設多切 `1.5T`。它只是**初始預設**，不是不可修改的硬規則；使用者之後仍可把下方改成 `HEIGHT`、`BOTH`、其他 amount 或其他既有合法 CornerType。
- 這個 `1.5T` **不需要新增 CornerType**：現有 `CROSS + EXTRA_CUT + WIDTH + amount_t` 已完整表達。

#### 3. `INSERT` — 嵌入型
- 上方 CornerType 的機械語意：封頭／封尾嵌入箱身內；該端對整箱外高占 `0T`。
- 目前固定以高方向多切 `amount_t × T` 表示嵌入避讓，預設 `amount_t=1.0`。
- 不得把 `INSERT` 的高向多切和 `CROSS/EXTRA_CUT` 的可選方向混為同一個 UI 語意；兩者資料模型不同。

#### 4. `INSERT_OVERLAY` — 嵌入貼外型
- 上方 CornerType 的機械語意：同時包含嵌入與貼外關係；只要存在貼外，該端對整箱外高占 `1T`。
- 第一級：貼外留肉，`amount_t` 預設 `1.0T`。
- 第二級：嵌入留肉／深度，現行預設：
  - `secondary_retain_t = 0.5T`
  - `secondary_depth_t = 2.0T`
- 第二級是雙段截角專屬資料，不能拿來替代 `CROSS` 的多切方向與 amount。

### C. 舊 C01~C04 只是相容代碼，不是新 GUI 的主要操作名稱
- `C01` → `CROSS + STANDARD`
- `C02` → `CROSS + RETAIN + WIDTH/HEIGHT + 1T`（方向由舊 rotation 相容轉換）
- `C03` → `CROSS + EXTRA_CUT + BOTH + 0.5T`
- `C04` → `INSERT_OVERLAY + amount_t=1T + secondary_retain_t=0.5T + secondary_depth_t=2T`

**重要**：舊代碼只是資料遷移入口。新程式、新 UI、新文件一律以 `CROSS / OVERLAY / INSERT / INSERT_OVERLAY` 與其正式參數解釋，不得再把 C01~C04 當成唯一模型。

### D. EndCap 上下角的責任分離
- 封頭／封尾**上方** `INSERT / OVERLAY / INSERT_OVERLAY` = 與箱身的組合／裝配語意，是機械真值。
- 封頭／封尾**下方**通常是板件自身加工 CornerType（例如 `CROSS / EXTRA_CUT`），不參與箱身成品高度扣量。
- `assembly_type` 若存在，只能是上方 CornerType 的 UI／相容 mirror，不能反向覆寫上方 CornerType。
- 選擇箱體組合方式可以設定「下方的初始預設」，但使用者後續手動修改下方加工參數後，普通刷新／重繪不得偷偷覆寫；只有再次明確選擇組合方式時才可視為重新套用預設。

**金庫型既有固定映射（legacy baseline）**：Door / Indicator → 舊 C02 語意；Base → 舊 C01；EndCap/Tail 下 → 舊 C03；上 → 舊 C04。此映射屬基準型號既有資料，不代表自訂模式永遠固定如此。


---

## 📦 箱體成品尺寸、FW 與組合方式（2026-08-22 更新）

### 1. `W / H / D` 的尺寸語意
- GUI 輸入的 `W / H / D` 是**完整箱體組裝完成後的包外目標尺寸**，不是箱身展開尺寸，也不是單一 core segment 長度。
- 3D 標註必須以**折彎完成後的實際外表面 envelope**為依據，並包含板厚 `T`。
- **禁止**使用以下資料直接當成 3D 成品包外：
  - 2D `material.bounds` / blank `bbox`
  - 展開總長／總高
  - `W-2T`、`D-T` 等 core 長度
  - Fold Chain 的 segment cumulative sum

### 2. 單件箱身高度與整箱包外 `H` 必須區分
完整箱體包外高度固定為使用者輸入的 `H`；但箱身單件折好後的實際高度由封頭／封尾在外部占用的板厚決定：

| 組合方式 | 單一端對整箱外高的占用 | 箱身該端扣量 |
|---|---:|---:|
| `INSERT`（嵌入） | `0T` | `0` |
| `OVERLAY`（貼外） | `1T` | `T` |
| `INSERT_OVERLAY`（嵌入貼外） | `1T` | `T` |

公式：

```text
BoxBodyFinishedHeight
= H
- HeadOutsideOccupancy
- TailOutsideOccupancy
```

例如 `H=600, T=2`：
- 嵌入 + 嵌入 → 箱身單件折後高 `600`
- 嵌入 + 貼外 → `598`
- 貼外 + 嵌入貼外 → `596`
- 嵌入貼外 + 嵌入貼外 → `596`

> **整箱組裝完成後仍必須是 `H=600`。** 例如箱身 596，加上封頭外占 2、封尾外占 2，組裝包外回到 600。

### 3. `FW` 的正式定義與控制權狀態機
- `FW` = **邊框寬度／框寬（Frame Width）**，是箱體正面門框的成品幾何基準尺寸。
- `FW` 是**尺寸參數**，不是「任意 Fold Chain 中剛好某一段的名稱」，也不得由相鄰折段重新分配或相加推導。
- 箱身 `settings.fw` 是箱身本體與門尺寸的正式 FW Source of Truth；封頭／封尾則依下列控制權狀態取得各自有效 FW。
- 封頭／封尾 FW 採四態控制權：
  - `FOLLOW_BODY`：初始狀態；箱身 FW 同時控制封頭與封尾。
  - `FOLLOW_HEAD`：使用者先改封頭 FW 時，封尾同步跟隨封頭；之後再改封頭仍繼續同步封尾。
  - `FOLLOW_TAIL`：使用者先改封尾 FW 時，封頭同步跟隨封尾；之後再改封尾仍繼續同步封頭。
  - `INDEPENDENT`：在 `FOLLOW_HEAD` 時再手動改封尾，或在 `FOLLOW_TAIL` 時再手動改封頭，封頭／封尾立即解除彼此連動，之後各自獨立。
- **使用者明確重新提交箱身 FW 時，箱身必須重新接管兩端**：不論目前是 Head/Tail 主導或獨立狀態，封頭與封尾都同步回箱身 FW 並回到 `FOLLOW_BODY`；即使此次提交數值與原值相同，也視為重新接管事件。
- 一般 redraw、refresh、切頁、載入其他 UI 狀態或非 FW 欄位更新，**不得擅自改變控制權**。
- 封頭／封尾 FW 欄位不得以「鎖死」取代控制權規則；兩端必須可直接人工輸入，由狀態機決定此次輸入是接管、跟隨或解除連動。
- 舊專案只有 per-part `follow_box` 狀態時，載入必須保持其既有效 FW，不得憑空猜測 Head/Tail 誰是主導者；下一次使用者明確操作 FW 後再進入四態規則。
- 所有 2D、3D、CornerPolicy、FinalScene、DXF export 與 `.p6fold` 都必須透過同一個「有效 FW 解析」取得數值，不得各自讀不同欄位或另算一套。
- **嚴禁**把獨立折邊與 `FW` 合併。例如 `16 + FW25 = 41` 只能代表某段展開總 span，**不得把結果重新命名或儲存為 `FW=41`**。
- 若未來需要同一板件內的左／右 FW 也能不同，必須再新增明確的 `FW_LEFT / FW_RIGHT` 契約；不得透過 Fold Chain 位置猜測。

### 4. Fold Chain 與 FW 的責任分離
- 箱身 Fold Chain 可為任意實際段數；目前實務測試上限抓 20 段，但演算法**不得寫死 3/5/9/12/20 段分支**。
- Fold Chain 描述的是**折彎拓撲、順序、長度與角度**；`FW` 描述的是**成品框寬尺寸語意**。兩者可以互相參照，但不可互相冒充。
- 箱身 Fold Chain 是箱身折法的 Source of Truth；封頭／封尾的接合折法為 derived data，需依當前箱身拓撲、組合方式與該板件解析後的有效 FW 重建，不得長期保存成互相獨立且可能漂移的三份真值。
- 3D 按「確定」後，Fold Chain 必須回寫並重新生成 2D `CUTTING / BEND` 與 DXF；3D、2D、DXF 不得各有一套折法。

### 5. 組合方式的真正 Source of Truth
目前支援的上方組合語意：

```text
INSERT          = 嵌入
OVERLAY         = 貼外
INSERT_OVERLAY  = 嵌入貼外
```

- **封頭／封尾上方 CornerType 本身就是機械組合方式的 Source of Truth。** GUI 可以在箱身頁提供一個「組合方式」選擇器方便一次設定，但它只能同步寫入真正的上方 CornerType。
- 若資料格式仍保存 `assembly_type`，該欄位只能是 UI／相容性／快照 mirror，**不得在載入時反向覆寫上方 CornerType**。兩者不一致時必須以實際上方 CornerType 為準，並將 mirror 修正或明確報出資料不一致。
- 組合方式用來決定箱身成品尺寸鏈與封頭／封尾上方接合規則；未來新增類型應透過 registry / definition 擴充，避免 GUI 與幾何散落固定分支。
- **下方 `CROSS / extra_cut` 不參與箱身成品高度扣量判定**；它是封頭／封尾板件自身的下方截角加工方式。

### 6. 封頭／封尾 CornerType 設定流程
- 上方 CornerType 是真正機械資料；箱身頁若提供統一組合選擇，只能作為一次設定 Head/Tail 上方 CornerType 的操作入口，不能成為另一套真值。
- 到封頭／封尾頁後，可設定該 CornerType 所需的加工參數。
- 上方預設 `左右相同 = ON`；需要時可取消，分別設定左／右參數。
- 下方預設：

```text
CornerType = CROSS
cross_mode = extra_cut
左右相同 = ON
```

- 下方左右也可取消連動後分別設定；下方加工 CornerType 不得回頭改寫上方組合 CornerType，也不得透過 `assembly_type` 改變箱體機械組合。
- CornerType 仍遵守既有原則：**CornerType 儲存固定加工規則，不儲存 Fold Geometry 的實際折彎尺寸**。

### 7. 3D 尺寸標註規則
- **箱身單件 3D**：標註箱身這片板折好後本身的真實包外，因此高度可能是 `H`、`H-T` 或 `H-2T`。
- **整箱組裝 3D**：標註完整箱體成品包外，應回到使用者設定的 `W / H / D`。
- 尺寸應從折後 mesh / surface 的外包絡計算，而不是從 2D 展開外框搬數字。

### 8. 板件存在狀態與編輯器操作
- `box_body` 為組合方式與 Fold Chain 的主體，預設不可刪除。
- 板件按鈕採**單擊一次直接進入**：禁止要求雙擊兩次，也不另設「編輯」按鈕。
- 「刪除板件」固定放在**板件按鈕區正下方**；`box_body` 時 disabled，其餘存在板件可直接刪除，可另外支援 Delete 鍵。
- `existing_parts` 是板件是否存在的正式狀態：刪除後 2D tab、3D workspace、DXF export、`.p6fold` 專案狀態必須同步；加回時再恢復。
- 封頭／封尾加回時，其接合折法應依當下箱身 Fold Chain + **實際上方 CornerType** 重新推導；若存在 `assembly_type` mirror，不得用它覆蓋 CornerType。門、底板等獨立板件可保留自己的 stash profile。
- 「取消」只捨棄本次 Phase6 暫存；「確定」才 commit 回主 GUI / 2D / 專案狀態。
- `.p6fold` 必須保存封頭／封尾 FW 的控制權狀態（`FOLLOW_BODY / FOLLOW_HEAD / FOLLOW_TAIL / INDEPENDENT`）與兩端有效值；重載後需還原相同控制權與有效 FW。舊專案僅有 per-part `follow_box` 時按第 3 節相容遷移，不得猜測 Head/Tail 主導者。

### 9. 箱身 → 封頭／封尾 Fold Chain 拓撲連動（2026-08-23 更新）
- **箱身 Fold Chain 是唯一折法 Source of Truth**。封頭／封尾接合側的 segment、BEND 數量、折彎角度與接合方向必須由當下箱身拓撲推導，不得保存一份會與箱身漂移的固定拓撲。
- 箱身在接合側**刪除一個外側折段**時，封頭與封尾對應折段必須自動刪除；箱身新增或改變該折段 angle 時，封頭／封尾也必須同步新增或更新對應折彎。使用者不應再手動到封頭／封尾補刪折。
- 拓撲連動只控制「折法／接合幾何」；`FW` 仍遵守第 3 節的四態控制權契約。封頭／封尾可有不同有效 FW，但**不能阻止 topology 隨箱身同步**。
- 封頭與封尾可以有不同 native order / local orientation；實作時應先由箱身建立共同的 canonical mating chain，再轉成各板件 native order，且必須保留每一道**折線 boundary 的 angle 所有權**，不得因反轉順序把 angle 移到錯的 segment 或消失。
- **可選折段不存在就是不存在**：例如箱身已刪掉某個外側折，對應 end-cap profile 中該 segment 可以完全缺席；reader/adapter 不得把缺少 `ytop1` 類欄位判成資料損壞，也不得 fallback 到舊固定折法。
- 2D 結構尺寸必須跟 topology 一起重建。刪除對應折段時，不只 BEND 消失，`Base Polygon / material bounds / blank size` 也必須由新的完整 profile 重算；禁止「BEND 少一條但外框仍維持舊尺寸」。
- **BEND 生成條件**：只有 source segment 明確具有 `angle` 時，該 segment 後方 boundary 才能生成 BEND。沒有 angle 的 terminal/co-linear segment 不得因為存在 cumulative boundary 就產生假 BEND。
- **2D / 3D 1:1**：Final 2D 的每一條 BEND 必須在 3D 有且只有一個對應 fold；3D 不得自行補折、刪折或使用 legacy profile。
- **角度驗證獨立於尺寸驗證**：90° 折彎必須直接驗證折後相鄰面的夾角為 90°；包外尺寸正確不能證明 bend angle 正確。

以目前 5 段箱身案例：

```text
箱身：FW → D → W → D → FW

封頭 Y：FW → D-core → 後側折邊
封尾 Y：後側折邊 → D-core → FW   # native order
```

若原本 9 段箱身的 FW 外側折已被刪除，封頭／封尾不得再自行補回該外側折；其 2D blank 高度也必須隨之縮短。


### 10. Fold angle 單一輸入契約（2026-08-23 更新）
- Fold Chain 編輯器的**操作員輸入 angle 是唯一角度來源**。輸入 90 就折 90；輸入 45、60、-60 等就依該輸入執行，不得在 EndCap derivation 中固定寫成 `-90`。
- UI/engine 若為既有座標慣例需要表示層正負號轉換，只允許在 `engine_angle_to_ui / ui_angle_to_engine` 這類單一邊界完成；必須保證 round-trip 回到相同操作員輸入值。Manufacturing/derived/3D 不得再做第二次翻號。
- 箱身 → 封頭／封尾 derivation 必須傳遞**對應 bend boundary 的實際 angle 值**。以 5 段 `FW → D → W → D → FW` 為例，EndCap 的 `FW→D-core` 與 `D-core→後側折邊` 各自取對應來源 angle；Tail native order 只反轉 bend ownership 順序，不改造輸入角度。
- 3D renderer 直接消費上述 derived profile angle；相機投影設定不得修改、替代或修補幾何角度。
- Phase6 commit 後，主 GUI 2D、3D、DXF export 必須全部重新指向同一 committed `PartSpec / FinalScene`。主 2D 尺寸不得再走舊 `ytop1 + FW + D` 公式。


### 11. 箱身 ↔ 封頭／封尾「使用者已確認」機械組合基準（2026-08-23 固化）

> 本節是經使用者明確確認的機械關係，後續 AI 與程式檢查皆視為**已知真值**，不是待猜測假設。檢查方向應是「程式有沒有符合這些關係」，而不是「拿目前程式反推這些關係是否成立」。

#### 11.1 箱身刪除接合鏈外側折，封頭／封尾對應折必須同步刪除
- 當箱身 Fold Chain 在與封頭／封尾的**組合接合鏈**上刪除外側可選折段時，封頭與封尾對應的 mating fold 也必須消失。
- **不得因 legacy profile、固定欄位或 fallback 再補回已不存在的折。**
- 此規則不是「箱身任何一折都能任意刪除」：`D-W-D` 為箱身核心結構，不能把這句擴張成可破壞核心拓撲。

#### 11.2 封頭／封尾上方截角就是組合方式的機械語意
- 封頭與封尾**上方 CornerType**直接表達它們和箱身的組裝／接合方式。
- `INSERT / OVERLAY / INSERT_OVERLAY` 的真正機械意義落在上方截角／接合關係；若程式另外存在 `assembly_type` 欄位，只能作為 UI／保存／統一選擇的表示層，**不得形成與上方 CornerType 脫鉤的第二套機械真值**。
- 封頭／封尾**下方截角**屬於板件自身加工（例如 `CROSS / extra_cut`），不參與箱身成品高度的上下端板厚扣量。

#### 11.3 貼外關係每端占用 1T
```text
INSERT          = 0T
OVERLAY         = 1T
INSERT_OVERLAY  = 1T
```
- `INSERT_OVERLAY` 雖包含嵌入語意，但只要存在貼外關係，該端對完整箱體外高即占 `1T`。
- 因此箱身單件折後高度必須依上下端實際組合方式回算：
```text
BoxBodyFinishedHeight
= H
- HeadOutsideOccupancy
- TailOutsideOccupancy
```
- 完整箱體組裝後的包外高度仍必須回到使用者輸入的 `H`。

#### 11.4 五段箱身的封頭／封尾對應關係
當箱身為：
```text
FW → D → W → D → FW
```
則接合 profile 必須為：
```text
封頭：FW → D-core → 後折
封尾：後折 → D-core → FW    # native orientation
```
- 原本較多段箱身才有的外側 `ytop1` 類折段，在 5 段拓撲中既然已不存在，封頭／封尾**不得自行補回**。
- 封尾允許 native order 與封頭相反，但 angle ownership 必須依 bend boundary 正確搬移，不能因反轉 list 而遺失或錯置角度。

#### 11.5 AI 判讀界線
- 以上四條均為已確認機械基準。
- 若目前程式、測試或舊文件與本節矛盾，先標記為**實作不一致**並追根因。
- 「本次 ZIP 沒附真 DXF／實體照片」只能表示無法新增新的機械推論，**不能用來撤回使用者已確認並固化的既有規則**。
- AI 不得把「沒有重新證明」說成「這條可能是瞎掰的」；除非出現新的直接反證，否則既有確認規則保持有效。


#### 11.6 箱身折起來後的實體：三個成形面、三個開口（2026-08-23 使用者確認）
- 以核心箱身 `FW → D → W → D → FW` 為例，折起來後真正形成的箱身主體是：
  - `W`：背面；
  - 左、右兩個 `D`：左右側面；
  - 兩側 `FW`：正面開口兩側的框邊／回折邊，**不是第四個封閉箱面**。
- 因此箱身折起後有三個尚未封閉的實體開口：
  1. **正面開口**：由門補上；
  2. **上端開口**：由封頭補上；
  3. **下端開口**：由封尾補上。
- 所以封頭、封尾是**上下端板**，不是「箱身前折／後折」的延伸，也不是「封頭跟箱身左側、封尾跟箱身右側」這種一對一關係。
- 任何 end-cap derivation 都必須先從「箱身折起後的上／下端開口實際邊界」理解接合，再映射回 2D Fold Chain；**不得只因一維 Fold Chain 的陣列順序，就把封頭／封尾當成前後折或任選其中一側 chain 來生成整片端板。**
- **尚未確認、禁止先猜的部分**：當箱身兩側外加折數不同（例如一側 FW 外多 2 折、另一側多 1 折）時，這些額外折在封頭／封尾各實體邊上到底如何對應，留待下一步依實際端口幾何討論確認。在使用者確認前，AI 不得自行宣稱「跟左邊」「跟右邊」「封頭跟某側、封尾跟另一側」或把兩側壓成單一 canonical chain。
- **2026-08-23 進一步確認判斷依據**：未來要判斷額外 Fold 到底是否需要由封頭／封尾跟隨，依據不是展開圖的左右位置、折數多寡或 segment index，而是該 Fold **實際折起後形成的形態與接觸角色**。必須先知道它折後落在哪一面、朝內／朝外、是否形成端口邊界、搭接邊、包覆邊或完全不接觸端板，再決定封頭／封尾是否以及如何對應。
- **目前刻意延後**：這種依折後形態分類會新增多個接合型態；使用者目前不希望處理這一層。因此現階段不得為了完成程式而自行新增型態、用「左跟左／右跟右」、或以「多 2 折／多 1 折」直接建立配對規則。先維持既有已確認型態，待使用者之後明確定義再擴充。


### 12. Phase6 UI／交易／貼外型已確認規則（2026-08-23）

#### 12.1 自訂模式不得顯示基準檔專屬資料
- `自訂` 模式本身不載入任何型號基準 DXF，因此所有**只有基準檔存在才有意義**的控制與數值必須整組隱藏。
- `固定孔`、`封尾固定孔` 等基準檔孔資料只能出現在「基準檔開孔資料」區，**不得又從「進階設定」重複露出**。
- 使用者自行新增的孔、Fold、CornerType 與真正自訂加工參數不屬於基準檔資料，不能因隱藏基準檔區而一起消失。

#### 12.2 箱身「組合方式」切換不得摧毀目前操作頁
- 箱身的組合方式 Combobox 是操作入口；選擇後可以同步更新 Head/Tail 上方 CornerType 與 derived profile，但**不得在 `<<ComboboxSelected>>` 事件執行途中 destroy/rebuild 觸發事件的 box_body 頁面**。
- 需要更新的 Head/Tail 頁面可 invalidate，等切入時再 lazy rebuild；目前 box_body 頁必須保持可見、可繼續操作。

#### 12.3 對稱折彎屬於 Fold/BEND 編輯區，且刪除也必須對稱
- 「對稱折彎」操作入口放在箱身 Fold/BEND 編輯區，沿用既有 `state.symmetric` / mirror 邏輯，不放到全域設定。
- 開啟對稱時，不只數值修改要鏡像；**刪除一側可刪折段時，鏡像對應段也必須同一交易一起刪除**。
- 若任一側對應到不可刪的核心／受保護 segment，整筆刪除取消，禁止只刪單側留下不對稱半狀態。
- `D-W-D` 核心與既有受保護 Fold 規則不因對稱模式而放寬。

#### 12.4 3D 編輯器是 modal transaction，開啟期間主 2D 不可同時編輯
- 3D Fold Designer 開啟時，主 GUI 2D committed state 必須鎖定，避免使用者同時修改兩份狀態。
- 3D 以 snapshot/draft 操作：`確定` 才一次提交；`取消 / X` 丟棄 draft。主 2D 在 draft 存活期間不得接受會改 committed state 的操作。
- 實作可用 Toplevel `transient + grab_set` 等方式建立真正 modal transaction；關閉後必須正確釋放 grab。

#### 12.5 封頭／封尾共同參數採單一真值，只有真的不同才分開
- 封頭與封尾若機械角色相同的參數，應共用同一 authoritative setting key；任一端修改後另一端讀到同一值。
- 只有明確屬於單一板件的參數（例如 tail-only 底孔）或日後使用者確認「兩端形態本來不同」的參數，才拆成兩份。
- 不得因 UI 分成 Head/Tail 兩頁，就無意間保存兩份可能漂移的同義參數。

#### 12.6 `OVERLAY`（貼外型）封頭／封尾沒有左右 X 向折彎
- 這是已確認的機械型態，不是顯示偏好：`OVERLAY` 時封頭／封尾**左右 X 向 Fold/BEND 不存在**。
- 因此同一份 authoritative profile 必須導致：
  - 主 2D FinalScene 不生成左右 X BEND；
  - 3D 幾何不生成左右 X BEND；
  - 3D Fold/BEND 編輯器不顯示虛構的 X 軸折彎頁，只保留實際存在的 Y 向 Fold。
- 不得只在 renderer 隱藏線；X Fold topology 必須從 profile/PartSpec 源頭表達為「無折彎」。
- 從 `OVERLAY` 切回 `INSERT / INSERT_OVERLAY` 時，正常 X Fold topology 必須由 authoritative 尺寸／Fold 規則恢復，不能被前一次貼外 flat profile 永久污染。
- **材料外框也必須跟著 topology 改變**：`OVERLAY` 沒有左右 X 折彎時，封頭／封尾 X 向展開材料總寬就是成品 `W`。不得先用 INSERT 型公式 `W-4T+|yl1|+|yr1|` 算出舊材料寬，再把三段折彎 profile 合併成一段假 flat span。
- 因此 `W=400, T=2, yl1=yr1=15` 的貼外封頭／封尾，X flat span 必須是 `400`，不是 `422`。`yl1/yr1` 在貼外 X topology 中不再是實際折邊；下方 `CROSS + EXTRA_CUT + WIDTH + 1.5T` 只改角落 CUTTING，不得增加整張材料寬度。

#### 12.7 `OVERLAY` 下方預設直接使用既有 `CROSS + EXTRA_CUT`，不新增 CornerType
- 前一版文件把 1.5T 誤寫成「要新增 CornerType」；這是 AI 對既有截角模型理解不足，現已撤回。
- 現行 `CROSS + EXTRA_CUT` 本來就支援 `WIDTH / HEIGHT / BOTH` 與任意正 `amount_t`，因此 `WIDTH + 1.5T` 已可直接表示貼外型需要的寬向避讓。
- 使用者已確認：**明確選擇 `OVERLAY` 時**，Head/Tail 下方初始預設為 `CROSS + EXTRA_CUT + WIDTH + 1.5T`。
- 這是「組合方式切換時帶入的初始預設」，不是把 `CROSS` 全域預設從 0.5T 改成 1.5T；其他型態／其他既有資料仍保留自己的設定。
- 使用者之後若把下方改成 `HEIGHT`、`BOTH` 或其他 amount，普通 refresh / render / load 不得再次偷偷洗回 1.5T；只有再次明確選擇組合方式，才可視為重新套用該組合型態預設。
- `CROSS + EXTRA_CUT` 是幾何手段；其機械目的可能是避自己折邊、另一板金板厚或另一板金折後干涉，不能只因「自己沒有 X 折邊」就判定多切不合法。

#### 12.8 截角類型縮圖方向是 UI 表示，不得反向改幾何
- 2D 區 CornerType 小圖依目前編輯位置顯示：**上方截角維持垂直翻轉；下方截角恢復原始方向，不做垂直翻轉**。
- 左上／右上視同上方；左下／右下視同下方。四種 CornerType 小圖與下方的大預覽必須一起跟隨目前 target 的方向，不得只改其中一張。
- 此方向轉換只作用於 preview canvas 座標；不得改 CornerType、FinalScene、CUTTING/BEND、3D 或 DXF 幾何。

#### 12.9 UI 數值不得暴露二進位浮點殘差
- `400.0000000000006` 這類值屬浮點運算殘差，不代表新的機械尺寸；使用者可見文字應顯示為 `400`。
- 顯示層可用極小容差判定「接近整數」後格式化；例如容差 `1e-9`。合法小數如 `400.25` 必須保留。
- 此規則只處理 UI 文字，不得藉由 round/截斷去改製造幾何、DXF 或 project state 的實際數值。

---

## 🧪 TDD 與更新規範
- 更新 AE 時，直接覆蓋 `ae_engine/` 目錄，透過 pytest 回歸驗證，不再進行繁瑣人工合併。
- 凡本輪新增/修改上述幾何、資料契約、2D/3D/DXF 行為或修復可重現 Bug，**同一輪直接更新本規範與 `06_踩坑記錄與防錯經驗庫.md`**；文件同步是完成條件，不等待使用者再次要求。
- regression 必須優先使用實際 `.p6fold` / 真 DXF 重現，再補合成單元測試；測試不得只驗 helper 而忽略 FinalScene / GUI / export 的實際資料鏈。

#### 12.10 板件存在狀態是全鏈單一真值（2026-08-23 使用者確認）
- `existing_parts` / physical presence 表達「這片板件實際存在不存在」；DXF checkbox 只表達「存在的板件這次要不要輸出」。兩者禁止混為一談。
- 刪除板件後，必須沿同一 presence source 同步處理整條鏈：
  1. 3D/Fold Designer 板件按鈕與可編輯頁消失；
  2. 主 GUI 左側 2D 展開尺寸列整排隱藏，**不留空白佔位**；
  3. 主 GUI 右側 2D preview tab 隱藏，不再繪製該板；
  4. 對應 FinalScene / RenderData 不再因殘留 `part_profiles` stash 被建立；
  5. DXF/NC/批次輸出不得輸出不存在板件，即使舊 checkbox 狀態意外仍為 True；
  6. `.p6fold` 保存／重載維持相同 `existing_parts`，不得被 stale feature、profile 或輸出選項復活；
  7. 重新「新增板件」後才恢復上述 UI、Scene 與輸出資格。
- 刪除可以只改 presence、保留 `part_profiles` 作為「重新新增時恢復使用者折法」的 stash；**stash 不是存在證據**，任何計算／Scene／輸出都必須先檢查 presence。
- Head/Tail 共用一組「封頭/尾展開尺寸」顯示，因此只要 Head 或 Tail 任一存在就保留；兩者都不存在才整組隱藏。
- 箱身 `box_body` 是 Fold Chain owner，固定存在且不可刪除。
- 修 Bug 不得只處理使用者眼前指出的一個 UI 症狀；必須主動由 Source of Truth 追到 2D/3D、保存/重載、製造輸出與 regression，避免要求使用者逐項補充相依問題。


### 14. CornerType 參數鎖與全域專案檔操作（2026-08-23 使用者確認）

#### 14.1 截角細參數預設鎖住並真正隱藏
- 一般操作只需看目前 CornerType／摘要；`cross_mode / direction / amount_t / secondary_retain_t / secondary_depth_t` 等細節預設收起。
- UI 必須有**明確可見文字**的 `🔒 參數鎖定 / 🔓 參數解鎖` 控制，不能只存在內部 boolean 或依賴一個可能看不清的圖示。
- 鎖定時細部輸入列以及 `左右相同` 這類進階編輯控制必須 `pack_forget/grid_remove`，真正不佔版面；CornerType 類型/目前摘要可保留供辨識。
- 使用者真的需要特殊加工時才解鎖展開。重新鎖上只收 UI，**不得把人工值重設成預設**。
- lock/unlock 是純 UI 狀態，不是幾何／製造資料，也不應寫成 `.p6fold` 的機械真值；讀檔後回到 locked。
- 驗收不能只 assert `_unlocked=False` 或按鈕物件存在，必須驗 `winfo_manager()`／實際 layout：鎖鈕可見、細節容器零佔位、解鎖後才重新出現。

#### 14.2 已知盤型也可解鎖細參數，但 CornerType 類型固定
- 已知型號的 factory CornerType 仍是不可改的類型真值；使用者解鎖後只能修改該類型內的細參數。
- 同 type 的人工細參數必須完整保存／讀回，且主 2D、3D、DXF manufacturing 都使用它。
- 不同 type_id 的舊檔／異常資料載入已知型號時，type 必須回到 factory type；不能因「可解鎖細參數」而讓已知型號變成可任意換類型。
- 指示燈盒／指示燈小門為固定共享板件，維持真正唯讀，不提供解鎖。

#### 14.3 已知盤型參數覆寫仍要保留 baseline DXF
- 已知盤型的 corner policy 覆寫只改 structural CUTTING/BEND/corner relief；不得為了套參數改走自訂 builder。
- 基準 DXF 的固定孔、MARKING、其他 secondary features 必須繼續由 baseline mapper 保留。
- 必須以完整鏈驗證：UI → project state → `.p6fold` → load → PartSpec/3D payload → baseline scene/export。

#### 14.4 `.p6fold` 開啟／儲存是全域功能
- 主視窗左上角提供：`開啟專案 / 儲存專案 / 另存新檔`。
- 3D Fold Designer 是 modal；主視窗被鎖住期間使用者仍必須能操作全域專案功能，因此 **3D 視窗左上角也提供同一組全域 `開啟專案 / 儲存專案 / 另存新檔`**。
- 3D Footer 仍只保留目前板件 transaction 的 `確定 / 取消 / 還原初始值`；全專案按鈕不能塞回 Footer 或混成板件操作。
- `儲存專案` 有目前路徑就覆存；沒有路徑才轉「另存新檔」。3D 另存後需同步目前 project path，後續主視窗/3D `儲存專案` 共用同一路徑。
- 全域 GUI 開啟、3D 全域開啟、Windows `.p6fold` 雙擊／argv 必須共用 authoritative project format / loader，不得各做一套資料還原規則。

### 15. Box Body / EndCap Assembly Collision Relief（2026-08-27 固化）

本節固化新的 assembly relief 架構方向：**先形成名義板件與折後實體，再由實際干涉反推 2D CUTTING**。不得再先用截角公式猜測每個角該切多少。

#### 15.1 正確資料流
```text
W / H / D / T
Fold Profile
板件角色 / ownership
        ↓
名義板件幾何
        ↓
形成折後實體 / resolved material
        ↓
SELF / Assembly 干涉檢查
        ↓
Collision Region
        ↓
ownership 判定誰保留、誰切除
        ↓
3D / 2.5D → 2D 反投影
        ↓
Relief Candidate
        ↓
真正 2D CUTTING
        ↓
重建 RenderData / FinalScene
        ↓
再次干涉驗證
```

第一版實作範圍為 **Box Body ↔ EndCap / Tail**：

```text
Box Body = RETAIN
EndCap / Tail = CUT
```

#### 15.2 API 與所有權邊界
- Assembly collision solver 屬於 `ae_engine` / manufacturing boundary，不屬於 GUI、renderer 或 DXF writer。
- Renderer 只消費已完成的 `PartRenderData(scene, material, fold_guides)`；不得呼叫 collision solver，也不得重新解析 CornerType 或 CUTTING material。
- `EndCapPartSpec` 透過 opt-in request 啟用 assembly relief；未啟用時既有 render data 行為保持不變。
- Solver 目前可使用 Shapely 2.5D footprint 作為第一版驗證，不宣稱已完成完整 CAD kernel 3D solid solver。

#### 15.3 Relief Candidate 規則
- `Collision Region` 必須來自已解析材料的真實重疊區，不得由固定 `0.5T / 1T / 2T` 公式預先假設。
- `ownership` 決定哪片板保留、哪片板切除；第一版固定箱身保留、封頭／封尾切除。
- `clearance` 可在 projection 階段加到 cut polygon，但必須以實際 collision 為基底。
- 切除後必須重建 `CUTTING` 與 `material`，並再次檢查 Box Body 與 EndCap 是否仍有干涉。

#### 15.4 後續擴充邊界
- 其他箱型、其他組合方式與非對稱 fold 端口不得自動套用本第一版規則；必須先確認折後實體接觸角色。
- 若未來新增真正 3D solid kernel，仍維持同一資料流與 ownership contract，只替換 collision / projection 的內部實作。


#### 15.5 Shared Assembly World Geometry（2026-08-27）
- `ae_engine/assembly_geometry.py` 是折後 mesh 與 assembly placement 的共同 Source of Truth。
- `PartRenderData + Fold Profile + final BEND guides` 必須先由共享 `folded_mesh_from_polygon()` 形成 local folded mesh，再由共享 placement 轉到 cabinet world coordinates。
- `phase6_final_scene_view.py` 只能委派共享 folding / placement；不得保留第二套實質演算法。
- `ae_engine/assembly_collision.py` 透過同一 shared geometry 將 Box Body 與 EndCap/Tail 放入同一世界座標；真正 3D collision 後續必須直接建立在這套 world mesh 上。
- 第一階段 assembly scene 只包含 `box_body + head + tail`。Door/Base Plate 屬其他組裝層，不得混入目前 BoxBody/EndCap 接合碰撞畫面。

#### 15.6 組合體是板件選擇第一項，不再是獨立 3D 模式按鈕（2026-08-27 最新）
- 左側 `板件選擇` 的第一項固定為 `組合體`，其後才是 `箱身 / 封頭 / 封尾 / ...` 等實際板件。
- 第一次進入 3D Designer 時直接進 `組合體`；底層可保留 `box_body` 作為 assembly 幾何 backing active part，但 UI 選擇必須顯示 `組合體`，3D request 必須走 assembly scene。
- 選擇任何實際板件時，自動切回 single-part 編輯模式；不再保留右側或頂部的 `單件 / 組合體` 兩顆模式按鈕，避免兩套導航互相打架。
- `組合體` 目前只組 `box_body + head + tail`，不混入 door / base plate；此範圍與目前 BoxBody/EndCap collision workflow 一致。
- 組合體不是實際板件，因此選中組合體時左側 Fold Editor 與一般板件設定都隱藏；`參數鎖定` 解鎖時不得誤顯示箱身設定，而是顯示「組合體診斷」。切回實際板件且參數為解鎖時，才顯示該板件設定。
- 驗收必須跑真 Tk：`part_choice_menu` 第 0 項為 `組合體`、初始 `part_var == "組合體"`、`_phase6_3d_display_mode == "assembly"`、Fold Editor/板件設定隱藏；切到箱身後 mode 變 `single` 且 Fold Editor 顯示。
- **組合體 Head/Tail 空間方向與貼合基準（2026-08-28 最新確認）**：組合體定位不得只靠旋轉名稱猜測，必須服從既有 `組合方式 -> CornerType -> Fold Profile topology` 語意。EndCap resolved Fold Profile 的 local `z=0` 是**板厚中心面**，不是實體接觸面；local `+z` 是實際折邊伸出／箱內方向。3D 組合體必須使用真實板厚 `T` 由中心面建立內外兩個 skin 與外周／折線側面。封頭將 local `+z` 映射為 world-Y 向下，中心面先向箱外偏移 `T/2`，使**內側 skin**精確貼箱身 world 上緣，外側成型面位於箱身外側；左右折邊與 `ybottom1` 往箱身內插。封尾維持 EndCap authoritative native orientation（local X、local Y 都不得在 assembly 再鏡射），local `+z` 映射為 world-Y 向上，中心面向箱外偏移 `T/2`，使內側 skin 貼箱身 world 下緣、外側成型面位於下方箱外。禁止再把零厚度 `z=0` 中心皮直接當作 mating face。
- `INSERT / INSERT_OVERLAY` 的 X topology 必須保留 `yl1 / endcap_w_core / yr1` 真實左右折邊；`OVERLAY` 的 X topology 必須是 `endcap_w_flat`，不得為了組合顯示虛構左右折邊。Assembly transform 消費已解析 Fold Profile，不建立第二份組合類型狀態或硬寫折邊長度。
- 封頭／封尾組合定位必須消費與 3D collision 相同的共享 assembly transform；不得只旋轉 viewer 外觀而讓 collision 仍使用舊方向。
- 從 `組合體` 切到實際板件時，即使 assembly 底層 backing `active_part` 本來就是該板件，也必須完成 mode transition 並重新顯示 Fold Editor；Tk Menu radiobutton 會先改 `part_var` 再呼叫 callback，禁止用 `active_part == key` 或目前選單文字直接 early-return。

#### 15.7 3D Designer 固定版面（2026-08-27 最新）
- 最上列固定順序：`[檔案 ▼] [3D 顯示：文字大小｜折彎透視｜面板透視] [全螢幕] ... [還原初始值]`。`取消 / 確定` 已移除；3D production edit 即時同步 canonical state。
- `全螢幕` 只控制 3D Designer 視窗最大化／還原，不得改幾何、設定或 project state。
- 全域設定固定兩行且永不消失：
  - 第 1 行：`[基準型號 ▼] [參數鎖定] [儲存預設值]`
  - 第 2 行：`[W] [H] [D] [T] [結構 ▼] [組合方式 ▼]`
- `文字大小` 從全域設定移到最上列 `3D 顯示` 區；全域設定不得再多出第三行。
- `結構`、`組合方式` 與 `參數鎖定` 不屬右側畫布控制列；它們固定在全域設定區。右側只允許：解鎖後才顯示的目前板件設定 → 3D 畫布。

- 右側「組合體診斷／板件設定」與 Matplotlib 3D canvas 共用 `pack` 時，設定面板必須排在 canvas **前面**；統一經 `_phase6_pack_right_panel_above_canvas()`，不得在 `fill=BOTH, expand=True` canvas 之後普通 `pack()`。驗收必須檢查 `winfo_viewable()==1` 與實際高度 > 1，不能只看 `winfo_manager()`。
- 左側固定：`板件選擇 / 新增 / 刪除` → 箱身才有 `對稱折彎` → `X 軸折彎 / Y 軸折彎` → 折彎列與新增前/後折。
- 驗收不能只掃 source string；必須用真 Tk 檢查 widget 的 master/grid/pack：top command row、global row 0/1、組合體初始導航，以及右側不得存在 duplicate `right_control_bar`。


#### 15.8 Physical EndCap 組合體的孔輪廓與真實折彎稜線顯示（2026-08-28）
- `PartRenderData.material` 仍是 CUTTING/孔的 Source of Truth；`Fold Profile + final BEND guides` 仍是折後 mid-surface 的 Source of Truth。Renderer 不得為了顯示重新建立孔或 BEND。
- Head/Tail physical sheet 由 folded mid-surface 加厚為 closed solid 後，**不得只靠 closed-solid open boundary 畫線**；closed solid 會把 through-hole 邊界與 formed crease 都封成共享 edge，造成畫面誤判為「孔消失／折彎沒做」。
- 組合體 EndCap 必須額外從加厚前的 authoritative folded mid-surface 抽可視線：單鄰接 edge = 材料外輪廓或 through-hole 輪廓；多鄰接 edge 若面法向非共面 = 真實 formed crease；共面三角化對角線不得顯示。
- 標準未修改金庫型仍固定保留完整 EndCap 5 道 BEND（X 2 + Y 3）。若畫面缺 `ytop1` 第一折、留肉附近折線或孔，先查 render edge extraction，不得先改 Fold Profile。

#### 15.9 Physical EndCap 孔口必須畫在實體外皮，3D BEND 固定實線（2026-08-28 06:49）
- `PartRenderData.material` 的 hole interiors 仍是孔洞 Source of Truth；Head/Tail 加厚後實體本身必須保持真正貫穿孔。
- **禁止只把孔輪廓畫在 folded mid-surface**。mid-surface 位於 ±T/2 兩個 skin 中間，組合後會被實體外皮遮住；若孔後面又緊貼 BoxBody，視覺上會像孔被填滿。
- 組合體 EndCap 的可視孔口必須由 **thickened physical solid 的非共面 feature edges** 取得，讓孔 rim 真正落在 ±T/2 外／內 skin 上；共面三角化對角線必須排除。
- 實體 feature edge 可包含：外周 rim、through-hole rim、板厚角、折彎／miter edge。這些線都必須是 solid line。
- `BEND` guide 在 3D 顯示一律使用**實線**，不得再使用 `--` 虛線。單件與組合體都遵守同一視覺規則。
- folded mid-surface 的 crease overlay 可保留作長折線 fallback，但不得成為孔口唯一顯示來源。
- 驗收至少包含：有孔平板加厚 T=2 後，孔 rim edge 必須出現在 `z=+1` 與 `z=-1` 兩個 physical skins；3D BEND line 的 matplotlib linestyle 必須是 `-`。


#### 15.10 組合體未退讓／干涉碰撞診斷（2026-08-28 08:00 修正版）
- 目標是先看見「固定截角尚未作用前」真正**由固定截角所消除的碰撞**，再決定如何反投影成 2D relief；此階段是診斷，不得直接改生產 CUTTING。
- `診斷時忽略固定截角` 的顯示材料仍可把 Head/Tail 外部固定 relief 補回，並保留所有 `Polygon.interiors` 貫穿孔；但**碰撞 probe 絕對不得使用整片補回後 EndCap**。
- 唯一合法的固定截角診斷 probe 是 `restored_endcap_relief_delta = restored_material - production_material`，亦即只取「原本固定截角切掉、現在診斷補回來」的那一小塊材料。整片 EndCap 做 surface crossing 會把正常插入／貼合接縫一起算成交線，產生整圈假紅區。
- BoxBody 與 relief-delta probe 都以真實 `T` 形成 physical solid 後再進 shared world space。干涉判定使用三角面 AABB broad-phase + 非共面 segment/triangle crossing；共面 mating contact 與單點 touch 不得標成 collision。
- 3D 診斷可用**半透明紅面**標示「delta probe 中確實命中的 target triangles」，並疊加 world-space `intersection_segments` 紅色粗實線。因 target 已被限制為 relief delta，此紅面只代表局部固定截角候選區，禁止再把整片 EndCap target triangle 染紅。
- 關閉 `診斷時忽略固定截角` 時，本固定截角診斷不得退回整片 production EndCap 做碰撞；應停止此 probe 並提示先啟用固定截角診斷。
- 純幾何診斷 owner 是 `ae_engine/assembly_geometry.py`；`phase6_final_scene_view.py` 只能呼叫 geometry helper。`ae_engine/assembly_collision.py` 可相容性 re-export，但 renderer 不得直接依賴 solver module。
- 下一階段若要自動截角，必須從這些 verified relief-delta world-space interference segments/regions 反投影到 EndCap 2D material，再套 ownership（BoxBody RETAIN / EndCap CUT）與 clearance，最後重折回 3D 驗證。


#### 15.11 3D 干涉反投影正式截角 Source of Truth（2026-08-28 13:04）
- 固定截角不再是最終尺寸答案。正式流程為：`補回固定截角但保留孔 → authoritative Fold Profile + final BEND 折成含 UV 的實體板 → shared assembly world transform → BoxBody physical solid 干涉 → barycentric 3D→2D 反投影 → corner cut polygon → 淨空 A → 新 CUTTING → 再折回 3D 驗證`。
- BoxBody = RETAIN；Head/Tail = CUT。3D Viewer 不擁有截角公式，solver owner 為 `ae_engine/assembly_collision.py`；world folding/placement owner 為 `ae_engine/assembly_geometry.py`。
- 每個 folded target triangle 必須保留原 2D flat UV；world intersection point 以 barycentric coordinate 精確回到 EndCap/Tail 展開座標，禁止用 world bbox 或螢幕投影猜尺寸。
- 舊固定截角只可作為「角落拓撲搜尋域」與第一級/第二級 band 的機械 topology，不得把舊 C03/C04 寬高當求解答案。每級實際寬/深由 3D 反投影交線決定。
- solver 必須迭代：每輪 `新 cut → rebuild material → refold → 再求 corner interference`，直到剩餘材料沒有實體穿透；A=0 可允許 CUTTING 邊界線接觸，但交線中點若仍落在剩餘 material interior 內即不得 verified。
- 淨空 A 只在 collision envelope 收斂後套用。對目前正交兩級截角，primary U/V 各 +A、secondary U +A、secondary depth 不變；禁止用通用 polygon buffer 產生 18.997 這類斜接數值噪音。
- 鏡像左右角若 canonical cut shape 在嚴格數值容差內已互為同形，允許取 canonical union 消除 triangle tessellation 微小誤差；真非對稱件不得強制對稱。
- verified cut 寫入 `EndCapPartSpec.resolved_assembly_relief_cuts` 後，Manufacturing API 必須先 restore legacy fixed relief，再套 3D cut；孔照原 material interiors 保留。新 CUTTING 建立後 BEND 必須從 authoritative Fold Profile 重建並依新 material 重新 clip，不能沿用舊固定截角截短的 BEND。
- verified cut 必須帶求解來源簽章；W/H/D/T、組合方式、箱身 Fold Profile、Head/Tail Fold Profile 任一變更，舊 cut 自動失效，必須重新求解。
- 實測基準只作 regression evidence，不得寫回公式：W500×H600×D200、T2、FW24、A=0 為 `39×38 + 14×4`；A=5 為 `44×43 + 19×4`。目前主 GUI 預設標準金庫型求得 Head/Tail 均為 `40×39 + 14×4`，且回折驗證零材料穿透。

#### 15.12 Dynamic relief 的 restore ownership：只回補本輪實際求解角（2026-08-28）
- `restore_unrelieved_endcap_material()` 只允許作 3D collision probe / formed reference；它會把整個外框四角補成矩形，**不得直接成為 production solved material**。
- verified dynamic relief 完成後，正式 material 必須從原始 `PartRenderData.material` 出發，只把 `raw_cuts` 有結果的 physical corner 對應 `restored_endcap_relief_delta` component union 回去，再扣除該角新的 verified cut。
- 未參與本輪干涉求解的其他 legacy corner relief 必須保持原 CUTTING，不得因 solver 探測而長回角片。
- 標準金庫型 A=0 regression：對應新尺寸 `40×39 + 14×4` 時，只允許兩角各回留 `2×4` 材料；禁止另外出現 `16×16` 角片。


#### 15.13 組合體箱身 BEND 必須使用 authoritative guide 實線顯示（2026-08-28）
- 單件與組合體的 `BEND` 視覺規則一致：所有 manufacturing BEND guide 都必須以實線顯示。
- 組合體箱身不得只畫 folded mesh 外框。`PartRenderData.scene` 中的 Box Body `BEND` 必須先依同一 Fold Profile / final BEND guide 折成 local 3D，再使用與箱身 mesh 完全相同的 shared assembly transform 放到 world-space。
- BEND 線的 assembly transform 必須以完整箱身 folded mesh 作 reference bbox；禁止拿線段自身 bbox 重新置中，否則線會漂離實際折彎面。
- shared transform owner 為 `ae_engine/assembly_geometry.place_assembly_points()`；`place_assembly_triangles()` 與 renderer 的 Box Body BEND overlay 都必須委派它，避免兩套座標公式。
- 標準金庫型真 GUI 驗收：第一次進組合體後箱身應存在可見藍色實線 BEND；目前預設資料可觀察到 8 條 `#2563eb`、`linestyle='-'` 的 Box Body BEND lines。


#### 15.12 2D / 3D / DXF Live Canonical State（2026-08-28）
- Fold Designer 不再擁有可延後提交的 production draft。3D UI 可以持有 widget/edit buffer，但一旦完成一個有效編輯事件，就必須透過完整 transaction payload 格式的 `on_live_sync(payload)` 寫回主 GUI canonical state。
- 主 GUI `_apply_fold_designer_live_snapshot()` 是 3D -> canonical state 的唯一 host seam；套用時必須有 re-entrancy guard，防止 `update_calculations()` 反向通知 3D 形成 callback loop。
- 3D 視窗關閉只做 `flush pending settings -> save visible part editor -> force publish -> destroy`；不得呼叫 `begin_designer/cancel_designer` 或 rollback。
- `確定 / 取消` UI 不再存在。`還原初始值` 是顯式 production edit，還原後立即 publish；檔案存檔仍需使用者明確操作。
- Assembly dynamic relief solver 只能輸出「verified cut polygon + diagnostics」。真正顯示／輸出的 Head/Tail 必須把 cut 寫回 canonical relief state，再重新 query 與主 2D / DXF 相同的 Manufacturing provider。
- Head/Tail relief 是一個原子交易：required EndCaps 全部 verified 才 commit；任一失敗，canonical relief 不得部分更新，assembly 也必須重新 query canonical geometry 顯示兩片。
- Relief source fingerprint 至少包含 `W/H/D/T/FW + assembly_type + BoxBody Fold Profile + Head/Tail X/Y Fold Profile`。任何不一致都必須失效，禁止 stale cut replay。
- 驗收不以螢幕外觀作唯一證據。對同一 EndCap，主 2D `PartRenderData.material` 與 assembly provider `PartRenderData.material` 的 symmetric difference area 必須 <= 1e-6。

## 15.13 單級 INSERT：真實 mating boundary 與 skin contact 分離（2026-08-29）

- 真板厚 EndCap 由 mid-surface ±T/2 形成 physical skins。collision solver 必須辨識 **contact** 與 **penetration**，不能把任一 skin 與 Box Body 的正常貼合交線直接當成需切除邊界。
- 單級 `INSERT` 的 relief topology 固定為單級；solver 多輪只允許收斂 `primary_u / primary_v`，不得 union 歷次候選而自行長出第二級階梯。
- 對單級 `INSERT`，正式回投影邊界取折後實際 mating boundary；如果兩張 skin 交線落在中心接合邊界兩側，正常 skin contact 帶必須排除，不能取外側 extrema。
- `自訂(9)` regression：`W=400, H=600, D=250, T=2, FW=25`，EndCap X profile `15 + 392 + 15`，Y profile `25 + 244 + 15` / tail native reverse。真實 mating boundary 回投影後 Head/Tail 左右角皆為 `38×27`。先前可觀測到約 `37.02` 與 `38.98` 的兩側 skin 線；取外側 38.98 是錯誤，中心真接合邊界 38 才是製造 relief。
- 上述 `38×27` 僅為 regression evidence。正式演算法仍由 assembly geometry、Fold Profile、T 與 world placement 動態求解，禁止寫死 38。
- verified cut 回寫 canonical relief 後，主 2D、單板 3D、組合圖與 DXF/NC 必須重新 query 同一 Manufacturing provider；尺寸標註也量同一 final material，不可用 legacy fixed relief 或另一套 UI cache。

## 15.14 Pre-solve collision evidence 與 topology/symmetry invariant（2026-08-29）
- collision overlay 必須保存 solver 前的 EndCap probe；production solved material 與 diagnostic probe 是兩個用途不同但來自同一 canonical input 的資料，不得混用。
- `projection_has_material_penetration()` 的 inward tolerance 若把整個 probe interior 消掉，該 probe 即為 sub-tolerance sliver；禁止 fallback 回原 material 把數值薄片復活。
- 3D solver 可以改 corner 尺寸，不得改合法 topology stage count。每個 dynamic cut 在 commit 前都要壓回對應 `restored_endcap_relief_delta` component 的 stage topology。
- topology normalization 後若 physical skin 尚有 crossing，只有在 crossing midpoint 全部位於 topology boundary band 內，且 semantic mid-surface 無 material penetration 時，才可分類為 contact；任一條件不滿足仍為 FAILED。
- X 向鏡像對稱判定使用 folded profile 幾何，不用 UI checkbox。Box Body X 與 EndCap X 都鏡像對稱、且左右 corner components canonical shape 相同時，左右 collision evidence 可取 mirror canonical union，補回 triangle tessellation 漏採樣；非對稱 profile 絕不可強制 mirror。
- assembly intent 測試 Source of Truth 是 `BOX_ASSEMBLY_TYPE_IDS`；新增 registry item 必須自動新增 Head/Tail、pre/post collision、topology、symmetry、2D/3D/assembly、Save/Reload 驗收。

## 2026-08-29 Certified Relief Registry SOP（強制）
1. 建立/修改 EndCap assembly relief 前，先以 `cabinet_family + part_role + joint_face + assembly_intent + topology precondition` 查 Certified Registry。
2. 命中 `CERTIFIED / CERTIFIED_FROM_3D`：公式直接生成 canonical cut；3D 只做 shadow validation，任何候選都不得覆蓋 canonical。
3. shadow 不一致：回 `ENGINE_CONFLICT` 並保留 certified formula，禁止 silent repair。
4. 多筆同優先級命中：`REGISTRY_AMBIGUOUS`，阻止自動決策。
5. MISS：只有「未知組合允許3D求截角」開啟時才可做 3D discovery；成功結果標 `PROVISIONAL_3D`。
6. Promotion：只建立 candidate manifest；多參數回歸＋人工核准後才新增/升版 registry rule。
7. Registry rule 存參數化 formula/precondition/topology/evidence/revision，不存特定 fixture 尺寸。
8. fixed Corner policy 與 dynamic Assembly Relief 都以 family-aware registry 為 Source of Truth；caller 不得另建相同公式。
9. Save/Reload 保存 `rule_id / rule_revision / trust_level`；revision 不存在時 invalidation，不得靜默重算成別的規則。
10. 新增 active rule/intent 後，registry-driven acceptance matrix 必須自動新增案例並通過 Head/Tail、collision、2D=single3D=assembly、Save/Reload。

### 15.15 OVERLAY flat-X 的 manufacturing U basis = 0（2026-08-29 更正）
- `OVERLAY` 的 `x_topology=flat` 表示左右 X BEND 不存在，因此 manufacturing U fold basis 必須為 `0`。
- legacy `yl1/yr1` 只可保留為相容／編輯 metadata；禁止加入 flat-X CUTTING。
- `FW` 是正式框寬 Source of Truth，不得由相鄰折段、outside-dimension 補償或 `FW+T` 重算。
- 上方標準 OVERLAY 單級：`U = FW`；`V = ytop1 + FW - amount_t*T`。
- 使用者實檔 `W=400, T=2, nominal FW=25, ytop1=16, amount_t=1`：箱身 FW 折後 formed occupation=29，因此上方每側 `29×39`；單側未截長 `371`，所以 `29+371=W400`；左右都截後中央 span=`342`。
- 先前 `nominal_side=15 + FW25 = 40 / 中央320` 是錯誤契約，已撤銷。

### 15.16 OVERLAY 上方／下方都使用 physical X basis；Corner residual 各自負責（2026-08-29）
- 上方 OVERLAY 與下方 CROSS 都不得共用 legacy nominal side basis；flat-X 的 physical X bend basis 一律 `0`。
- 上方 U 由 Certified Registry 的 `BOX_BODY_FORMED_FW` mating geometry 提供；EndCap nominal FW25 只保留其自身製造/Y 向語意。
- 下方 `CROSS + EXTRA_CUT + WIDTH + 1.5T` 只提供 `1.5T`；T=2 時每側 `3`、中央 `394`。
- 若上方得到 `40/320`，代表 nominal 15 被錯加；若得到 `25/350`，代表漏看箱身 formed FW；若下方得到 `18/364`，則是下方 basis ownership 錯誤。
- 2D、單板 3D、組合圖與 Save→Reload 必須共用同一 canonical material，並同時通過上方 `29/342`（單側 `29+371=W400`）與下方 `3/394` invariant。


