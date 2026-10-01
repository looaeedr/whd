---
name: 拆解任務工單
description: 將已核准 spec/plan/issue/conversation 拆成可實作且可驗收的工單；若需求尚未核准，先用 requirement discovery / executable RED 釐清需求，再拆票。已核准規格不得被舊 RED-first 或第二次人工核准 gate 拉回去。
disable-model-invocation: true
whd_doc_role: CURRENT
whd_contract: approved-requirement-ticket-decomposition
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 拆解任務工單

把需求拆成窄而完整的 tracer-bullet tickets。核心原則是先判斷「需求是否已核准」，再選路徑；**requirement RED 不是所有拆票的通用前置硬閘門**。

## 1. Authority order

固定順序：

1. 使用者本輪明確指示與已核准規格。
2. current spec / issue / conversation 中已完成的需求決策。
3. CURRENT AI Library / project contract。
4. current code/test behavior，只用來找 implementation seam，不得覆蓋已核准產品需求。

若 current explicit requirement 與歷史 AI Library 衝突，以 current requirement 為準，並把 durable conflict 標成 AI Library Writeback。

## 2. Route selection

先判斷 `requirement_status`：

```text
APPROVED
UNAPPROVED
```

### APPROVED_REQUIREMENT_FAST_PATH

符合任一條件即可視為 APPROVED：

- 使用者明確說規格/需求已核准、定稿、照此施工；
- 同一對話中已逐條確認並完成 final spec，接著使用者要求「拆工單／拆票／拆成工單」；
- current owning issue/spec 已明確標示 accepted/approved 且沒有新的 unresolved product question。

已核准規格路徑固定：

```text
讀 approved requirement
→ 建 requirement-to-ticket matrix
→ 切 tracer-bullet tickets
→ machine validate closure ownership
→ blockers first 建 GitHub owning Issues
→ readback / dependency wiring
```

硬規則：

- **直接拆票**；不得重新要求 requirement-level RED。
- 不得把 implementation test 尚未存在，誤判成產品需求尚未核准。
- 不得再要求第二次核准才開始拆票或發布 Issue；使用者要求「拆工單」本身就是對已核准規格的 breakdown 執行指示。
- 不新增人工 approval gate。
- 每張票仍必須有 Acceptance Tests；這些 tests 是施工/驗收條件，不是回頭重審產品需求的 gate。
- 若拆票過程真的發現規格內部矛盾或 blocking product ambiguity，只把該具體矛盾升級為 `USER_INPUT_REQUIRED`；不得把整份已核准規格退回 discovery。

### REQUIREMENT_DISCOVERY_PATH

只有在**需求尚未核准**時才走此路徑，例如：

- 使用者只是描述症狀，尚未決定預期行為；
- spec 仍有互斥方案未選；
- 同一 requirement 在 current sources 中有真正 authority conflict。

此時 executable RED 用來回答「目前系統在哪個 seam 違反候選需求」，不是拆票儀式。

流程：

1. 建 requirement matrix。
2. 能用 existing public seam 就直接寫/找 executable RED。
3. 實際執行，確認是**正確失敗**，不是環境、syntax/import、broken fixture 或 missing-path noise。
4. 用 RED 與 authority evidence 協助使用者核准需求。
5. 使用者核准需求後，立即切回 `APPROVED_REQUIREMENT_FAST_PATH`。

**RED 只用來釐清未核准需求**；一旦 requirement approved，不得繼續用 RED approval 當 ticket publication gate。

若 supposed RED 已是 GREEN，先確認 seam/需求是否已實作；不得為了湊工單而捏造 repair ticket。

## 3. Gather context for breakdown

讀：

- approved spec / issue / current conversation；
- 相關 CURRENT AI Library；
- current code/test public seams；
- 既有 owner boundary / authority map（若會影響切票）。

建立 Requirement Authority mapping：

```text
Requirement ID → approved source → implementation seam → acceptance seam
```

對已核准 spec，優先直接引用其 R/T/section 編號，避免重新抄一套產品規則。

## 4. Draft vertical slices

按 evidence 切票：

- same root contract + inseparable implementation/verification → 同票；
- independent state/persistence/geometry/UI/export contract → 可分票；
- 每票都要能在 fresh context 完成；
- shared owner file 很重時，優先按 migration sequence / dependency 切，不要讓多票同時重寫同一核心 owner；
- closing/acceptance ticket 負責跨票 regression、AI Library durable writeback、完整 DXF/Save→Reload acceptance。

每張票至少列：

- `Requirement Authority`
- `Spec References`
- `AI Library References`
- `AI Library Writeback`
- `Blocked by`
- `Issue Closure owner`
- `What to build`
- `Acceptance Tests`

