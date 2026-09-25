---
whd_doc_role: CURRENT
whd_contract: spec-authoring-skill-gate
whd_canonical: ".agents/skills/engineering/寫成規格書/SKILL.md"
whd_schema: WHD_DOC_META_V1
---

# WHD 規格書 Skill 前置與 Grounding 規則

日期：2026-09-21  
狀態：CURRENT

## Problem Statement

WHD 已有 `AGENTS.md`、Phase6 Knowledge Preflight、`寫成規格書` Skill 與 AI Library 規則，但仍發生「知道 Skill 存在，卻沒有在本輪 fresh-read 就直接寫規格」的流程違規。

本次事故的直接原因不是缺少 Skill，而是執行者把**聊天記憶／先前回合已知內容**誤當成**本次 invocation 已讀取 canonical Skill**，因此跳過 mandatory pre-spec gate，先開始人工整理規格。這種行為會讓最新版 gate、required references、authority 分層與交付要求被漏掉。

本規則把「知道 ≠ 已讀」固化成 durable fail-closed contract。

## Confirmed Product Rules

本文件是 AI／工程流程規則，不新增任何板件、幾何、尺寸、placement、collision、DXF 或 manufacturing 產品規則。

使用者已明確要求：

1. 寫 WHD 規格書時必須真的讀 Skill，不能只靠聊天記憶。
2. 此規則必須寫進正式文檔與 AI Library，不能只在聊天中更正。
3. 使用者指出這類可重複錯誤後，必須做 durable writeback，避免下一個 Agent 再犯。

## Current State / RED Evidence

### Existing authority

- `AGENTS.md` 已要求 Skill invocation announcement 為第一個 user-visible 內容。
- `AGENTS.md` 已要求 Phase6 Knowledge Preflight、required Skills、required references 與 branch-first。
- `.agents/skills/engineering/寫成規格書/SKILL.md` 已要求 mandatory pre-spec gate：owning production code、AI Library/SOP、既有 spec/design note、tests，以及存在時的 fixture/baseline/certified data。
- `tools/phase6_skill_preflight.py` 會把全域踩坑庫列為永久 required reference。
- `.agents/skills/skill_registry.json` 已有 `explicit-skill-寫成規格書` route。
- `tests/test_skill_invocation_announcement_contract.py` 與 `tests/test_phase6_skill_preflight_gate.py` 已對公告與 Preflight 做 machine guard。

### Observed failure

在 2026-09-21 的「板件接合定位打標」規格精修中，執行者先人工修改 v1.3，之後才反讀 `寫成規格書/SKILL.md`。因此該輪不能視為符合 canonical Skill gate。

**RED invariant：**

> 只要在 fresh-read canonical Skill 與 required references 之前已開始產出／修改規格正文，即使後面補讀，也不得回溯宣稱該輪已符合 Skill gate。

## Solution

### SG-1 — 每次 invocation 都要 fresh-read

只要任務是建立、重寫、精修、更新、定稿或交付 WHD 工程／產品規格：

1. 第一個 user-visible 內容先依 `AGENTS.md` 公告：
   `使用「寫成規格書」技能。`
2. **本次 invocation 必須 fresh-read**
   `.agents/skills/engineering/寫成規格書/SKILL.md`。
3. 先執行 Phase6 Knowledge Preflight，取得 required Skills / required references。
4. 逐一讀完 required references，保留 `READ_REFERENCE: ...` evidence。
5. 再完成 Skill 的 mandatory pre-spec grounding。
6. 以上完成前不得開始 normative spec drafting。

聊天記憶、上一回合摘要、先前已讀過的 Skill、模型記憶或「我知道這個流程」**一律不能抵銷本次 fresh-read**。

### SG-2 — mandatory grounding 不得縮水

規格前至少交叉讀：

- owning production code / current behavior owner；
- 相關 AI Library / SOP；
- 同語意既有 spec / design note；
- current tests / regression contracts；
- 有則讀 fixture / baseline / certified data。

涉及 geometry、CAD、2D、3D、DXF、Fold、assembly、placement、collision、relief、dimensions 時，一律不可跳過。

### SG-3 — Evidence classification

規格中的重要事實必須維持：

- CONFIRMED PRODUCT RULE
- CURRENT IMPLEMENTATION
- CURRENT TEST ORACLE
- PROBE / DIAGNOSTIC VALUE
- HYPOTHESIS
- OPEN / UNRESOLVED

