# WHD 板金展開自動化系統

## AI 開發交接總覽

# 0. 啟動硬閘門：先完成 Phase6 Knowledge Preflight，才准做事

> **這是所有 AI / Agent / Subagent 接手本專案後的第一個執行規則。優先級高於本文後續章節。**

在進行任何實質的**程式分析、Bug 診斷、派工、規格判斷、程式/測試/SOP 修改、重構、回歸或出包**之前，必須先執行 Phase6 Knowledge Preflight。禁止先靠經驗、記憶或通用技能開始工作，再事後補讀。

第一步固定執行：

```powershell
python tools/phase6_skill_preflight.py --task "<本次任務完整描述>"
```

當預計修改檔案已知後，必須再次帶入所有預計修改檔：

```powershell
python tools/phase6_skill_preflight.py --task "<本次任務完整描述>" --changed-file "<file1>" --changed-file "<file2>"
```

Preflight 輸出的兩類清單都屬於硬閘門：

1. `REQUIRED SKILLS`：讀 `.agents/skills/skill_registry.json` 的匹配結果，將每一個 required Skill 對應 `SKILL.md` **逐一讀完**。
2. `REQUIRED REFERENCES`：將每一個 required reference **逐一讀完**。其中全域踩坑庫永遠必讀；命中領域 route 時，再加讀任務領域踩坑庫與 canonical 規格 / registry / Source of Truth。
3. 全域踩坑庫固定為 `個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`。任何任務都不得省略。
4. 組合／截角／Relief／3D／Joint 類任務的任務領域踩坑庫至少包含 `個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md`；實際清單以 registry 的 `required_references` 為準，不得只靠這一條手工白名單。
5. 讀完後建立 evidence 檔。Skill evidence 保留 Skill 名稱；每一個 reference 必須寫入精確標記 `READ_REFERENCE: <repo-relative-path>`。沒有 evidence 視同未讀。
6. 確認 required Skills、全域踩坑庫、任務領域踩坑庫、canonical 規格 / registry / Source of Truth 全部完成後，才可開始實質分析或修改。
7. 若任務途中新增修改檔、範圍擴大，必須重新跑 Preflight 並補齊新增 requirements。
8. 派工給 Subagent 時，Subagent 必須在自己的隔離工作上下文重新跑相同 Preflight、讀相同必讀來源並留下自己的 evidence；總控不得用自己的 evidence 代替 Subagent。
9. 正式交付前依第 11 節要求再次跑帶 verification evidence 的 Preflight。

### 0.0.1 派工 Skill 實際執行硬閘門

當任務明確要求「派工」、使用 `.agents/skills/engineering/派工/SKILL.md`，或總控自行拆成 PM / Worker / QA 工單時，不能只在文字上宣稱已派工。總控必須驗收以下外顯證據，任一缺失即視為**未實際執行派工 Skill**：

1. 回覆或 checkpoint 中明確出現派工狀態機標記：`[轉移至：實作者]`、`[當前角色：Tn 實作者]`、`[轉移至：總控審查]`、`[當前角色：總控審查]`。
2. 每個工單有實體 checkpoint path；長任務另需 journal/state path，且 checkpoint 內容可讓下一回合不靠聊天記憶續工。
3. checkpoint / journal 至少記錄 task id、工單 id、目前角色、已完成項、pending 項、failed/blocked 項、相關檔案、驗證命令與下一步 resume command。
4. 若環境沒有真正背景 Subagent Runtime，執行者必須依派工 Skill 在同一工作上下文自動完成 PM → Worker → QA 角色切換，禁止回報「已派給其他人等待」。
5. 總控不得接受只有口頭進度、無 checkpoint path、無 journal/state、無角色標記的 Subagent / Worker 回報；此類回報必須退回補落盤，或標記為不可續跑並重建證據。

### 0.1 知識載入優先級

```text
AGENTS.md 啟動硬閘門
    ↓
tools/phase6_skill_preflight.py
    ↓
全域踩坑庫（永遠必讀）
    ↓
.agents/skills/skill_registry.json
    ├─ 專案 required SKILL.md
    └─ required_references
         ├─ 任務領域踩坑庫
         └─ canonical 規格 / registry / Source of Truth
    ↓
通用 Superpowers / 其他一般技能
    ↓
production code
```

