---
whd_doc_role: CURRENT
whd_contract: agent-startup-process
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# WHD 開發與本地整合規則

- **舊工單交易、工作槽與 lease 控制系統已退役**；不得要求其憑證、工作槽、Preflight receipt 或其他管控才能執行修改、測試、Git commit。
- 執行來源以 GitHub Git 與當前本地工作區為準；使用者明確要求 /接手 時在 CoreELEC 的 whd-dev 容器 `/workspace/whd` 施工。
- **產品施工通道**：產品程式、GUI、幾何、DXF、製造資料、產品測試及任何與它們混合的修改，先整合本地 `localX`，再由使用者當次明確 `/推推` 授權 `localX → cleanup/2d-3d-sync` (X)。一般測試需經必要產品回歸，且仍由 `tools/localx_publish_gate.py` 校驗本人 exact PR/SHA 核准。
- **治理直送通道（正式硬閘門）**：僅限 `tools/change_lane_gate.py` 明確白名單內的非產品文件、治理規則、技能、GitHub 工作流程與其專用測試。此類修改**不必**走 localX、`/推推`、工單派工或產品 QA；直接在本機從最新 X 開獨立 `governance/*`、`docs/*` 或 `skills/*` 分支，修改並做對應檢查，推送 GitHub PR 至 X 後直接合併。
- **混合／未知檔案一律回產品通道**：只要包含一個非白名單路徑，即不得走治理直送；檔案改名必須同時分類舊、新路徑，空 diff、跨 repo、來源分支不符都 fail closed。正式判斷由 `.github/workflows/whd-change-lane-hard-gate.yml` 與 `tools/change_lane_gate.py` 執行。
- GitHub 正式硬閘門必須在 X 的 Ruleset 把 `WHD Change Lane Gate` 設為 required status check，否則只能算 CI 檢查、不能宣稱平台端不可繞過；直接 push X 應由分支 Ruleset 禁止。
- 禁止遺失使用者本地未發布修改，禁止用 X 覆蓋 localX。保留程式碼 review、製造幾何與產品回歸檢查；無需工單交易硬閘門。
- 本地工作不需 Google Drive 工作根目錄，也不需調用舊協調分支。


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
1. 讀本 AGENTS.md
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

## 截角資料庫來源

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



---
