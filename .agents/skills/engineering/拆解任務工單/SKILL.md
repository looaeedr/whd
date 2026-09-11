---
name: 拆解任務工單
description: 將已確認的 plan/spec/issue/conversation 拆成可實作工單。必須先以可執行 requirement-level RED 證明需求、取得使用者核准，再依 root contract 切票；WHD 工單還要帶 Requirement Authority、AI Library traceability、GitHub owning Issue 與 closing ownership。
disable-model-invocation: true
---

# 拆解任務工單

把**已核准需求**拆成窄而完整的 tracer-bullet tickets，blocking edge 由證據決定，而不是先猜架構再補測試。

## Iron Rule

```text
NO TICKET BREAKDOWN BEFORE APPROVED REQUIREMENT-LEVEL RED EVIDENCE
```

Requirement RED 不是形式。它用來判定多個症狀是否其實共享同一 root contract，或一個需求是否包含可獨立驗收的不同 contract。

## 1. Gather context

先讀目前對話、spec/issue、相關 comments、project glossary/ADR、**相關 `個人AI檔案庫/**`** 與 existing code paths。此階段只收 Requirements，不先分 T-number/title/blocker。

### AI Library traceability gate

WHD/project work 的 AI Library 是工程 evidence source：

- RED 設計前搜尋/讀取相關 `個人AI檔案庫/**`，記錄精確路徑。
- 建立 `Requirement Authority`，區分 current user-approved requirement、code/test behavior、AI Library historical guidance。
- current explicit user-approved requirement 高於 stale/conflicting AI Library。
- 發現 durable conflict/pitfall/invariant 時標 `AI Library Writeback: REQUIRED` 並指定 target path/category。

## 2. Explore the codebase

追 current public seams，找每個 Requirement 可被真實觀察的位置。優先 existing tests/public APIs；沒有可執行 seam 才加最小 test/probe。

RED 核准前允許的變更只有 requirement RED test/probe 與 evidence；不得先寫 production、ticket 或 tracker issue。

## 3. RED Gate

建立 requirement matrix：

| RED ID | Requirement | RED command/nodeid | expected failure | observed failure | interpretation | user decision |
|---|---|---|---|---|---|---|

每個 Requirement：

1. 寫或找到 executable RED。
2. **實際執行** exact command/nodeid。
3. 確認 failure 真的到 intended behavior seam。
4. 記錄 expected/observed failure，足以區分 requirement violation 與 harness noise。
5. 與使用者逐條論證 RED 是否真的代表需求、是否共享 root contract、是否測錯 seam。
6. 每個 relevant RED 都要有使用者核准。

下列不能算 requirement RED：environment/DISPLAY/Xvfb/network/tooling failure、syntax/import/collection error、broken fixture/mock、只有 timeout、missing test path。

若 supposed RED 已 GREEN，不得硬建修復票；先重新確認 seam/current implementation/症狀是否屬另一條 path。

### Fail closed before RED approval

RED 未核准時：

- 不得拆票或 assign T-numbers/titles/blockers；
- 不得建立 GitHub/Linear issue；
- 不得寫 `.scratch/**` local ticket；
- 不得讓 `派工` 轉移至實作者。

## 4. Draft vertical slices

RED 全部核准後，才按 evidence 切票：

- same root contract + inseparable implementation/verification 通常同票；
- independent contract + separate GREEN condition 分票；
- 每票能在 fresh context 完成；
- wide mechanical refactor 可用 expand–migrate–contract；
- 每票列 `Approved RED IDs`、`Requirement Authority`、`AI Library References`、`AI Library Writeback`、`Blocked by`、deliverable、acceptance criteria；
- stale AI Library 被 current requirement 推翻時，至少一張 closing/acceptance ticket 必須擁有 REQUIRED writeback。

## 5. 使用者第二次核准

把 proposed breakdown 逐票呈現：Title、Approved RED IDs、Requirement Authority、AI Library References、AI Library Writeback、Blocked by、What it delivers。

使用者確認 granularity/root-contract grouping/blocking edge 後才算 breakdown 核准。這是**第二個 gate**，與 RED 核准分開。

## 6. Publish tickets

只發布已核准 breakdown：

- Local-only tracker → `.scratch/<feature>/issues/<NN>-<slug>.md`。
- GitHub/其他 real tracker → blockers first，一票一 issue，能用 native blocking/sub-issue relation 就使用。

不要自行 close/修改 parent issue。

### GitHub owning Issue publication gate

GitHub-backed project 的 approved ticket **必須先有 real GitHub owning Issue 且已反讀，才算可派工**：

1. blockers first 建立每張 Issue。
2. 依工具真 schema 取得 `issue_number` + canonical URL，不猜欄位。
3. 反讀 created Issue，核對 title/body/dependencies。
4. 將 Issue number/URL 寫入 dispatch state/journal。
5. 然後才可讓 `.agents/skills/engineering/派工/SKILL.md` 進 Implementer。

`.scratch/**`、chat T-number、branch、commit、QA workflow、checkpoint ZIP 都不是 owning Issue。

若工作已開始才發現漏 Issue，立即建立並明標 **Retroactive provenance / created after work started**，帶實際 branch/commit/run evidence；不得 backdate 或假裝 Issue 原本就存在。

## Ticket Template

```markdown
# <NN>: <Ticket title>

**What to build:** user-visible/end-to-end behavior.
**Approved RED IDs:** R1, R2
**Requirement Authority:** current user-approved spec / issue / exact contract.
**AI Library References:** exact `個人AI檔案庫/**` paths used.
**AI Library Writeback:** exact path(s) + intended update, or `None — no durable knowledge change` + reason.
**Blocked by:** None, or exact blocking tickets.
**Status:** ready-for-agent

- [ ] Acceptance criterion 1
- [ ] Acceptance criterion 2
```

## Deep-module closing ownership

若來源是 `掃描深模組`：

- 每張施工票仍需 GitHub owning Issue；
- 至少一張 closing/acceptance ticket 是 **AI Library Writeback owner**；
- 至少一張是 **Combined Acceptance owner**，負責跨票 regression、source ownership scan、config invariant、remote QA、cleanup、drift audit、integration evidence；
- 兩個 owner 可同票，但不可寫成模糊的「大家負責」。

## Red Flags

- 「spec 很清楚，先拆再補 RED」→ 不行，先跑 RED。
- 「test error 就算 RED」→ harness failure 不是 requirement evidence。
- 「RED 已綠但還是建 bug ticket」→ 先找對 seam。
- 「先建 draft Issue 再等核准」→ 建 issue 就是發布，兩個 approval gate 前 fail closed。
- 「AI Library 以前說 X，所以蓋過使用者新規格」→ authority 順序錯；記 conflict 並 REQUIRED writeback。
- 「有 `.scratch` ticket 就能派工」→ GitHub-backed project 必須 real owning Issue。