**通用技能不能取代專案技能；專案技能也不能取代踩坑庫與 canonical references。** 任一層未完成，都視為尚未取得分析／修改資格。

### 0.2 Fail-closed 禁止事項

以下行為一律視為流程違規：

- 只跑 Skill Preflight 卻未讀 `REQUIRED REFERENCES`。
- 漏讀全域踩坑庫，或命中領域 route 後漏讀任務領域踩坑庫。
- 只讀通用 Superpowers，未讀 `.agents/skills/`、踩坑庫或 canonical references。
- 憑記憶猜哪些 Skill / reference 適用，而不執行 `phase6_skill_preflight.py`。
- 派工給 Subagent 時未要求該 Subagent 重新完成同一套 Preflight。
- 宣稱已執行派工 Skill，卻沒有 PM / Worker / QA 角色標記、checkpoint path、journal/state path 與 resume command。
- evidence 只寫檔名但實際沒有讀取；reference evidence 必須使用 `READ_REFERENCE: <path>`。
- Preflight 有任何 required Skill / reference 未完成就修改 production / tests / SOP。
- 因任務「看起來很簡單」而跳過 Preflight。

若 Preflight 腳本無法執行、registry 缺失、required Skill / reference 找不到，**不得自行降級成無 Skill／無踩坑模式**；必須先修復/定位啟動鏈問題，或明確回報阻塞。

---

> 本文件是下一個 AI 的第一閱讀入口。
> 若需要了解完整架構、金庫型製造規則、零件拓撲對照、開發規範或後續計畫，請再閱讀 `handoff/` 目錄內的細節文件。

---

# 1. 專案核心精神

本專案為 V5 世代的：

> **鈑金自動展開與 DXF 生成引擎**

目前第一套完整驗證的製造體系為：

> **金庫型箱體**

但架構目標不是做成「金庫型專用程式」，而是：

> **以金庫型作為第一套 Factory Policy，建立可持續擴充的通用 2D Sheet-Metal Geometry Engine。**

---

## 1.1 揚棄 Hardcoded Vertex Arrays

新版已開始全面淘汰：

```python
cutting_points = [
    (...),
    (...),
    ...
]
```

這類針對特定零件人工排列 12 點、16 點、17 點主外框的作法。

現在主外框的核心思想為：

```text
母材 Base Polygon
        -
退讓 / 裝配切刀 Relief Polygon
        =
最終 Material Polygon
```

主要透過 Python `Shapely` 執行：

```text
difference
union
intersection
```

最終再取得 polygon exterior 作為 `CUTTING`。

---

## 1.2 Geometry 是唯一真相來源

系統正在收斂成：

```text
Config / 1.csv / 使用者參數
              ↓
      sheetmetal_geometry.py
              ↓
       Geometry Result
        ┌─────┴─────┐
        ↓           ↓
    GUI Preview   DXF Export
```

GUI 與 DXF 不應各自維護一套座標演算法。

---

## 1.3 Topology 與 Factory Policy 分離

必須區分：

```text
Topology
= 這塊板是怎麼折的
```

與：

```text
Factory Policy
= 因為裝配 / 生產需求，哪裡需要退讓
```

例如：

```text
FourSideFlange
```

是一種通用 Topology。

而金庫型封頭尾使用的：

```text
Assembly Insertion Relief
```

則屬於金庫型 Factory Policy。

禁止把目前金庫型規則直接當成所有鈑金箱體的宇宙通則。

---

# 2. 系統模組架構

目前系統主要分為三層。

---

## Layer A：幾何引擎

### `sheetmetal_geometry.py`

負責純 2D 板金幾何。

此層：

```text
不可依賴 ezdxf
不可處理 GUI
不可直接寫 DXF
```

目前主要幾何結構包含：

### FourSideFlange 系列

目前用於：

```text
Door
Indicator Box
Base Plate
End Cap / Tail
```

封頭尾雖然具有較特殊的二折與裝配退讓，但仍應盡可能建立在共用 FourSideFlange / topology 基礎上，而不是重新退化成獨立硬編碼外框引擎。

### StripFoldChain

目前用於：

```text
Box Body
Stretched Box Body
```

它代表沿單一方向連續折彎的板材。

BEND 位置由 segment cumulative sum 動態產生，不再由 exporter 自行維護：

```text
x1
x2
...
x8
```

---

