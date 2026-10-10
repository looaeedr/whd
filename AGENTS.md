---
whd_doc_role: CURRENT
whd_contract: agent-startup-process
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# WHD 開發與本地整合規則

- **舊工單交易、工作槽與 lease 控制系統已退役**；不得要求其憑證、工作槽、Preflight receipt 或其他管控才能執行修改、測試、Git commit。
- **入口及階段分流**：`/派工` 的**施工、修改、測試、commit、PR 與 CI** 只能在 GitHub／排程／雲端執行器完成，嚴禁使用使用者本機。**唯一例外是 exact SHA CI 已通過後的 `LOCALX_INTEGRATION` 最終階段**：此時 `/派工` 可經 Desktop Commander（DC）連線 CoreELEC `whd-dev:/workspace/whd`，**只做使用者本機 `localX` 合併／必要整合驗證／同步回讀**，不得在該階段暗改產品程式或重做雲端施工。`/接手` 仍須使用者明確指令，才可在 RC 進行整個施工流程。
- **產品施工通道**：`/派工` 遠端施工提交後建立 GitHub `localX` 目標 PR，確認 exact HEAD 的 CI SUCCESS；**先透過 DC 在本機 `localX` 整合且保留本機未發布修改**，通過整合驗證後以非強制方式同步 GitHub `localX` 並讀回兩端 SHA／PR 狀態。若 **DC 實際無法連線**，才允許 GitHub PR 直接合併遠端 `localX` 備援，需註明 `DC_UNREACHABLE`、`LOCALX_SYNC_PENDING`，不能聲稱本機已合併或同步。DC 可連但本機有衝突、髒檔、權限拒絕、CI RED，**不可冒用斷線備援**。`/接手` 依其明確指令走 RC 全流程。正式 X 的產品發布仍必須當次 `/推推`。
- **治理直送通道（正式硬閘門）**：僅限 `tools/change_lane_gate.py` 明確白名單內的非產品文件、治理規則、技能、GitHub 工作流程與其專用測試。此類修改**不必**走 localX、`/推推`、工單派工或產品 QA；**優先直接使用 GitHub／雲端治理分支** `governance/*`、`docs/*` 或 `skills/*`，從最新 X 修改、檢查、PR 至 X 並合併。**未取得使用者本次對 DC／本機的明確授權，不得為治理修改存取 CoreELEC、whd-dev 或本地 shell**；雲端能力不足時回報阻塞，不得自動轉走 DC。
- **混合／未知檔案一律回產品通道**：只要包含一個非白名單路徑，即不得走治理直送；檔案改名必須同時分類舊、新路徑，空 diff、跨 repo、來源分支不符都 fail closed。正式判斷由 `.github/workflows/whd-change-lane-hard-gate.yml` 與 `tools/change_lane_gate.py` 執行。
- GitHub 正式硬閘門必須在 X 的 Ruleset 把 `WHD Change Lane Gate` 設為 required status check，否則只能算 CI 檢查、不能宣稱平台端不可繞過；直接 push X 應由分支 Ruleset 禁止。
- 禁止遺失使用者本地未發布修改，禁止用 X 覆蓋 localX。保留程式碼 review、製造幾何與產品回歸檢查；無需工單交易硬閘門。
- 本地工作不需 Google Drive 工作根目錄，也不需調用舊協調分支。
- **兩入口共享交付範圍、不共享施工權限**：已確定 Issue 的 `/派工`、`/接手` 均限定 repo=`looaeedr/whd`、工作分支、PR base=`localX`、exact CI 和回讀。`/派工` 對 DC 的許可**僅限最終 `LOCALX_INTEGRATION`，不代表取得本機施工授權**；`/接手` 才允許使用者 RC 工作區完成施工。無需退役 remote token／unlock；**平台公開上傳安全審查仍有效**，不能繞過。沒有 `/推推` 不得發布正式 X。

## 工單範圍授權延續 `ISSUE_SCOPE_AUTHORIZATION_REUSE`

- **授權以施工範圍為主、SHA 供版本驗證**：使用者已明確核准指定 Issue 的公開交付時，範圍包含 `repo=looaeedr/whd`、指定 Issue、原工作分支、允許修改的功能／檔案範圍、PR 目標 `localX` 與 push／PR／CI／同工單修復／重測／整合 `localX`。執行者須能回讀原授權對話或可驗證的核准證據，不可捏造、不可用另一張 Issue 的核准冒充。**若使用者明示僅限某固定 commit SHA，仍以該較窄的授權為準。**
- **同一工單同一範圍的修復續作**：CI 失敗、必要測試修復而產生新 commit SHA，原授權仍有效，**不因 SHA 更新就要求重複核准公開上傳**。但每個新 SHA 的 diff 都要重新核對原範圍、以新 exact HEAD 重跑必要測試／CI，不能繼承舊 SHA 的 GREEN；於 PR／Issue 留存版本變更證據。
- **跨越原範圍須新授權**：跨 Issue（#1466 的許可不等於 #1467）、repo、工作分支、PR 目標，或新增無關功能、使用者明示排除的檔案；不得用「小修正」包裝擴權。**正式產品 `localX → cleanup/2d-3d-sync` 仍只依當次 `/推推` 與 `tools/localx_publish_gate.py` 的 exact PR／SHA 驗證**，本規則不得放寬。
- **外部平台安全審查不受此規則改寫**：GitHub／RC／自動核准系統若實際拒絕公開 push／merge，保留既有提交，明確回報被拒工具、操作、缺少哪類證據與 `PUBLIC_UPLOAD_REVIEW_BLOCKED`。不得以切換工具或傳輸管道繞過；已具有有效範圍核准時，也不得只是對使用者重播同一句核准問題而不解決證據傳遞。
- 此條不恢復舊 Flow v2／lease／工作槽等交易控制，也不能把聊天文字聲稱為已通過平台審查。