只有 CONFIRMED PRODUCT RULE 可直接成為 normative product behavior。

### SG-4 — 事後補讀不能洗白前段輸出

若先寫規格、後讀 Skill：

- 先前輸出標為 **NON-CANONICAL / PRE-GATE DRAFT**；
- 不得宣稱「現在補讀所以前面也算有用 Skill」；
- 必須依 fresh-read 後的 authority 重新檢查／重產規格；
- 若內容碰到 hypothesis、datum、tolerance、測試值或現況 implementation，必須重新分類。

### SG-5 — Durable writeback

若使用者指出一次可重複的 spec-authoring 流程錯誤：

- 同步正式 governance/spec 文檔；
- 同步 AI Library；
- 必要時同步全域踩坑庫；
- 有衝突舊說法時標示 SUPERSEDED / REVOKED；
- 最後從遠端反讀 marker 與正文，未反讀不得宣告完成。

### SG-6 — 最終 Markdown 交付硬閘門

只要 `寫成規格書` Skill 產出最終規格：

- 必須有實際 UTF-8 `.md` artifact；
- user-visible final 必須提供可下載連結；
- artifact 內容必須與最後定稿一致；
- 修改後未重產 artifact，不得宣告規格完成。

## User Stories

### US-1

身為使用者，我要求「寫規格書」時，不需要再提醒 AI 先讀 Skill；AI 會在本輪一開始自行 fresh-read canonical Skill。

### US-2

身為後續 Agent，我不能因聊天摘要已經告訴我 Skill 內容，就跳過 Preflight 與 required references。

### US-3

身為 reviewer，我可以從 durable 文檔判定某份規格是 canonical Skill 產物，還是 pre-gate draft。

## Implementation Decisions

1. canonical execution authority 仍是 `.agents/skills/engineering/寫成規格書/SKILL.md`；本文件不建立第二套 Skill。
2. 全域 bootstrap / announcement / branch-first authority 仍由 `AGENTS.md` 擁有。
3. machine routing 仍由 `.agents/skills/skill_registry.json` 與 `tools/phase6_skill_preflight.py` 擁有。
4. 本文件只補 durable process invariant：**per-invocation fresh-read 不可由聊天記憶取代**。
5. AI Library companion：`個人AI檔案庫/第二層_專案與SOP/12_WHD規格書Skill前置與Grounding規則.md`。

## Testing Decisions

現有 machine guards 已覆蓋：

- Skill invocation announcement；
- Phase6 Knowledge Preflight；
- required reference evidence；
- `寫成規格書` Registry route。

本次為 docs / AI Library durable correction，不修改 test suite。後續若要把「per-invocation fresh-read」做成可執行 runtime guard，應另開工程任務，不可用聊天文字假裝已具備 runtime enforcement。

## Out of Scope / Open Items

- 不修改 `寫成規格書/SKILL.md` 本體；其現有內容已明確要求 mandatory pre-spec gate。
- 不修改 `AGENTS.md`；目前全域 announcement、Preflight、durable writeback、branch-first 已存在。
- 不在本文件定義 marking、contact、L/C frame、tolerance 或 DXF 的產品規則。
- runtime 是否要新增「本輪 Skill fresh-read receipt」機器證據，留待獨立工程任務。

## Evidence / Traceability

本規則建立前已 fresh-read：

- `AGENTS.md`
- `.agents/skills/engineering/寫成規格書/SKILL.md`
- `.agents/skills/skill_registry.json`
- `tools/phase6_skill_preflight.py`
- `tests/test_skill_invocation_announcement_contract.py`
- `tests/test_phase6_skill_preflight_gate.py`
- `tests/test_writing_skill_preflight_route.py`
- `個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`
- `個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md`
- `個人AI檔案庫/第二層_專案與SOP/WHD_拷問前先讀程式_SourceFirst_20260911.md`

本輪 branch-first：

- target：`cleanup/2d-3d-sync`
- target HEAD：`26250add1a7c17e27cfce2f13f141ad44bf0f873`
- work branch：`docs/spec-authoring-skill-gate-20260921`
- branch parent 已遠端反讀為同一 SHA。

Preflight：

- REQUIRED SKILLS：`寫成規格書` ✓
- REQUIRED REFERENCES：`個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md` ✓