## Layer B：參數整合與 DXF 輸出

### `ae.py`

### 目前開發版本可能為 `ae_3.py`

此層負責：

```text
讀 config.ini
接收尺寸參數
將舊參數轉成 Geometry / Policy
呼叫 sheetmetal_geometry
寫入 DXF layer
處理孔洞與其他 secondary features
```

加工層包括：

```text
CUTTING
BEND
MARKING
CHECK
STOCK
DATUM
```

原則：

> `ae.py` 可以做 Adapter，但不應重新實作 Shapely 主外框布林算法。

---

## Layer C：自動化產線與 GUI

### `batch_unfolder.py`

### `gui.py`

負責：

```text
讀取 1.csv
盤體分類
使用者輸入
批次派發
GUI Preview
```

目前主要待辦：

> 將 `gui.py` Canvas 裡既有的手算預覽座標移除，改為直接使用 `sheetmetal_geometry.py` 的 geometry result。

目標是：

```text
GUI Preview == DXF Structural Geometry
```

---

# 3. Relief / Clearance 的正確定位

不是所有尺寸都必須是 `T` 的倍數。

例如：

```text
ytop1
FW
yl1
yr1
```

這些是真實折邊尺寸，仍然來自：

```text
config
工單
使用者輸入
```

但加工與裝配 clearance 若本質上和板厚有關，應優先表示為：

```text
0.5T
1T
2T
fold - T
```

而不是固定毫米值。

例如金庫型封頭尾目前已確認：

```text
Top Secondary X extra = 0.5T
Top Secondary depth   = 2T
Bottom extra          = 0.5T
```

詳細金庫型規則請讀：

```text
handoff/02_VAULT_FACTORY_RULES.md
```

---

# 4. 理論幾何與加工補償的界線

本 Geometry Engine 應負責：

```text
零件真實外形
折彎拓撲
裝配必要退讓
結構性 interference relief
```

例如：

> 金庫型封頭尾為了插入箱身而產生的 Primary / Secondary Relief

這些屬於零件設計本身，必須留在 Geometry / Factory Policy。

但是下列後加工細節不應污染理論幾何：

```text
Laser Kerf compensation
Corner over-cut hole
一字清角
折床加工補刀
CAM 特殊過切
NC 加工補償
```

這些應由後端 CAM / NC 層處理。

---

# 5. 下一個 AI 的嚴格規則

## 禁止依盤名新增主幾何演算法

錯誤方向：

```python
if part_type == "NEW_PANEL":
    build_new_panel_17_points()
```

正確流程：

```text
先辨識 Topology
↓
尋找現有 Policy
↓
若已有相同物理關係，直接共用
```

---

## 禁止手算主外框 Vertex Array

不得為新截角重新推導：

```text
12 點
16 點
17 點
```

應建立：

```text
Base Polygon
+
Relief / Tool Polygon
```

再做布林差集。

---

## 禁止把金庫型 Rule 當成所有箱型 Rule

目前主要 regression 與製造規則來自：

```text
金庫型
```

未來若新增：

```text
落地盤
壁掛盤
戶外箱
其他箱型
```

應先確認實際裝配方式。

Topology 可以共用。

Factory Policy 不一定相同。

---

## 必須維持 API 邊界

`sheetmetal_geometry.py`：

```text
不可 import ezdxf
```

`ae.py`：

```text
不要自己實作主 Shapely boolean geometry
```

GUI：

```text
不得再自行維護另一套 Structural Geometry
```

---

# 6. 目前進度

目前第一階段通用化已涵蓋：

```text
Box Body
Stretched Box Body
End Cap / Tail
Door
Stretched Door
Base Plate
Indicator Box
```

目前核心方向已由：

```text
每個零件一套座標公式
```

轉成：

```text
Part Parameters
→ Topology
→ Factory / Relief Policy
→ Polygon Boolean
→ CUTTING
→ Material-clipped BEND
```

---

# 7. 下一步任務

目前下一個主要任務：

> **GUI Preview 重構**

將 `gui.py` Canvas 裡原本負責畫零件預覽的手工座標邏輯逐步刪除。

改成：

```text
GUI Parameters
      ↓
Part Adapter
      ↓
sheetmetal_geometry.py
      ↓
Outline / Bend Result
      ↓
Canvas Rendering
```

這樣才能保證：