## `/派工` 分階段位置硬閘門 `DISPATCH_CLOUD_BUILD_DC_LOCALX_ONLY`

- **施工階段**（`DISCOVERY / BUILD / TEST / COMMIT / PUSH / PR / CI`）：限 `execution_location=GITHUB|SCHEDULER|REMOTE_ACTION` 的真正雲端執行器（不得暗接使用者裝置）；`RC / DESKTOP_COMMANDER / LOCAL_SHELL / /workspace/whd / Z:\\新WHD` 一律 `DISPATCH_LOCAL_EXECUTION_DENIED`。
- **最終整合階段**（`LOCALX_INTEGRATION`）：PR HEAD exact CI SUCCESS 且 scope／工作分支驗證通過後，**才**允許一次 DC 連線，將已測試的 commit 整合到**本機** `localX`，確認 `localX` 現況並保留任何本機未發布改動；整合必須非強制、不得 reset／覆蓋、不得藉本機修改程式取代遠端施工。完成本機整合後才同步 GitHub `localX` 並回讀兩端；PR 自動關閉或 GitHub 狀態異常時必須實際回讀，不虛構 merge。
- **DC 無法連線的唯一備援**：記錄實際連線失敗／逾時、當時 PR/HEAD/CI 證據後，才可合併 GitHub 遠端 `localX`；標記 `DC_UNREACHABLE + LOCALX_SYNC_PENDING`，安排後續本機對齊而非冒稱本機已整合。DC 可連線但 merge 衝突、工作樹 dirty、認證被拒或測試失敗時**不能**改走斷線備援。
- 沒有雲端施工能力回報 `REMOTE_EXECUTOR_UNAVAILABLE`，不能用 DC 做施工；`/派工` 不會因此隱性轉成 `/接手`。任何平台公開上傳／遠端工具拒絕仍需遵守，不得換 transport 偷渡。

## /派工 產品交付不中斷閘門（執行者責任）

- `/派工` 不以「已建立 PR」「CI queued/in_progress/pending」作為交付完成。這些都是 **CONTINUE_POLL**，不能以「等 CI 完成」作最終答覆來退出當輪任務。
- 一旦已建立指向 `localX` 的產品 PR，就應在**當次可執行回合**追蹤 exact PR HEAD、base 與 Canonical Product Regression 的 GitHub Actions run；短間隔再次查詢。每 2–3 次操作回報實質進度，但**回報本身不是停止訊號**。
- exact HEAD 的 Product Regression `SUCCESS` 且 PR 可整合 → **合併至 localX（本機優先），進入 `LOCALX_INTEGRATION`，使用 DC 合併本機 `localX` → 必要本機整合驗證 → 非強制同步 GitHub `localX` → 兩端 SHA／PR 狀態回讀 → 工單留言 → close + readback**。僅 DC 連線實際失敗時可走遠端 `localX` 備援並標記 `LOCALX_SYNC_PENDING`；不需用戶重複喊「繼續」。
- **觸發點是本機 `localX` 真正合併成功並回讀、或已證實 DC 斷線而 GitHub `localX` 備援合併成功且記錄待同步；不是 Issue CLOSED。** 回讀確認成功後立即執行 `NEXT_ISSUE_DISCOVERY_REQUIRED`：查最新 GitHub Open Issue 與前置狀態、排除已完成／既有 owner／衝突工作；符合資格者直接進入下一張的派工及施工入口。原工單留言／close/readback 仍要完成，但不得把 close 當尋找下一張的前置，也不能因「已結案」就退出。沒有符合條件者要回報搜尋範圍、已檢查原因及 `NO_ELIGIBLE_ISSUE`，不得虛構已派出。

- CI 失敗 → 查該 run 的 job/step/log，修復並重測；沒有執行中的 run → 檢查 workflow branch/path 觸發與權限，修接線並重新觸發。不得將其他 SHA、舊 local GREEN 或 pending 冒充目前 PR GREEN。
- 若實際 API/權限/機器或當次執行限制阻止繼續，必須留下**可驗證的阻塞證據及續作點**，不得寫「派工交付完成」。聊天回合結束後**沒有自動背景輪詢**，除非另有明確建立的排程監控；不得宣稱本規則能自行喚醒模型。
- 以上只授權整合產品變更至 `localX`，**不授權發布正式 X**；`/推推` 是 X 產品發布的必要條件。不得增設 GitHub 分支保護、恢復 Flow v2 或其他舊交易門檻。



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
