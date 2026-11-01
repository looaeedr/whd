---
whd_doc_role: REFERENCE
whd_contract: manufacturing-architecture
whd_canonical: 個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md
whd_schema: WHD_DOC_META_V1
---

# WHD × CADSplit API 架構與權威整合說明

> **文件性質：權威來源整合版（REFERENCE，不是第二份 CURRENT）**  
> **查核日期：2026-11-01（Asia/Taipei）**  
> **WHD 查核基準：** v4 原查核 `localX@eb6cd16bc4c9c595e4330429585e505c24bd8631`（含 #2637、#2638）；v5 增量交叉查核 `localX@fbb271cf3cde0797690ddd78d6cd1013e8c08d41`（本版程式證據以明確讀取的檔案為準）。  
> **CADSplit 查核基準：** `looaeedr/CADSplit` · `main` · `77677c7398eca7ae676c1117a9da0b8d72b9f740`  
> **適用範圍：** WHD GUI、WHD Headless Python API、金庫型／受電箱製造、CADSplit 自動拆圖、現存 JSON／CLI wire、2D／3D／DXF／Save→Reload。  
> **本版修訂：** v5.1／2026-11-01。僅補充「CADSplit 來源 Set/Bay 識別」與「WHD Engine canonical 製造身份」的用詞邊界；這是施工語意澄清，不是原規範衝突或架構變更。v5 原修訂內容：承接 v4 的共用 API／Family 擴充與向後相容原則，補上 CADSplit **從原圖到正式製造輸入的全自動目標**；明確區分 Family 註冊與已實作製造分派、跨版本相容與單次出圖來源追溯、API 成功與 DXF 重開幾何驗收，並修正 Receiving 條件式 Adapter 的表述。此文件仍為 REFERENCE，非第二份 CURRENT；下列「目標／驗收要求」不得誤稱為既有產品能力。  
> **證據分級：** `CONFIRMED PRODUCT RULE`＝已核准產品／架構規則；`CURRENT IMPLEMENTATION`＝目前原始碼現況（未必獲製造放行）；`PROPOSAL`＝本文件的施工建議（尚非 CURRENT 決策）；`OPEN`＝尚待原權威或實測確認。**新增 `PROPOSAL` 不得冒充已採用架構或已通過 CI。**

## 0. 一頁結論

1. **WHD `ae_engine/` 是唯一製造規則與 canonical 結果權威。** GUI、CADSplit、Worker adapter 不得各自持有製造公式、正式製造板件身份決策、展開孔位、折彎補償、截角／裝配退讓、FinalScene 或 DXF 幾何的第二份決策。
2. **WHD GUI 僅負責操作、輸入與顯示。** 正式的製造行為以 immutable request／PartSpec／Context 呼叫 Engine 公開 API；Engine 不得反向依賴 Tk、GUI 或 renderer。
3. **CADSplit 負責原圖來源，而不是製造。** 它識別來源視圖、盤體、孔／Block／文字、原圖座標、來源追溯與替換表，形成經確認的 finished-face Feature／操作輸入；WHD Engine 決定如何製造。**正式全自動目標不能再把人工選取受電箱 JSON 或基準檔目錄當成正常必經步驟**；應從已確認拆圖資料、專案狀態與 Engine 既有資源定位／Family 規則取得，真正缺少可信輸入時明確阻擋而非猜測。
4. **「CADSplit 內有 `ae_engine`」不等於「CADSplit 已直連 WHD」。** 現行 CADSplit `main` automatic bridge import 專案內的 `ae_engine` 程式副本；此為既有 Python 入口，不等於已通過跨程序接線驗收，也不意味著必須與 WHD 最新 commit 相同。所有版本仍以 WHD 的單一製造規則上游為權威。
5. **WHD `integration_cli` 目前沒有開啟任何對外製造能力。** 它只保留 source-only `capabilities / prepare / export` wire 相容入口。`capabilities` 全部禁用；公開 `prepare/export` 經 schema 驗證後仍回 `WHD_OPERATION_NOT_IMPLEMENTED`、`manufacturing_verified=false`，不輸出 DXF。安裝版 `WHD-Engine.exe` 路徑已於 2026-11-01 退役。
6. **公開 Python API 存在 ≠ 每個箱型／板件都已完成製造認證。** read-only preview、部分 `PART_ONLY` DXF、測試 helper、Feature catalog、Schema 列舉或單個綠燈都不能推論整箱／全部 Bay 已獲製造放行。
7. **不同 Engine 版本可以並存，不是必須修正的架構故障。** CADSplit 與 WHD 的 `manufacturing_api.py` Git blob 不同、CADSplit 記載較舊來源 SHA，只說明兩端功能集合可能不同；**不代表舊版不能繼續使用已存在的 API**。但每筆製造必須能追溯實際 Engine／Registry／baseline／原圖來源與驗證範圍；同一組輸入在不同 Engine 版本**不保證**得到相同 DXF。
8. **箱型擴充優先沿用 `ae_engine/cabinet_types/` 與適用的既有公開 API。** 新增 Family 須註冊身份、定義已確認的 Policy／Topology／必要板件能力；單板件可沿用適用的 `generate_part`，組合、多 Bay／批次與 NFB 等應沿用相應 Engine API。只有既有契約無法表達的新操作才增加公開 API。**現行 Family Registry 不等於所有 Part／Operation 已完成資格准入或製造分派**，不得因註冊成功即宣稱可加工；既有金庫型合法流程與舊版已具能力仍須維持。

> **最重要的架構判準：** **不為新箱型複製製造入口；優先擴充 Family 並重用適用的既有 Engine 公開 API。** `DoorPartSpec`／`BoxBodyPartSpec`／`EndCapPartSpec` 為已存在的單板件契約；多片組合、批次與特定 NFB 另有各自的 Engine 公開路徑。Family 註冊、函式可 import、出現暫存 DXF，都不代表已完成該操作的製造資格與驗收。CADSplit 的目標是以**原圖／已確認來源 → 自動構造可信請求 → Engine → 驗證**取代常態人工挑選 JSON／基準目錄。外部 source-only JSON／CLI 停用狀態與此分開。

## 1. 正式權威鏈與文件優先序