```text
使用者畫面看到的形狀
=
最終輸出的 DXF 形狀
```

---

# 8. 接手 AI 的閱讀順序

本文件只負責「快速建立全局認知」。

需要細節時依序閱讀：

```text
handoff/00_AI_HANDOFF_README.md
```

快速接手說明。

```text
handoff/01_ARCHITECTURE.md
```

完整 Geometry / Topology / DXF 分層。

```text
handoff/02_VAULT_FACTORY_RULES.md
```

金庫型封頭尾與相關 Factory Rules。

```text
handoff/03_PART_TOPOLOGY_MAP.md
```

Door / Indicator / BasePlate / EndCap / BoxBody 的 Topology 對照。

```text
handoff/04_DEVELOPMENT_RULES.md
```

TDD、Hard-Code 禁令、Regression 與驗證規則。

```text
handoff/05_NEXT_STEPS.md
```

後續重構方向與 roadmap。

---

# 9. 接手後第一個動作

下一個 AI 不要拿到專案就立刻修改。

正確流程：

```text
1. 讀本 AI_HANDOFF.md
2. 按需求閱讀 handoff/ 細節文件
3. 讀 sheetmetal_geometry.py
4. 找目前實際使用中的 ae.py / ae_3.py
5. 讀現有 tests
6. 跑完整 test suite
7. 確認 green baseline
8. 再開始 GUI Preview 重構
```

---

# 10. 一句話核心

> **Geometry 是共用的，Factory Rule 是可配置的，Part Name 不是幾何規則；GUI 與 DXF 最終必須共用同一份 Geometry Result。**

---

# 11. Skill Preflight 強制啟動鏈

Skill 決定「AI 怎麼改」。截角資料庫決定「程式算什麼」。兩者是不同強制鏈，禁止互相取代。

修改任何程式、測試、SOP、registry 或 release policy 前，必須先執行 Skill Preflight：

```powershell
python tools/phase6_skill_preflight.py --task "<本次任務描述>" --changed-file "<預計修改檔案>"
```

機器可讀觸發表固定在：

```text
.agents/skills/skill_registry.json
```

AI 不需要靠記憶猜有哪些 Skill；必須依 registry 列出的 `required_skills` 逐一讀完 `SKILL.md`，並留下 verification evidence。沒讀完、沒 evidence，禁止修改 production code，release gate 也不得出包。

任務類型的最低要求：

```text
截角 / relief / INSERT / INSERT_OVERLAY / WRAP / 3D / FinalScene / AssemblyJoint
→ 必讀 phase6-corner-3d-model-integrity

OVERLAY / flat-X / formed FW / BOX_BODY_FORMED_FW
→ 必讀 phase6-corner-3d-model-integrity
→ 再必讀 phase6-overlay-relief-basis

release / FULL / UPDATE / packaging / 出包
→ 必讀 phase6-release-packaging

GUI 效能 / 卡頓 / live-sync / Tk trace / 重算 / DXF cache / debounce / 3D designer
→ 必讀 phase6-gui-performance-integrity

bug / debug / regression / 修正
→ 必讀 diagnosing-bugs
→ 必讀 tdd
```

正式出包前必須再次執行：

```powershell
python tools/phase6_skill_preflight.py --task "release FULL UPDATE" --changed-file "release_required_artifacts.json" --evidence "<本輪 verification evidence>"
```

若有動到對應 production 檔，但 preflight 顯示任何 `✗`，禁止打包交付。

---

# 12. 截角資料庫強制鏈

截角資料庫不是 Skill。它是 runtime 製造規則 Source of Truth：

```text
基準檔/截角資料庫/certified_relief_rules.json
→ ae_engine/certified_relief_registry.py
→ lookup_certified_endcap_relief()
→ manufacturing geometry
→ 2D / 3D / DXF
```

任何修改 Corner / Relief / Assembly Intent / Registry / 3D backprojection 前，必須先讀：

```text
基準檔/截角資料庫/README_母規則說明.md
基準檔/截角資料庫/certified_relief_rules.json
基準檔/截角資料庫/certified_relief_rules.schema.json
```

Registry HIT 時，Certified JSON 的公式與 metadata 是 canonical 製造答案；production code 禁止另寫第二套公式。Registry MISS 才能進 3D discovery / candidate flow，且 PROVISIONAL 結果不得冒充 CERTIFIED。

