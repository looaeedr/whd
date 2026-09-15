---
whd_doc_role: REFERENCE
whd_contract: ai-library-reference
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 個人 AI 檔案庫

本 README 是 **AI Library 的導覽入口**，不是 WHD production、幾何、UI、release、remote QA 或 executable process 的 CURRENT authority。

AI Library 的用途是保存長期背景、協作偏好、專案 SOP、canonical authority 導覽，以及事故／踩坑 REFERENCE。任何規則若已有 CURRENT owner，README 只指向該 owner，不複製第二份 current prose。

## 目錄導航

目前頂層結構：

```text
個人AI檔案庫/
├── README.md
├── 第一層_核心檔案/
├── 第二層_專案與SOP/
└── 踩坑庫/
```

### 第一層_核心檔案

- `01_個人背景與身份.md`：長期背景與角色資訊。
- `02_溝通風格與輸出偏好.md`：溝通與輸出偏好。
- `03_核心目標與近期重點.md`：核心目標與近期重點。
- `04_全域AI協作規則.md`：跨任務 AI 協作 REFERENCE；不擁有 executable/process/domain CURRENT authority。
- `05_反饋學習與自我演化機制.md`：反饋與知識沉澱機制。

### 第二層_專案與SOP

主要入口包含：

- `01_DXF與CAD自動化全域規範.md`
- `02_通用任務SOP模板.md`
- `03_常用Prompt指令庫.md`
- `04_WHD鈑金展開幾何引擎規範.md`
- `05_CAD批次拆圖與特徵萃取規範.md`
- `06_踩坑記錄與防錯經驗庫.md`
- `07_Phase6尺寸語意與標準截角母規則.md`
- `07_WHD技能發現與掃描深模組規則.md`
- `08_WHD截角資料與2D入口收斂規則.md`
- `08_WHD技能建立與修改規則.md`
- `09_WHD_Canonical_Authority_Map.md`

第二層也可能包含日期化 verification、專案交接或其他 REFERENCE 文件；**檔名看起來較新不代表它是 CURRENT owner**。

### 踩坑庫

`踩坑庫/` 保存事故、反例、踩坑與復原經驗。這些資料可協助診斷與避免重犯，但不得因內容較詳細就覆蓋 CURRENT spec、Skill、registry 或 executable authority。

## Authority 規則

唯一的 canonical authority 導覽入口是：

`個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md`

使用順序固定為：

```text
先找 Authority Map
→ 找到該 contract 的 CURRENT owner
→ 讀 CURRENT owner
→ 再用 REFERENCE / pitfall / historical evidence 補充背景
```

角色語意：

- `CURRENT`：該 contract 唯一現行 owner。
- `REFERENCE`：背景、方法、事故或延伸說明；不得覆蓋 CURRENT。
- `MIRROR`：相容入口／導覽，只能 pointer 到 canonical owner。
- `HISTORICAL`：歷史證據，不得進 current routing。

若 README、REFERENCE 或歷史文件與 Authority Map 指向的 CURRENT owner 衝突，以 CURRENT owner 為準；不要在 README 裡再建立平行規格。

## 使用方式

開始 WHD 任務時：

1. 先依 `09_WHD_Canonical_Authority_Map.md` 找到 contract owner。
2. 若屬 startup / process routing，依 `AGENTS.md` 與 required Skill 執行。
3. 若屬 manufacturing / geometry / UI / DXF / persistence 等 domain 行為，讀 Authority Map 指向的 CURRENT owner，不從 README 猜規格。
4. 需要事故背景時再讀 `06_踩坑記錄與防錯經驗庫.md` 或 `踩坑庫/`。
5. 驗證結果只能判斷實作是否符合 authority，不能反過來成為 production 或文件真值來源。

一般原始碼與文件修改以 **Git branch / commit** 為主要 rollback authority，不為每個檔案自動建立額外實體備份。只有下列情況才另外建立實體備份：

- 使用者明確要求；
- Git 無法保存或還原的外部資產；
- 高風險二進位資產。

本 README 不保存日期型 UI 狀態、Assembly layout、EndCap positioning、release 細節或其他產品 CURRENT 規格；這些內容應由各自 CURRENT owner、REFERENCE/HISTORICAL 文件、verification、Git history 或 GitHub Issue 保存。