`Acceptance Tests` 可以引用 approved spec 的 T-IDs，也可以列尚待施工時建立的 RED→GREEN tests；它不是 requirement approval gate。

## 5. Closure-owner machine gate

每張 draft ticket 在發布前必須通過：

```text
tools/ticket_breakdown_guard.py
```

規則：

- `Issue Closure owner` 必須**恰好一個**。
- draft identity 使用單一 `T<N>`。
- GitHub publication 後改成單一 `#<N>` owning Issue。
- `TBD`、everyone、多人 owner、斜線/或選項全部 fail closed。
- breakdown-level validation 必須確認引用的 `T<N>` 真存在。

machine validator 只擁有 closure-owner schema，不擁有產品需求或 ticket granularity。

## 6. Publish tickets

### 已核准規格路徑

使用者已要求拆票時，完成 machine validation 後即可發布；**不再插入第二次人工 approval gate**。

GitHub-backed project：

1. blockers first 建立 owning Issues。
2. fresh-read issue number/title/body。
3. 將 draft `Issue Closure owner: T<N>` 回填成 exact `#<N>`。
4. 建 dependency/sub-issue relation（工具支援時使用 native relation；否則 body 明確列 dependency）。
5. readback 確認 Requirement Authority / Spec References / Acceptance Tests / blocker 都存在。
6. 然後才交給派工/執行 Skill。

不要自行 close parent/master issue；closing ownership 由指定 closing ticket 處理。

### 未核准需求路徑

只有 requirement 被使用者核准後才可發布實作 tickets；核准後立即切入上方 fast path，不再多一輪 breakdown approval。

## 7. Ticket template

```markdown
# T<N>: <Ticket title>

**What to build:** <可交付的 end-to-end behavior>
**Requirement Authority:** <approved spec/issue/current explicit requirement>
**Spec References:** <R-xxx / T-xxx / section refs>
**AI Library References:** <exact paths>
**AI Library Writeback:** <exact path + update intent，或 None + reason>
**Blocked by:** <None 或 exact T/#>
**Issue Closure owner:** T<N>
**Status:** ready-for-agent

## Acceptance Tests
- [ ] <test / command / observable acceptance>
- [ ] <test / command / observable acceptance>
```

## 8. AI Library traceability

WHD breakdown 必須讀相關 CURRENT AI Library。若本次 approved requirement 改變了可重用流程/產品 invariant：

- 至少一張 closing/acceptance ticket 標 `AI Library Writeback: REQUIRED`；
- 指定 exact target path/category；
- writeback 不得建立第二套 domain authority，只記 current accepted rule 與 owner reference。

## 9. Deep-module / combined acceptance

若來源是大型跨模組 work：

- 每張施工票仍需 GitHub owning Issue；
- 至少一張 Combined Acceptance owner；
- 至少一張 AI Library Writeback owner；
- 有 parent/chain topology 時再明列 Chain Closure owner；
- 這些角色可以同票，但 identity 不得模糊。

Combined Acceptance 至少負責：

- cross-ticket regression；
- source ownership / duplicate authority scan；
- Save→Reload / DXF / product regression（適用時）；
- final target drift audit；
- durable writeback；
- parent/child closure readback。

## 10. Red flags

- 「已有核准 spec，但 Skill 又叫我先寫 requirement RED」→ 錯，走 `APPROVED_REQUIREMENT_FAST_PATH`。
- 「拆票後還要再問一次要不要建 Issue」→ 已核准規格且使用者已要求拆票時，不新增第二人工 gate。
- 「Acceptance test 還沒寫，所以 requirement 不算 approved」→ 錯；產品核准與 implementation RED 是不同層。
- 「需求仍有兩個互斥答案，直接拆票」→ 錯，先走 `REQUIREMENT_DISCOVERY_PATH`。
- 「environment/import/missing path failure 當 requirement RED」→ 錯。
- 「AI Library 舊文蓋過使用者 current approved spec」→ authority 順序錯。
- 「有 branch/commit 就算 owning Issue」→ 錯，GitHub-backed project 仍需 real owning Issue。

<!-- ISSUE693_COMBINED_ACCEPTANCE_WRITEBACK_V1 -->
## #693 Combined Acceptance durable readback

- domain: `skill_ticket_breakdown`
- accepted chain: `#687/#688/#689/#690/#691/#692 -> #693`
- retained invariant: machine-readable single `Issue Closure owner` remains mandatory.
- historical RED-first publication rule is superseded by `APPROVED_REQUIREMENT_FAST_PATH` for already-approved requirements.
- deployment/readback manifest: `docs/governance/issue693_combined_acceptance_writeback_manifest.json`