| 領域／疑問 | 唯一權威或現行主要來源 | 文件角色 | 不可混淆之處 |
|---|---|---|---|
| 產品已確認的機械需求 | 使用者已核准的產品／機械需求 | 最高需求權威 | 舊測試與預覽不得反推未核准尺寸 |
| 製造架構／公開 API 權責 | [`個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md`](https://github.com/looaeedr/whd/blob/localX/個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md) | **唯一 CURRENT：manufacturing-architecture** | 本文不得另立製造 authority |
| 尺寸、折邊、STANDARD 與裝配語意 | [`07_Phase6尺寸語意與標準截角母規則.md`](https://github.com/looaeedr/whd/blob/localX/個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md) | CURRENT | 外包、成形包外、料尺寸、WRAP 不得混用 |
| 已認證截角／Relief 公式 | [`certified_relief_rules.json`](https://github.com/looaeedr/whd/blob/localX/基準檔/截角資料庫/certified_relief_rules.json) ＋ [`README_母規則說明.md`](https://github.com/looaeedr/whd/blob/localX/基準檔/截角資料庫/README_母規則說明.md) ＋ Registry runtime | Certified data / runtime | Registry HIT 是已知公式權威，3D 不得重寫答案 |
| CURRENT／REFERENCE／HISTORICAL 角色與 owner | [`09_WHD_Canonical_Authority_Map.md`](https://github.com/looaeedr/whd/blob/localX/個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md) | CURRENT：authority map | 同一契約不可出現雙 CURRENT |
| GUI／Engine 單向硬閘門 | [`AGENTS.md`](https://github.com/looaeedr/whd/blob/localX/AGENTS.md) 與 AI 庫 04 | CURRENT | `GUI_ENGINE_API_OWNERSHIP_HARD_GATE_V1` 全箱型適用 |
| Python API 使用與範例 | [`HEADLESS_API.md`](https://github.com/looaeedr/whd/blob/localX/HEADLESS_API.md) | **REFERENCE** | 歷史段落不能覆蓋 CURRENT 架構 |
| 實際 Python 介面 | [`ae_engine/contracts.py`](https://github.com/looaeedr/whd/blob/localX/ae_engine/contracts.py)、[`ae_engine/manufacturing_api.py`](https://github.com/looaeedr/whd/blob/localX/ae_engine/manufacturing_api.py)、[`ae_engine/__init__.py`](https://github.com/looaeedr/whd/blob/localX/ae_engine/__init__.py) | CURRENT production code | export 的存在不等於外部能力認證 |
| CADSplit source-only wire 執行者 | [`integration_cli/cadsplit_worker.py`](https://github.com/looaeedr/whd/blob/localX/integration_cli/cadsplit_worker.py) | CURRENT：source-only CLI owner | 僅擁有 wire 行為，不擁有獨立製造 authority |
| 對外 JSON／CLI 協定說明 | [`docs/integrations/CADSplit_WHD_Contract.md`](https://github.com/looaeedr/whd/blob/localX/docs/integrations/CADSplit_WHD_Contract.md)、[`integration_cli/README.md`](https://github.com/looaeedr/whd/blob/localX/integration_cli/README.md) | REFERENCE | 描述保留協定，不表示可對外製造 |
| CADSplit 現有拆圖行為 | [`整合出圖合併注意事項.MD`](https://github.com/looaeedr/CADSplit/blob/main/整合出圖合併注意事項.MD) 與 `modules/automatic_*_bridge.py` | CADSplit 既有實作／整合資料 | 內嵌 `ae_engine` 是現況，不是跨程式 WHD 權威 |
| CADSplit 專案入口與其記載的歷史 SHA | [`CADSplit/AGENTS.md`](https://github.com/looaeedr/CADSplit/blob/main/AGENTS.md) | CADSplit 現行工程入口 | 記載的 WHD SHA 供追溯，不代表要求消費端必須跟最新版同步或鎖版 |
| API 演進與向後相容 | **使用者確認：新增箱型優先擴充 Family Policy／Topology，沿用適用的公開製造 API；只有既有契約無法表達的新操作才新增公開 API** | `CONFIRMED PRODUCT RULE`，本文件為 REFERENCE 說明 | 舊版已具備的功能不因新增操作而強制升級；不同版本的 DXF 結果仍須追溯與分別驗證，不保證跨版本輸出等價 |

**衝突處理：** 先依已確認產品規則，再依所屬 CURRENT AI 庫／Certified data，再看當前 production code、tests、diagnostics；REFERENCE 和 HISTORICAL 不可推翻 CURRENT。發現 CURRENT 彼此矛盾時必須先校正權威與來源，而非讓 caller 自行選一套公式。

## 2. 三條路徑必須嚴格區別

### 2.1 WHD 內部 GUI → Engine（目標與現行施工規則）

```text
WHD GUI / Tk 操作
  ├─ 收集欄位、使用者動作、來源選擇
  ├─ 僅做格式／型別檢查與 presentation
  └─ 組成 immutable Request / PartSpec / Context
                         │
                         ▼
              WHD Engine 公開 Python API
              ae_engine.contracts / manufacturing_api
                         │
          Family → Topology → Factory Policy
          → Certified Registry / baseline
          → physical part / canonical geometry
                         │
              FinalScene / 2D / 3D / DXF
                  → Save → Reload 驗證
                         │
                         ▼
                  GUI 呈現結果／錯誤
```

這是**權責規則**，不是「所有 GUI 都已完成遷移」的聲明。#2517 持續將既有 GUI 製造決策搬回 Engine，尚未完成全功能驗收。2026-11-01 合併 [#2638](https://github.com/looaeedr/whd/pull/2638) 後新增 `list_cabinet_model_choices()`，使主 GUI／Fold Designer 型號選項共用 Engine read-only API；**此 API 是型號入口，不是製造能力宣告**。

### 2.2 CADSplit `main` 的現有自動拆圖 → 內嵌 Engine 副本（實際程式現況）

```text
原始 DXF / 圖元、Task、finalized info_data
  → CADSplit source owner / view / physical Feature extractor
  → automatic_hole_catalog + 使用者替換 CSV
  → finished-face Feature / operator input
  → automatic_door_bridge / automatic_endcap_bridge
    或 receiving_api_bridge（有經驗證的 resolved geometry 才可出圖）
  → import CADSplit repo 內的 ae_engine.manufacturing_api
  → PartSpec / ManufacturingContext / Engine Python API
  → DXF / verification（依實際 caller、輸出路徑及證據）
```

`automatic_door_bridge.py` 與 `automatic_endcap_bridge.py` 目前都呼叫 `manufacturing_api.generate_part()`；`receiving_api_bridge.py` 有 stable Set/Bay、已解析 physical geometry、batch save/reopen verification 的**條件式 Adapter**，且 `resolve_receiving_source_bays()` 要求呼叫者已提供完整且可信的 Fold／Corner／structure 等必要 Engine PartSpec，與有效 `resource_root`。`export_tasks.run_automatic_processing_tasks()` 在沒有上游 Receiving 輸入時會回 `RECEIVING_API_INPUT_REQUIRED`，不可使用金庫型 bridge 補出圖。**這些只能證明既有條件式內嵌 Python 接線，不代表 Receiving 原圖自動構造完整製造輸入、無人工外部檔案選取或所有 Bay 正式加工已完成。**

**版本差異事實（`CURRENT IMPLEMENTATION`；不是相容性失敗證據）：** 兩 Repo 的 `ae_engine/contracts.py` Git blob 均為 `85dccab7a749…`；v5 增量查核的 `manufacturing_api.py` 在 WHD 為 `993fe38302e0…`，CADSplit 為 `d0539284ab86…`。CADSplit `AGENTS.md` 記載 WHD `36ad9f178b39`；v4 基準 `localX@eb6cd16` 相對它超前 93 個提交，這是歷史快照數字，不是現行差距常數。**各版本能用什麼 API 應依自身實際內容判斷**；不要求鎖版，也不能反推不同版本同輸入的 DXF 必然一致。

### 2.2.1 CADSplit 全自動製造的正式目標（`CONFIRMED PRODUCT RULE`；尚未驗收落地）

**目標流程不要求使用者在常態自動拆圖時另外挑選「受電箱 JSON」或「基準檔目錄」。** 使用者回報目前 GUI 仍有這些人工選取步驟；本次已確認接線函式需要外部餵入已建立的 Receiving source／resolved DTO 與 `resource_root`，但**尚未完整重現 GUI 每個檔案選擇視窗的行為**。因此將「人工選取為現況」列為 `USER-REPORTED CURRENT BEHAVIOR`，而「常態全自動」列為明確的目標要求，禁止把它寫成既有能力。

```text
CADSplit 原始 DXF／已確認 finalized info_data／專案持久化狀態
    → 自動辨識盤名、Family、來源視圖、尺寸、孔源、來源 Set/Bay 標籤／關聯、來源版本
    → 根據正式來源定位已存在的 Engine 資源／Registry／baseline
    → 由 Engine 公開 API 建立或解析必要 PartSpec／Fold／Corner／Topology
    → Engine 依 canonical state／Family／Topology 對應來源 Set/Bay，決定正式物理片身份／角色
    → 依 Family + Part + Operation 進行製造資格與來源完整性檢查
    → 已驗證的 Engine 製造與 DXF Save→Reload
    → CADSplit 顯示結果、檔案及可追溯證據
```

- CADSplit 應從**現有拆圖資料與已持久化、已確認的專案設定**自動建構或取得當次請求；JSON 可以是既有內部狀態／DTO 的序列化，不得被設計成每次必須由操作者另行瀏覽指定的外部前置檔案。
- `resource_root`／baseline 應由既有專案根目錄、受信任的 Engine 資源查找／Family source contract **自動解析並檢查**；不要求操作員平常手選「基準檔目錄」，也不默默搜尋不受信任的任意檔案。
- **來源可辨識 ≠ 來源足以加工。** 原始 DXF、CSV 缺少 Factory Policy／Fold／Corner／裝配等必要已確認參數時，應查既有正式 Engine/Project authority；仍無唯一可信答案則僅阻擋該 Bay／板件／操作並回明確缺項，不得用畫面 bbox、金庫型預設或猜測數值補洞。
- **來源識別不等於製造身份決策：** CADSplit 自動辨識並維持來源盤名、Set／Bay 標籤／關聯、穩定來源鍵與版本證據，傳入請求以便定位和追溯；這些來源標籤不直接構成製造 `physical_part_id`。WHD Engine 依已確認的 canonical project／assembly state、Family／Topology 與來源對應，決定正式物理片身份、板件角色、數量及輸出命名空間。CADSplit 不得按來源視圖數目自行發明 BoxBody／Door／Head／Tail／Divider／NFB 板件；來源 Set／Bay 不能可靠對應時，應回報缺項並僅阻擋受影響範圍。
- 若真遇到原圖模糊、來源缺漏、衝突或資料版本漂移，允許**例外的明確補件／確認**，但不得把人工選 JSON／選資料夾當成日常全自動流程；例外不能降級為未驗證製造成功。

**驗收方式（`PROPOSAL`，尚未宣稱 CI 已覆蓋）：** 對有完整可信資料的金庫型／受電箱來源，從單一原圖與既有專案資源啟動，無需人工另選 JSON／baseline root 即能建立對應 Engine requests、輸出已獲放行的範圍並完成獨立 Save→Reload；對缺 Fold／Corner／基準／Set/Bay 憑據的案例，應明確指出缺項且不得輸出該範圍的正式 DXF。既有完整資料的金庫型門與封頭尾回歸不得退化。這是補足現有 upstream 資料接線，不建立 CADSplit 第二套製造引擎。

### 2.3 CADSplit → WHD 外部 JSON／CLI（保留，但製造停用）

```text
CADSplit －－ JSON／CLI wire －－> WHD integration_cli/cadsplit_worker.py
                 capabilities －－> source-only; supported_part_kinds=[]
                 prepare      －－> schema validation → NOT_IMPLEMENTED
                 export       －－> schema validation → NOT_IMPLEMENTED
                                          manufacturing_verified=false
                                          無 DXF 輸出
```

這條路徑 **不是** (2.2) 的同義詞。存在命令、Schema、response 或內部 trusted helper，不代表這條路徑已接通真正的 Engine 製造。

### 2.4 核心箱型擴充：一套製造入口、多個 Family（修正 v3）

**設計目標（`TO-BE`，不是目前已完成的呼叫圖）：**

```text
WHD GUI ／ CADSplit（可信 operator/source request）
           │
           ▼
ae_engine.contracts / 適用的 manufacturing_api 公開入口
           │   單板 generate_part；實體組合／批次／NFB 使用相應既有 API
           ▼
Family Identity（cabinet_types.registry）＋ Family Policy / Topology
           │   檢查該 Family／Part／Operation／來源的實際製造資格
           ├─ vault：沿用經驗證的金庫型既有製造行為
           ├─ receiving：僅實作受電箱已確認的專屬差異
           └─ ro：implemented=False，未經驗證不可放行
           ▼
共用 Engine geometry / Certified Registry / physical parts
           ▼
正式 FinalScene → 適用的 DXF Save→Reload → 驗收狀態
```

**現況（`AS-IS`）：** `cabinet_types/registry.py` 主要管理 Family identity／aliases；`policy.py` 只對現有能力使用 Family module hooks。`manufacturing_api._export_to_temp()` 仍依 `PartSpec` 類別直接進各 exporter，沒有在此入口先完成所有 Family／Part／Operation 的統一製造資格檢查；`_base_plate_export()` 仍直接比對 `受電箱`／`RECEIVING`。因此上圖**不可被標示為目前已全面落地的 Family 製造分派架構**。

**使用者確認之擴充原則（`CONFIRMED PRODUCT RULE`）：**

1. **原本架構不變。** 新箱型優先沿用既有 request、PartSpec、Family/Topology/Policy 與**適用**的共用 Engine 公開製造 API；`generate_part` 是單板件入口，不能強制所有組合／批次／NFB 都經同一函式。不得因受電箱加入便對金庫型另開平行生產入口。
2. **在 `ae_engine/cabinet_types/` 擴充，但不把「註冊完成」等同「製造完成」。** 在 `registry.py` 註冊身份及 alias，已核准差異由對應 Family 模組與 `policy.py`／既有拓樸 owner 提供；公開 API 執行時仍需核實 Family／Part／Operation／來源的實際適用資格。缺能力明確 unsupported，不能因 `implemented=True` 或 `PartSpec` 可建立即推論有合法 DXF。
3. **新增公開入口是最後選項，不是每新增一種箱型就必須做。** 只有既有 API 真正無法表達的新操作（例如新型獨立交易）才向後相容增加公開函式／DTO；不得以「新 Family」或「新板件」為由複製已有的 Door／BoxBody／EndCap 製造入口。
4. **金庫型舊路徑不可改壞。** 既有名稱、PartSpec 輸入語意、合法成功／拒絕情境、Geometry、2D/3D、DXF 與 Save→Reload 行為必須回歸；修復經證實的製造 bug 另依 CURRENT 資料處理，不可偷換原契約。
5. **舊 Engine 缺新增能力很正常。** 只拒絕當版不存在的新功能，舊版的既有能力照常提供；不要求 GUI、CADSplit、Engine 同 SHA，也不因新功能的缺席全面停用既有功能。
6. **來源與認證另算。** API 可呼叫不等於製造通過；各 Family／Part／Operation 按其實際 Registry、baseline、工藝和 Save→Reload 的已認證條件判定。

**現行程式查核（`CURRENT IMPLEMENTATION`，非已驗證故障原因）：**
**2026-11-02 使用者再次確認（`CONFIRMED PRODUCT RULE`；以 AI 庫 04 CURRENT 為權威）：** 「同一條擴充」是現有 `ae_engine.contracts`／`manufacturing_api` 的共用製造體系，新增 Receiving Family 差異只能在既有 Family／Topology／Policy owner 延伸；不是要求所有作業只呼叫 `generate_part`，也不是為受電箱新設 `dispatch_manufacturing_integration(export)` 平行製造路由。CADSplit 金庫型已能以完整 Door／EndCap `PartSpec` 呼叫既有 `generate_part`；Receiving 應從可信原圖來源與 Project/Factory state 補齊完整真實 `PartSpec` 或既有適用 Engine 製造 Request，經相同 Engine owner 製造及 DXF Save→Reload，不得自行造 Fold、Corner、物理板件身份或額外 JSON／Bridge／GUI。

**真圖 API 證據與拒絕語意（`CURRENT IMPLEMENTATION`）：** CADSplit [#15 真實 API 實測](https://github.com/looaeedr/CADSplit/issues/15#issuecomment-6565031621) 分別以 `p1~.dxf`、`a-pt1~.dxf` 來源身分呼叫 `dispatch_manufacturing_integration(operation="export")`，得到 `EXTERNAL_EXPORT_NOT_CERTIFIED`／`WHD_INTEGRATION_MANUFACTURING_NOT_CERTIFIED`、`manufacturing_authorized=false`，製造 DXF 0。WHD `ae_engine/integration_api.py` 這個 source-only `export` 分支對所有進入的已實作 Family 都固定拒絕；它**不是**金庫型已使用的 `generate_part` 出圖路徑，不能由此推論 Receiving Engine 本體不能製造，也不能靠追加 CSV 欄位取消拒絕。不得為了讓這項呼叫成功而刪除 fail-closed、偷換 source-only 入口用途，或把它升級成第二條製造權威。

**未完成的共同接線驗收：** 以同一可追溯來源／當版 Family×Part×Operation 核對資料所有權及必需欄位；對完整可信的 Vault／Receiving Request 分別測真實 Engine 解算與 DXF 獨立重開，對缺 Factory/Topology/Set-Bay/Features/revision、未支援 Part 或漂移做負向拒絕，且保證金庫型既有可用操作不退化。未實際測試者標未完成，source-only `prepare`、`capabilities`、Family `implemented=True` 均不等於製造放行。





- `cabinet_types/registry.py` 目前主要提供 `CabinetTypeRegistration`、別名及註冊；`vault.py` 目前只有註冊資訊，`receiving.py` 已包含多項受電箱 Family 規則；`policy.py` 透過 registry 與 module hook 提供**部分** Family-aware 能力分派。這證明擴充點存在，但不是完整的製造權限宣告或全路徑分派。
- `manufacturing_api._export_to_temp` 依 `PartSpec` 類別進入 Door／BoxBody／EndCap／BasePlate 等 exporter；`_base_plate_export` 仍直接判斷 `受電箱`／`RECEIVING`，需逐項釐清可移回既有 Family Policy 的差異。**目前沒有證據證明整體入口已在執行前統一拒絕未支援 Family／Part／Operation，也不能反推此處造成所有金庫型／受電箱故障**。
- #2638 的 `cabinet_model_choices.py` 是將 GUI 原有清單邏輯搬入 Engine 的唯讀 API；仍直接特殊判斷金庫型的 baseline。這是待清理的 Family-specific selector policy，但非第二套製造 executor，也沒有足夠實證宣稱它導致製造故障。
- 目前未取得使用者所述「新不能用、舊也壞」的具體可重現輸入／DXF 差異；正式產品修復須先沿真實 GUI → Family → Engine → Save→Reload 測試找到 RED，再改程式。不可以文件判定來臆造製造公式或當作 CI GREEN。

**不綁 transport：** 同程序 Python 或將來的新 transport 都沿用上述共用 Family/製造入口；這與外部 installed Worker／EXE 已退役並不矛盾。

## 3. 各層模組責任與禁止事項

| 層 | 負責 | 禁止 |
|---|---|---|
| CADSplit source adapter | 盤體／來源視圖辨識、原圖物件、真實孔來源、CSV selector／替換、finished-face 相對位置、來源檔 SHA／handle／revision、錯誤紀錄 | 推算展開料 CUTTING／BEND、製造 Fold、截角、製造方向補償、臆造 Bay 板件 |
| WHD GUI / Phase6 adapter | 操作、選片、輸入、顯示、錯誤訊息、將操作者值轉成 immutable DTO | 呼叫低層 `ae.export_*`、`ezdxf` 製造、私有 geometry helper、重複製造演算 |
| Public API (`ae_engine.contracts`, `manufacturing_api`, `__init__`) | 公開 DTO、製造入口、出圖／狀態／校驗與結果契約 | 反向 import GUI/Tk；以 GUI state 取代 canonical spec |
| `ae_engine/cabinet_types/` Family Registry / Policy | 以 registry 辨識箱型／alias、各 Family 模組保存差異、policy 供共用 Engine 呼叫，實體拓樸／折法依既有 CURRENT owner 解算 | 因新增箱型而複製 `generate_part`／金庫型 DXF 管線；在主 GUI 硬寫受電箱製造規則；把未註冊型別冒稱已實作 |
| Certified Registry / Baselines | 認證 Relief 公式／revision／metadata、正式基準來源 | 用測試 fixture／3D shadow 推翻 Registry HIT；把 Registry MISS 當已認證 |
| Manufacturing / Export / Serialization | 產生 canonical physical material、BEND、Features、Joint、2D／3D／DXF、原子寫入、重開驗證 | 使用 Preview／Canvas 當製造答案；寫未驗證 DXF；悄悄覆蓋來源 |
| `integration_cli` | 版本化 wire、JSON 驗證、協定回應、fail-closed source-only 相容 | 自行啟用安裝版製造、建立第二套 Engine、把 Schema enum 當作 capability |
| API 增量演進／相容性 | **先擴充 Family；先重用既有共用製造入口**；真正新增操作才另加公開 API。保留舊 DTO／結果，版本只供追溯 | 為每個箱型再開平行製造入口、破壞金庫型老行為；因 SHA 不同禁用舊功能 |

## 4. Python 公開 API：功能分類與實際狀態

實際 export 以查核當下的 `ae_engine/__init__.py` 與 `ae_engine/manufacturing_api.py` 為準。以下**列代表性公開入口，不宣稱所有 export 都有完整製造認證**。

| 類別 | API／型別（例） | 權責／使用方式 | 能否直接推導外部 CADSplit 可用？ |
|---|---|---|---|
| 請求 DTO | `ManufacturingContext`、`ManufacturingPolicy`、`DoorPartSpec`、`BoxBodyPartSpec`、`EndCapPartSpec`、`BasePlatePartSpec`、`IndicatorBoxPartSpec`、`CustomFoldPartSpec` | typed／immutable 輸入與製造上下文 | **不能** |
| 一般單板件 | `generate_part(spec, output_path, context)`、`PartExportResult` | WHD Engine 內部的無 GUI 單板件出圖入口，依型別 dispatch | **不能**；需另驗對外 operation |
| 型號清單（#2638） | `list_cabinet_model_choices(available_baselines=None)` | 統一主 GUI／Fold Designer 型號選項；金庫型需有來源基準，受電箱可用已實作公式型入口 | **不能**；read-only selector 不等於製造認證 |
| Policy／來源 | `resolve_policy`、`expected_baseline_path_for`、`receiving_baseline_source_stamp` | 工廠設定、基準檔來源與指紋 | **不能** |
| 來源 Feature | `map_door_features_to_unfolded_material`、`door_finished_face_size`、`door_indicator_offset_for_finished_center` | 成品面語意、由 Engine 做投影／校正 | **不能** |
| 實體板件／批次 | `materialize_resolved_manufacturing_parts`、`save_resolved_manufacturing_geometry_batch_dxf`、`verify_saved_resolved_manufacturing_geometry_batch_dxf` | resolved physical pieces 與批次 DXF／保存重開驗證 | **不能**；需真實完整 geometry 與驗證 |
| Family／Fold | `resolve_live_cabinet_family`、`build_box_body_fold_profile`、`build_endcap_xy_fold_profiles`、`resolve_receiving_box_body_structure_state` | Family、Topological Fold、結構尺寸決策 | **不能** |
| Relief／Joint | `solve_endcap_assembly_relief`、`resolve_manufacturing_joint_graph`、`resolve_family_divider_reliefs`、`replay_resolved_endcap_render` | 正式物理組合、Registry 與已驗證 material；不可用 3D 直接蓋過 certified 規則 | **不能** |
| Receiving NFB 來源／顯示 | `candidate_committed_csv_nfb_config`、`resolve_receiving_nfb_assembly_parts`、`validate_receiving_nfb_manifest_view`、`project_receiving_ear_side_piece_2d_preview` | 來源狀態、實體 identity、read-only manifest／preview | **不能**，部分僅供顯示 |
| Receiving NFB 部分出圖 | `export_verified_receiving_nfb_inner_door`、`export_verified_receiving_nfb_base_plate`、`export_current_csv_nfb_door_base_pair` | 在特定已提交／驗證來源下進行指定實體 `PART_ONLY` 出圖 | **不能**推論 EAR／PAD／整箱 MFG-2 已認證 |
| 2D／3D 顯示投影 | `project_solid_mesh_xy_outline`、`resolve_receiving_settings_assembly_world_meshes` | 物理 mesh 轉檢視資料，GUI 只畫圖 | **不是** CUTTING／DXF 證明 |

**注意**：同名 API 的 import、Facade re-export、幾何結果型別、單元測試，不自動授與其他箱型、其他來源、其他板件或外部跨程序製造權限。**增加新入口不得讓舊入口失效**；新入口未出現，不代表舊版不相容。

### 4.1 API 能力分級與宣告原則（避免「可 import＝可加工」）

下表是**評估欄位的建議分類（`PROPOSAL`）**，不是宣稱現行 repository 已有同名 capability enum 或已完成正式對外查詢服務。每項 Family／Part／Operation 應分開記錄：

| 分級 | 可以證明什麼 | 不能推論什麼 |
|---|---|---|
| `IMPORTABLE` | 該版本的公開 Python 名稱存在且可載入 | 製造成功；其他舊入口因缺少新入口而失效 |
| `READ_ONLY` | 來源解析、型號列表、preview／manifest 顯示已測 | CUTTING、BEND、正式 DXF 可出圖 |
| `PART_ONLY_VERIFIED` | 指定輸入與指定實體、DXF 保存重開及幾何驗證已通過 | 其他板件、Set/Bay 或 complete assembly 可製造 |
| `BATCH_VERIFIED` | 指定批次／實體集合交易與驗證已通過 | 未包括的 topology／NFB／EAR／PAD 可製造 |
| `ASSEMBLY_VERIFIED` | 明示 Family、所有必要物理片、來源與裝配驗收已通過 | 其他未驗來源／實體也獲得授權 |
| `EXTERNAL_VERIFIED` | 已決定並驗收的**具體外部入口**與端到端功能範圍 | 其他入口、其他 Family 自動認證；或所有客戶必須同版 |

功能可用性應先確認**該版具備所需入口及合法輸入語意**，再依 `family`、`part_kind`、`operation`、`output_scope`、`source_requirements`、`verified_scope`、`blocked_reason` 判斷；`engine_revision`、`registry_revision`、`baseline_fingerprint`、`source_revision` 屬**單次製造結果應可追溯的資料**，不作「兩 Repo SHA 必須一致」的全域版本鎖定。即使兩版均能呼叫同名 API，同一輸入也**不能未經比對就宣稱 DXF 幾何等價**。未支援的新功能 blocked，原有能力依自身已驗證的 scope 繼續使用。**以上名稱是文件用評估欄位與狀態分級，並非當前公開 schema／enum。**

### 4.2 一般單板 Python API 範例（只示意同程式中的正式入口）

```python
from ae_engine.contracts import DoorPartSpec, ManufacturingContext
from ae_engine.manufacturing_api import generate_part

part = DoorPartSpec(
    width=500,
    height=600,
    thickness=2.0,
    frame_width=25.0,
    model_name="金庫型",
    features=(),
)
result = generate_part(
    part,
    "門-展開.dxf",
    ManufacturingContext(resource_root="<含基準檔的已驗證目錄>", overwrite=False),
)
```

這段是 **Python 同 runtime** 呼叫示例，不是 CADSplit JSON／CLI 示例，不是對未知來源的出圖授權。真實出圖還必須符合 `PartSpec` 內容、來源資料、基準檔、Registry、正式製造驗收及輸出權限；如已存在正式檔且 `overwrite=False`，應拒絕覆蓋。

## 5. CADSplit ↔ WHD 資料與座標契約

### 5.1 來源與製造的分界

- **CADSplit 擁有：** 原始 DXF 的 source ownership、來源圖元／Block／Text、分類、來源 Feature 候選、CSV 替換規則、來源檔版本與抽取／轉換證據；`finalized info_data` 等 CADSplit 正式輸入語意不能用畫面 bbox 反推。
- **WHD Engine 擁有：** `PartSpec` 的真正製造語意、Family/Topology/Policy、基準檔、實體分件、已認證角部／裝配退讓、成品面對應至展開料的投影、CUTTING／BEND／MARKING／BLIND_HOLE、DXF 驗證結果。
- **雙方不得：** 共用兩套可互相漂移的 Fold／Relief 計算；CADSplit 不得為了補缺 API 自行算 `offset`、鏡像整張製造圖或宣告 unknown physical part READY。

### 5.2 finished-face Feature 是 1:1 mm 的來源契約

```text
source_finished_face_center = 原始來源成品面中心
source_feature_center       = 原圖實體 Feature 中心

來源相對位移：
  dx = source_feature_x - source_finished_face_center_x
  dy = source_feature_y - source_finished_face_center_y

由 WHD Engine 的 finished-face resolver 投影到正式材料／DXF 座標。
```

這個算式描述**來源定位／傳輸座標**，不是新的展開／加工製造公式。禁止把 Canvas pixels、0～1 normalized positions、原圖整張 view bbox 中心、展開總料中心當作 finished-face center；門四邊 Fold 不同時尤其不能假設 finished-face center 等於 stock center。封頭／尾的鏡射與旋轉若屬製造決策，必須由 WHD 正式 Engine 全圖一致處理，不能在 CADSplit 只翻孔。

### 5.2.1 座標方向與 transform 所屬責任（`PROPOSAL` 待正式契約落地）

目前 5.2 只確認 finished-face 相對位移與單位，**未足以證明所有旋轉／鏡射／正反面情境可互通**。未來同源 API request 需能在現有實作基礎上驗證下列資訊；新增欄位名稱與數值約定必須由 CURRENT Engine contract 定義，不能讓 CADSplit 擅自發明：

- **Source frame**：DXF 單位、原點、視圖和成品面定位依據，以及被引用的 source entity handle／SHA；只以視圖 bbox 代替實體成品面基準不合格。
- **Finished-face frame**：成品面局部原點、X/Y 正向、面向／正反面、單位 mm、經驗證的 feature anchor；必要時指明 mirror/rotation 原因與可逆轉換證據。
- **Manufacturing frame**：由 WHD Engine 以 canonical PartSpec／Family／Fold／Policy 決定料面、折後位置、全圖鏡射／旋轉及最終 DXF；CADSplit 不擁有製造 transform。
- **Round-trip oracle**：真實孔中心與形狀（含非中心特徵）在相同 source／PartSpec 下，完成原圖→finished-face→Engine→保存重開後仍符合 CURRENT 允差；頭尾左右或正反面案例需明示期望，不可由畫布方向反推。

此處不固定「一律左下為零」、「一律順時針」、「鏡射 X」等尚未經所有 Family 核實的產品事實。

### 5.3 尺寸與實體身份

- `W/H/D/T`、FW、`OUTSIDE`、`MATERIAL`、`FORMED_OCCUPATION`、INSERT／OVERLAY／WRAP 的語意與換算，依 CURRENT 07 與 Registry；本文件不複製正式加工公式。
- **來源識別（CADSplit）：** 從已確認的原圖、`finalized info_data` 和持久化專案資料識別來源盤名、Set／Bay 標籤及關聯、來源版本與穩定來源鍵，保留原始 DXF SHA／handle 等追溯資料，供製造請求關聯使用；來源識別本身不決定正式製造板件。
- **製造身份（WHD Engine）：** 依 canonical project／assembly state、Family／Topology、PartSpec 與來源對應決定正式 `physical_part_id`、實體板件角色／數量及各 Set／Bay 的製造映射；多 Bay 保留各自獨立的製造實體鍵與輸出命名空間。來源標籤和 GUI label／資料夾名稱不能直接冒充 canonical 製造身份。
- 受電箱 NFB CSV 來源、品牌、型號、已提交證據、世界 X／旋轉、真實 source DXF SHA／handle 等變更，必須使受影響的舊驗證失效；未提交資料不能混進正式出圖。
- read-only preview／trial scene、局部 `PART_ONLY` 的認證範圍，不能延伸為完整組合體製造認證。

### 5.4 來源與執行版本可追溯性（不做版本鎖定）

**版本相容**與**單次製造結果可追溯**是兩個獨立問題。CADSplit／WHD 不要求同 SHA、不強迫舊版為未使用的新 API 升級；舊版仍有的功能依自身合法來源與已驗證範圍運作。但對每筆**正式製造結果**，應可從原有受信任記錄／結果回讀關聯下列事實（欄位如何落在現有結果結構，屬實作設計，非現行已完整提供）：

- 執行的 Engine 身分／實際 revision、被呼叫的公開 API／operation，以及 Family、PartSpec／物理片、Set／Bay／版本 scope。
- 採用的 Certified Registry 規則及 revision／內容指紋、Family/Factory Policy 來源與必要參數、baseline 實際路徑與內容指紋（或經核准的 formula-only 路徑及理由）。
- 原始 DXF SHA／必要 entity handle、CSV／替換表 revision、finished-face Feature／immutable request digest、實際輸出 DXF digest、幾何驗收範圍及結果／錯誤。

**`CURRENT IMPLEMENTATION` 差距：** 目前共用 `PartExportResult` 主要有 `part_kind`、`output_path`、`exporter_name`、`used_baseline`、`baseline_path`、`expected_baseline_path`，尚不足以獨立表示上述全部版本／來源證據。`integration_cli` source-only capabilities 的 `engine_commit` 與其他欄位不構成正式製造結果，不能拿它填補這項缺口。後續實作應優先沿用現有可追溯資料 owner，不建立第二套管理流程。

**不保證跨版 DXF 相等：** 即使輸入表面上相同，Engine／Registry／baseline／Policy 或 transform 的差異都可能造成不同輸出。只對實際需要的功能與來源作契約／幾何比對；來源變動使相關操作驗證失效，不能反過來宣稱整個舊版不相容。

## 6. source-only JSON／CLI 協定（存在 ≠ 啟用）

### 6.1 唯一保留的公開命令

```bash
python integration_cli/cadsplit_worker.py capabilities --response /safe/out/capabilities.json
python integration_cli/cadsplit_worker.py prepare --request /safe/in/request.json --response /safe/out/prepare.json
python integration_cli/cadsplit_worker.py export --request /safe/in/request.json --response /safe/out/export.json
```

命令只是**協定查核／拒絕**用；請勿把 `export` 的字面當作可產出正式 DXF。沒有公開 `verify`、`--installation-id`、`_private_installed` 或已啟用的安裝版 Worker。CLI 不覆寫已存在 response，驗證 JSON／來源路徑與輸入 ID 時採 fail closed。**未來共用 Python API 的建議路線與此 source-only CLI 為兩件事；此段不構成重新啟用現有 wire 製造的授權。**

### 6.2 v1.0 Wire 欄位概覽

| 訊息 | 核心欄位 | 現行真實語意 |
|---|---|---|
| Request | `protocol_version`、`client_installation_id`、`request_id`、`job_id`、`request_digest`、`operation`、`coordinate_contract_revision`、`items[]` | JSON/schema/關聯識別；不是製造授權 |
| Request item | `item_id`、`part`、`source_document_sha256`；可有 `physical_part_id`、`features`、`preparation_digest` | 傳輸來源與意圖；不能自行創造 WHD 物理幾何 |
| Capability response | `engine_version`、`engine_commit`、`supported_part_kinds`、`capability_flags`、`resource_health`、各 SHA | source-only metadata；目前 `supported_part_kinds=[]`，flags 全 false |
| Prepare/export response | `operation`、`status`、`manufacturing_verified`、`items`、`diagnostics`、關聯欄位 | 合法請求仍 `failed`／`WHD_OPERATION_NOT_IMPLEMENTED`／`manufacturing_verified=false` |

- 目前 `protocol_version=1.0.0`；`coordinate_contract_revision="1"`。schema 列出的 `part.kind` 只是可能的 wire 值，**不代表任何 kind 能出圖**。
- source-only `engine_version=source-only-unreleased`，`installation_id=source-only-<commit-prefix>` 只是協定相容 metadata，**不是**安裝身份、金鑰或製造認證。
- `request_v1_1`、`response_v1_1`、`capabilities_v1_1` 可存在於 repository，屬先前外部試驗的相容／參考 artefact；不能據此宣布 1.1.0 installed family routes 已放行。
- CLI 的 `max_batch_items=20` 是請求防護上限，不代表能執行 20 件製造。

### 6.3 退役邊界

2026-11-01 的 CURRENT 決策已停用：`WHD-Engine.exe` 安裝版／打包契約、DPAPI/HMAC installer custody、packaged identity admission、private installed command、public installed certification。W-03/W-04/W-06 的 Python helper 可以留下作**非公開內部基礎**，但不能從 Git history 偷接回公開 CLI。未來如重新需要 executable/installer，先要使用者新決策及正式 CURRENT owner，並通過 exact-SHA 的真實製造驗收。

## 7. 功能覆蓋與製造放行矩陣（截至本次查核）

| 範圍 | 現行程式證據 | 可主張的狀態 | 不可主張的狀態 |
|---|---|---|---|
| 金庫型單板 Door／Head／Tail／BoxBody／BasePlate／Indicator | WHD `generate_part`、相關 PartSpec、API tests | 有 Python 製造 API 與對應測試路徑 | CADSplit 外部 Worker 已核准任何 kind |
| CADSplit 金庫型 automatic door／endcap | 兩個 bridge 實際使用內嵌 Engine 的 `generate_part` | 來源辨識 → 同程序 Engine Python API 的接線現況 | 跨程式 WHD 正式 API 已接通 |
| WHD 受電箱 GUI／Engine | #2517 已有多個部分 API：Family、Fold、NFB、assembly、顯示／部分出圖；#2638 再加入共用型號清單 | 個別 port 需逐一依其特定 scope 驗收 | 「受電箱全部功能 API 完成」或模型可選即代表可加工 |
| CADSplit Receiving bridge | 已存在已解析 Bay／經填妥 PartSpec 的條件式 Adapter 與 batch save → verify；缺上游完整資料回 `RECEIVING_API_INPUT_REQUIRED` | 有受限的同程序 adapter 與 mock／契約測試 | 從原圖不需人工 JSON／baseline 選取、全 Bay 全自動製造或任何路徑已完整驗證後才提交 |
| Receiving NFB inner door／base pair | WHD 的 verified `PART_ONLY` public APIs | 特定來源下的局部 DXF 出圖入口 | NFB PAD、EAR、整箱 MFG-2 或所有 CUTTING 已放行 |
| source-only CLI `capabilities/prepare/export` | 現行 CLI + v1 Schema + headless tests | 命令／schema／明確拒絕的行為已存在 | 任一外部製造功能已開通 |
| WHD/CADSplit `ae_engine` 雙 Repo | `contracts.py` 相同 blob，但 `manufacturing_api.py` 不同；CADSplit `AGENTS` 記舊 WHD SHA | 不同版可能有不同 API 清單；各版依自身入口與已認證 scope 運作 | 必須鎖版／同步升級，或假設同名 API／同輸入必定產生相同 DXF |

**#2517 工單狀態：** 2026-11-01 查核時仍為 `OPEN`；不能依已合併的單一子工作或 Feature catalog 數量將整單視為完成。 [WHD Issue #2517](https://github.com/looaeedr/whd/issues/2517)

### 7.1 #2517 增量接線與舊版相容驗證（依使用者確認的演進方式）

1. **新增 Family／既有操作先不新增公開入口**：在 `cabinet_types/` 註冊／擴充 Family Policy／Topology，重用適用的既有公開 Engine API（一般單板件 `generate_part`；組合／批次／NFB 依原有相應入口）；只有原契約真的無法表達的新操作才擴充公開函式及必要 immutable DTO。已註冊 Family 不自動通過製造資格檢查。
2. 共用**對應操作的 API 契約**服務金庫型與已實作的新 Family，Family／Part／Operation／來源由 Engine 核實；新增操作只由需要它的 WHD GUI／CADSplit caller 使用，舊 caller 不需依賴該新入口，也不能假設同一名稱的跨版 DXF 完全等價。
3. **先跑舊金庫型（Vault）正反回歸，再跑受電箱新增 Family 分支**：同 API 下驗箱型選擇、request 結果、2D/3D、DXF Save→Reload 與拒絕情境；新增獨立 API 時另驗簽章、缺席時舊行為不受影響。
4. **保留既有 Door／EndCap 自動呼叫，以及 Receiving 的條件式 API Adapter；Receiving 從原始 DXF 自動建立完整製造輸入的流程尚待完成及驗證。** 正式目標是自動取得合法的原圖、專案狀態及 Engine 資源，不把人工選 JSON／基準目錄當正常前置；缺必要機械資料則精確拒絕，不在 CADSplit 發明公式。
5. **API 成功回傳不等於製造驗收成功**：依實際 exporter 區分原子輸出、暫存檔 Save→Reload、提交前／提交後幾何驗證、可回復性與人工 UAT；不得以生成 DXF 檔案路徑或 `PartExportResult` 即宣稱幾何驗收。若未來真的需要跨程序操作，再決定新 transport／operation；目前 source-only CLI 不因此解鎖製造。

**不得新增**「Engine SHA 相同才可用」、「CADSplit 一律需升級到最新版」、「缺少新 capability 則整個系統停用」等全域鎖版檢查；這不免除**每筆正式加工的 Engine／Registry／baseline／原圖／輸出證據與幾何驗證**。本節不另建 Issue、SOP 或發版流程。

## 8. 未來外部 API 真正放行的必要條件（驗收契約，不指定退役 transport）

以下是「當 CADSplit 消費現有共用 WHD Engine API 的新 Family 能力，或增加真正的新操作（若未來跨程序亦同）」需要的**單功能／單 Family／單操作**驗收要求；**不要求 CADSplit、WHD GUI 與 WHD Engine 鎖定同一 commit 或同步升級**。這不是現行全部已實作，也不授權恢復安裝版 EXE。

1. **唯一 Engine owner：** 外部 adapter 僅傳輸 immutable operator/source request，呼叫同一 WHD `manufacturing_api`；所有 Family、Fold、Relief、Joint、孔位、CUTTING/BEND 在 WHD Engine。
2. **Family 擴充與能力分流：** 既有 Engine API 先查 Family Registry／Policy；針對該版存在的 Family、part kind、operation、`PART_ONLY`/complete assembly、來源與 blocked code 分別驗證。新 Family 缺能力，只拒絕該新情境，不破壞金庫型既有路徑。
3. **全自動完整可信請求：** CADSplit 從原始 DXF／`finalized info_data`／現有專案持久化設定自動取得 Family、`W/H/D/T`、來源 Feature、來源 Set／Bay 標籤／穩定來源鍵及關聯、來源 SHA／handle／revision；由 Engine 依 canonical state／Family／Topology 決定正式製造實體身份、Set／Bay 映射與必要板件，再透過既有 policy／resource discovery 取得合法 baseline／Factory Policy、Fold／Corner／Topology 與 immutable request digest。不依賴常態人工挑選受電箱 JSON、基準目錄；原圖缺必要參數時需精確報缺，不接受猜測 default、未授權 transform 或假來源 JSON。
4. **準備／輸出分界（若未來 transport 採 prepare/export）：** prepare 回傳 Engine-derived frame／policy 並綁定**同一筆請求及必要來源／規則修訂**；export 重驗相應來源、Feature、token／fingerprint，僅拒絕該筆資料失效操作。這不是要求所有客戶同版，不暗示當前 CLI 已可出圖。
5. **製造與交易（目標驗收，不宣稱所有 exporter 已符合）：** 依各路徑真實支援的操作，由 Engine 產生 canonical physical part／FinalScene；需要正式製造放行的路徑須以可信暫存輸出、**提交前** Save→Reload 重開、幾何／實體清單比對及可明確判定的提交或回滾完成。**現行 `generate_part` 一般單板件只保證 temp → `os.replace` 原子替換，沒有在此函式內統一於替換前做 DXF 重開幾何驗證；CADSplit Receiving Bridge 則先 batch save 再做 post-commit verification。** 不能把兩條路徑誤稱為相同的已驗收交易保證。
6. **實體與數量：** 金庫型／受電箱、單／雙／多層、Set/Bay、2／3 片 BoxBody、內門、底板、封頭尾、Divider、NFB／EAR／PAD、數量 Q 必須逐功能確認實體身份與必要來源；未認證項目明確 blocked。
7. **API 不可逆向：** WHD Engine 不得 import CADSplit 或 GUI；CADSplit 不得透過深層 helper／原始 `ae.export_*` 重製製造結果；缺 API 補 Engine，不在 CADSplit 寫 workaround。
8. **實證（依 exporter 分別列證據）：** 定向 RED→GREEN、負向／錯誤碼、是否僅完成檔案原子替換、Save→Reload 發生於提交前或提交後、重開與 canonical FinalScene 的幾何／工藝層／實體身份比對、來源漂移、已存在輸出不被誤蓋、批次失敗是否確保回滾、實際 2D/3D/DXF 同源，再由 GitHub PR exact SHA 必要 CI 判定。**API 回傳成功／DXF 可開啟／Mock PASS 均不得替代正式製造驗收。** 沒跑過不能寫 GREEN。
9. **權威更新：** 新對外 transport 的正式決定要先同步 AI 庫 04／09 Authority Map／AGENTS／契約與測試；不能只修改 `HEADLESS_API.md` 或某份草案就宣稱 CURRENT。
10. **舊入口持續相容，但單次結果可追溯：** 針對已公開函式保留合法簽章／DTO／錯誤語意並跑回歸；新入口只在具備該 API 的 Engine 使用。每筆正式製造保留實際 Engine／Registry／Family Policy／baseline／原圖／輸出指紋與驗收證據；**不要求消費端同 SHA，但不保證不同版同輸入產生相同 DXF**。
11. **fallback 與覆寫：** 只有在該 Family／Part 已存在 CURRENT 授權且已測的公式出圖能力時，才允許缺 baseline 改走公式；缺基準但本來就應依基準加工的情境必須拒絕。輸出檔存在、舊輸出版本不符或 Save→Reload 失敗時，不得默默覆寫並宣告成功。

## 9. 失敗處理與禁止 fallback

| 條件 | 正確反應 |
|---|---|
| `capabilities` 未宣告製造能力 | CADSplit 阻擋對外製造，不呼叫 export 假裝成功 |
| 現行 source-only `prepare/export` 回 `WHD_OPERATION_NOT_IMPLEMENTED` | 保持 failed，`manufacturing_verified=false`，不得建立成功清單或 DXF |
| Missing Family／physical identity／Fold／必要 Registry source | 明確 unsupported/error；即使 Family 已註冊或 PartSpec 可產生，也不能繞過製造資格；不可用畫面猜幾何 |
| 缺少**必需**基準檔，或無法證明當前 Family／Part 有正式公式製造能力 | 明確拒絕該 operation；不可因 exporter 有 fallback 就宣告已認證 |
| 缺 baseline，但該 Part 明確允許且已測公式製造 | **僅在已核准 scope** 經 Engine 公式路徑、來源與實際 DXF 驗證後可處理；須記錄 `used_baseline=false` 等證據，不一概拒絕 |
| Registry HIT 且 3D shadow 顯示衝突 | 診斷並走認證規則處理，不用 shadow 重寫已認證 formula |
| Registry MISS／Provisional | 可做 discovery／candidate，但不得直接正式 CUTTING／DXF 放行 |
| 原圖／CSV／Set/Bay／該操作所依賴的來源指紋或製造規則變動 | 僅受影響操作的舊驗證失效，重新驗證；與其他獨立舊 API 無關 |
| `PART_ONLY` 成功但其他實體未驗 | 僅宣告指定實體片的成功，不宣告整箱 |
| API 回傳出圖路徑或 `PartExportResult`，但未執行獨立 DXF 重開驗證 | 只能宣稱輸出路徑／函式成功，**不可**宣稱已通過正式幾何製造驗收；依該 exporter 記錄已實行的驗證層級 |
| DXF save/reopen／數量／幾何驗證失敗 | 不視為製造成功；若驗證在提交後才進行，必須如實標示「已產生檔案但未通過驗收」，不得假稱已回滾或用 preview 代替 |
| 已存在正式輸出檔、來源 digest 不同、或 caller 提供 `overwrite=True` | 預設**建議**先拒絕或隔離 staging；僅當現有 CURRENT 製造交易規則明確授權覆寫、完成驗證與可回復性保障時才提交，不能把 caller 的旗標當作製造放行 |
| Engine 版本不同，但既有 API 仍在且相關來源有效 | **沿用該版既有合法 API 與原範圍驗證**；記錄實際 Engine／Registry／baseline／來源版本，不能未經比對就聲明 DXF 跨版等價 |
| 客戶要求該版未提供的新 API | 僅該新操作 unavailable／unsupported；既有 API 不受影響 |
| 某一操作的 Registry／baseline 或請求來源驗證失敗 | 僅該操作 fail closed；不得把製造資料不合格誤寫成全系統版本不相容 |

**現有程式與建議政策不可混為一談：** CADSplit `modules/automatic_door_bridge.py` 使用 `ManufacturingContext(overwrite=True)`，缺門 baseline 時仍可走現行公式門路徑；WHD `tests/test_manufacturing_api.py` 也測到缺門 baseline 的 `generate_part()` formula dispatch。這些是 **CURRENT IMPLEMENTATION／CURRENT TEST**，不是該來源已通過正式幾何驗收的產品認證。

**各 exporter 的實證分層（`CURRENT IMPLEMENTATION`）：**

| 入口 | 目前在程式中可確認的行為 | 不能自動宣稱 |
|---|---|---|
| `generate_part()` 一般單板件 | exporter 寫到同目錄暫存檔；函式成功則 `os.replace()` 到目的路徑，回 `PartExportResult`；失敗嘗試清掉暫存檔 | 函式內已統一完成 Save→Reload 幾何驗證或同版／跨版 DXF 等價；驗收須按特定 exporter、基準檔與來源另取證 |
| `save_resolved_manufacturing_geometry_batch_dxf()` | Engine 先做現有 source／NFB guard，經 `_save_resolved_rows_atomic` staging 後提交；只有特定 `verified_nfb_parts`、paired door 或 `verify_all_staged` 被啟用時才會於 staging 階段做相應幾何重開檢查 | 所有批次板件均一律在提交前完整重開幾何驗證 |
| CADSplit `export_receiving_resolved_bays()` | 先呼叫上項 batch save，之後再呼叫 Engine `verify_saved_resolved_manufacturing_geometry_batch_dxf()`；後驗證若 `ok=False` 則回錯 | 發生 post-commit 驗證錯誤時已自動回滾；或未經完整上游可信輸入就已完成 Receiving 全自動製造 |
| `save_verified_final_scene_batch_dxf()` | 已提供需 `pre_commit_guard` 且 `verify_all_staged=True` 的獨立 staged Save→Reload 公開函式／內部 W-04 foundation | CADSplit 已經改接此交易入口、外部 Worker 具正式製造 capability 或所有場景已獲放行 |

**修正方向（`PROPOSAL`）：** 對具正式加工範圍的流程，先確認 Engine 既有的正確驗收入口和交易能力，再補最小改動，使成功狀態只在**該範圍**幾何驗收通過後成立；不要以修改文件或例外 catcher 假裝恢復失敗前檔案。`overwrite=True` 的存在亦非授權可覆蓋正式客戶檔案的證據。

## 10. 測試、硬閘門與交付邊界

- **所有 GUI／Engine 修改：** 依 `AGENTS.md` 與 AI 庫 04 的 `GUI_ENGINE_API_OWNERSHIP_HARD_GATE_V1`；現行 workflow：`.github/workflows/whd-gui-engine-api-boundary.yml`；相關治理測試：`tests/governance/test_gui_engine_api_boundary_gate.py`。此靜態檢查阻擋偵測到的**新增**越界，不足以保證全程式無舊債。
- **Headless 製造 API：** `tests/test_manufacturing_api.py`、`tests/test_manufacturing_api_finished_face_contract.py`、`tests/test_resolved_manufacturing_export.py` 等；需真實 source／baseline／DXF 檢查，不能只靠 mock。
- **source-only CLI：** `tests/test_issue2377_cadsplit_headless_cli.py` 與 `tests/test_installed_worker_exe_wiring_retired.py`；證明關閉製造／退役路徑的拒絕契約，**不是**對外 DXF 成功證明。
- **CADSplit 內嵌橋接：** `tests/test_automatic_manufacturing_api_boundary.py`、`tests/test_receiving_api_bridge.py`；mock 路由證據不能自動證明 WHD 跨程序製造放行。應新增**從原始 DXF／正式資料自動建立 Receiving source 與可信資源根目錄**的真實整合用例，確認常態流程不彈人工 JSON／基準目錄選取；缺資料 fail closed。
- **產品回歸：** 真正修改產品路徑時遵守 `.github/workflows/whd-product-regression.yml` 與 exact HEAD CI；已通過的舊 SHA 不可冒充新版本成功。
- **新增入口／舊版相容回歸（尚未宣稱已建立 CI）：** 新 Family 在既有**適用** API 下的正反測試、未支援 Family／Part／Operation 的拒絕測試、真正新操作的有／無測試、舊 caller 繼續正常；需要時核對 Registry／baseline，並就各 exporter 記錄正式 DXF 幾何驗證時間點、覆寫／rollback、原圖來源、實際 Engine／Registry／baseline 版本。**禁止測試要求兩 Repo 相同 SHA，也不能反向假設跨版 DXF 一定等價。**
- **Family / #2638 型號 API：** `tests/test_issue2517_shared_cabinet_model_choices_engine_api.py` 只驗 read-only 型號 selector；**不能替代金庫型既有出圖回歸、新增受電箱同 API 出圖回歸**，亦不能證明 `cabinet_types` 製造分派完整。
- **開發與正式分支：** WHD 日常施工權威為 GitHub `localX`；PR 合入 `localX` 不等於 Windows `Z:\localX` 已同步，也不等於正式 `X=cleanup/2d-3d-sync` 已發布；後者必須有當次 `/推推` 授權及正式 gate。

## 11. 已辨認的文檔矛盾與本次消歧

| 原先容易誤解的說法 | 本次正確解讀 |
|---|---|
| AI 庫 04 稱 `integration_cli` 是「已授權外部 seam」 | **已在 PR #2637 修正**：只有 source-only wire；沒有已驗證的外部製造 seam |
| `HEADLESS_API.md` 有「拆圖端直接用 `ae_engine`」等舊路徑 | REFERENCE／內嵌 Python 接線描述，不代表現行 WHD 跨程序對外 API 已完成 |
| CADSplit「AE Core 只有 `ae_engine/` 一份」 | **指 CADSplit repo 內的模組組織**，不等於兩個獨立程式共同調用 WHD 最新唯一 runtime；製造規則權威仍在 WHD |
| `request_v1_1` 列大量箱型與 feature kind | Schema enum 是接收資料型別，不代表 runtime capability；安裝版歷史路徑退役 |
| `PART_ONLY` 或 GUI Preview 可畫出 NFB／EAR／PAD | 只有明示 scope 的 verified output 才可宣稱成功；read-only render 不等於已批准製造 |
| #2517 有大量公開 API | 逐項 Engine 遷移不等於全產品全情境已完成；Issue 本身仍 OPEN |
| #2638 主 GUI 型號選項已使用 Engine API | `list_cabinet_model_choices()` 是 read-only selector，移動的是原 GUI 清單邏輯，**不是新的製造入口**；其中特殊處理金庫型基準檔的規則尚應走既有 Family policy，不能因此跳過製造回歸 |
| CADSplit `AGENTS.md` 記較舊 WHD SHA，兩個 Repo 都有 `ae_engine` | 各版本 API 集合可以不同；SHA 不作全部功能的全域鎖，但每筆製造仍須追溯實際 Engine／Registry／baseline／原圖版本；跨版同輸入不保證同 DXF |
| CADSplit door bridge `overwrite=True`、缺 baseline 時公式門 | 屬現有 caller 行為；何時允許公式或覆寫須由 Engine CURRENT 與真實 DXF 測試證明；`generate_part` 成功不等於提交前 DXF 已重開驗證 |
| CADSplit GUI 要人工選受電箱 JSON／基準檔目錄 | 使用者回報屬現況與體驗阻礙；正式目標是由原圖、已確認專案資料與 Engine 資源／Family 規則自動完成上游製造輸入；尚未驗收落地，不把人工檔案選取當正式設計 |
| AI 庫 09 的部分整合／治理文字仍寫舊 DC／直接 X 路由 | 與目前 `AGENTS.md` 的 `GITHUB_LOCALX_FIRST`、治理先 `localX` 有可見落差；本 REFERENCE 只記錄 `OPEN` 文檔校正，不擅自重定 CURRENT 流程 |

既有文檔矛盾修正來源：[PR #2637](https://github.com/looaeedr/whd/pull/2637)，已合併到 `localX`，commit [`a7fa73a2e12f`](https://github.com/looaeedr/whd/commit/a7fa73a2e12fcbe5020e4685375ea2e3f958e60c)。新增型號 API：[PR #2638](https://github.com/looaeedr/whd/pull/2638)，合併 commit [`eb6cd16bc4c9`](https://github.com/looaeedr/whd/commit/eb6cd16bc4c9c595e4330429585e505c24bd8631)。兩 PR 都不是全功能製造放行。

## 12. 非範圍與未決事項

- **不在本文**重新定義任何 Corner/Relief 參數公式、成品／料尺寸換算、加工座標補償或 fixture expected；這些各自有 CURRENT／Certified owner。
- **不規定固定版本或鎖版交付。** 未決事項僅限將來採 Python package、受控 source dependency、RPC、HTTP、JSON/CLI 等**傳輸與交付形式**；既有製造 API 不因新 Family 重複增開、真正新操作才增加入口；舊版無需為了未使用的新功能升版。已退役的安裝版 Worker／EXE 不可未經新決策恢復。
- **不在本文**宣布 CADSplit 已放棄舊副本或已完成外部遷移；要以實際 CADSplit repository 的接線及回歸為準。
- **未完成事項：** #2517 的所有功能、全箱型與每個實體板件對 GUI 公開 API 的覆蓋仍需逐個證實；**CADSplit Receiving 從原始 DXF／既有專案狀態自動建立完整可信製造輸入、無常態人工 JSON／baseline root 選取**仍待落地及驗收；各 exporter 正式 DXF 幾何驗收、單次 Engine／Registry／baseline／原圖版本追溯、外部 transport（若有需求）需逐項證實；**不以官方固定版本部署為前置**。
- **待原 CURRENT 文件校正：** AI 庫 09 部分整合／治理敘述與 `AGENTS.md` 已有版本差異；須沿既有 owner 修改原檔並跑治理測試，而非讓本 REFERENCE 宣稱已修正。
- **未證實：** 新增入口的完整向後相容回歸、座標 transform 共用契約或覆寫安全修復已在程式落地；本文區分使用者已確認的演進規則與尚待實作／驗證的程式狀態。
- **未經證實：** Windows `Z:\localX` 是否更新、現場 UAT／實際機器切割是否通過；本文只引用指定 GitHub commit 的程式與文件狀態。

## 12.1 盤名與多實體單檔 DXF 消費端查核（#2689–#2694；CURRENT 程式功能）

> 此節是 **REFERENCE 使用說明**，CURRENT 製造／資料權威仍是 AI 庫 04、現行 Engine 原始碼和 Certified Registry；不得把一般 DXF 檔成功寫出宣稱為 Receiving 全箱 MFG-2/NC 工廠放行。

WHD GUI 不計算製造板材，也不為金庫型重造第二個引擎。單箱與 Receiving Bay 共用 Engine 製造展開；Bay `panel_name`、全工程 `next_panel_number` 會在專案 Save→Reload 中保存，但盤名與 canonical physical `stable_id`、實體展開來源完全分離。Receiving 名稱經 `manufacturing_api.rename_receiving_panel`、Vault 名稱經 `manufacturing_api.set_cabinet_panel_name`；非法路徑或重名由 Engine 拒絕。

對 Receiving 多連 Set/Bay，消費端選取 `PER_SET`、`ALL` 或 `END_VS_MIDDLE`，可先呼叫 `manufacturing_api.plan_receiving_grouped_dxf(layout, mode)` 取得 **Engine 唯一**群組檔名及成員；首末連是各套首末 **Bay**，而不是頭尾封板。正式來源驗證及輸出走 `manufacturing_api.export_grouped_receiving_multibay_dxf`，需提供當前實體 Bay FinalScene resolver 與 pre-commit source guard。舊逐板件的 export API 持續存在，未因新增模式被封鎖。

對金庫型單箱，無盤名時 `manufacturing_api.vault_panel_dxf_filename("", at=<具時區 datetime>)` 得到台北時間 `金庫型_YYYYMMDD_HHMMSS.dxf`，有盤名回傳 `<盤名>.dxf`。實際多實體合併出圖走 `manufacturing_api.save_composed_panel_dxf(((panel_name, resolved_geometry),), path, pre_commit_guard=...)`，不是把 GUI 幾何拼貼成一張圖；同名既有 DXF 須提示確認覆寫。

驗收區別：`PartRenderData` 的每片 flat UV、材料、CUTTING／BEND／MARKING／BLIND_HOLE／CHECK 要獨立 Save→Reload，合併的單檔 DXF 再獨立回讀各片圖元、來源與不重疊排列；來源缺失／漂移／PAD-EAR-NFB 未認證／批次提交失敗都 fail-closed。受電箱完整 MFG-2/NC、外部 CADSplit 生產輸入串接仍需各自現行 Gate 放行，**這批 #2689–#2694 不是全部製造能力已核准的聲明**。

## 13. 證據索引（可開啟）

### WHD CURRENT

- [AGENTS.md](https://github.com/looaeedr/whd/blob/localX/AGENTS.md)
- [AI 庫 04：製造引擎規範](https://github.com/looaeedr/whd/blob/localX/個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md)
- [AI 庫 07：尺寸與 STANDARD 語意](https://github.com/looaeedr/whd/blob/localX/個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md)
- [AI 庫 09：權威地圖](https://github.com/looaeedr/whd/blob/localX/個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md)
- [ae_engine/contracts.py](https://github.com/looaeedr/whd/blob/localX/ae_engine/contracts.py) · [ae_engine/manufacturing_api.py](https://github.com/looaeedr/whd/blob/localX/ae_engine/manufacturing_api.py) · [ae_engine/__init__.py](https://github.com/looaeedr/whd/blob/localX/ae_engine/__init__.py)
- [#2517 主工作單](https://github.com/looaeedr/whd/issues/2517) · [#2637 架構 seam 文檔修正](https://github.com/looaeedr/whd/pull/2637) · [#2638 型號清單引擎入口](https://github.com/looaeedr/whd/pull/2638) · [cabinet_model_choices.py](https://github.com/looaeedr/whd/blob/localX/ae_engine/cabinet_model_choices.py)
- [Certified Relief Registry 資料](https://github.com/looaeedr/whd/tree/localX/基準檔/截角資料庫)

### WHD API 與 CLI REFERENCE

- [HEADLESS_API.md](https://github.com/looaeedr/whd/blob/localX/HEADLESS_API.md)
- [CADSplit_WHD_Contract.md](https://github.com/looaeedr/whd/blob/localX/docs/integrations/CADSplit_WHD_Contract.md)
- [integration_cli/README.md](https://github.com/looaeedr/whd/blob/localX/integration_cli/README.md)
- [v1 request](https://github.com/looaeedr/whd/blob/localX/integration_cli/schemas/request_v1.schema.json) · [v1 response](https://github.com/looaeedr/whd/blob/localX/integration_cli/schemas/response_v1.schema.json) · [v1 capabilities](https://github.com/looaeedr/whd/blob/localX/integration_cli/schemas/capabilities_v1.schema.json)

### CADSplit 現行程式

- [automatic_door_bridge.py](https://github.com/looaeedr/CADSplit/blob/main/modules/automatic_door_bridge.py)
- [automatic_endcap_bridge.py](https://github.com/looaeedr/CADSplit/blob/main/modules/automatic_endcap_bridge.py)
- [receiving_api_bridge.py](https://github.com/looaeedr/CADSplit/blob/main/modules/receiving_api_bridge.py)
- [整合出圖合併注意事項.MD](https://github.com/looaeedr/CADSplit/blob/main/整合出圖合併注意事項.MD)
- [CADSplit AGENTS.md](https://github.com/looaeedr/CADSplit/blob/main/AGENTS.md) · [CADSplit ae_engine/manufacturing_api.py](https://github.com/looaeedr/CADSplit/blob/main/ae_engine/manufacturing_api.py) · [WHD API 正反測試](https://github.com/looaeedr/whd/blob/localX/tests/test_manufacturing_api.py) · [CADSplit bridge 測試](https://github.com/looaeedr/CADSplit/blob/main/tests/test_automatic_manufacturing_api_boundary.py)

---

**文件維護原則：** 本文件是**現行權威的單一閱讀入口／整合參考**，不是另一份製造規格。收錄於 WHD repository 後仍保留 `REFERENCE` 角色和 `whd_canonical` 指向 04；「Family 優先擴充、重用適用的共用 Engine API、CADSplit 常態全自動取得可信製造輸入、舊版按自身能力照用而每筆結果可追溯、正式 DXF 應有明確幾何驗收」的規範需在實作時對齊既有 CURRENT AI 庫 04／相關測試，不建立第二份 CURRENT。**v5.1 本次僅加入 REFERENCE 文件；未修改 Engine、CADSplit GUI 或 CI，亦不聲稱已完成全自動出圖、金庫型／受電箱實際功能修復或 Windows 現場驗收。**
