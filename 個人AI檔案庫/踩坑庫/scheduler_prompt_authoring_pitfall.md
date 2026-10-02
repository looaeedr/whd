---
whd_doc_role: REFERENCE
whd_contract: scheduler-prompt-authoring
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Scheduler Prompt Authoring / 排程「有醒但沒施工」踩坑

> **[HISTORICAL / SUPERSEDED EXECUTION MECHANICS — FLOW_V2_LEGACY_EXECUTION_HISTORY_FENCE_V1]**  
> 本檔保留事故、migration 與舊治理機制做 reference。凡下文出現 `execution claim`、`coord/dispatch-claims`、`execution_claim_guard.py`、Remote Guard、Claim Activation、checkpoint closure、main↔X mirror 等 imperative wording，**都不是 CURRENT 執行指令**。CURRENT authority 固定為 `.agents/skills/engineering/flow-v2-execution/SKILL.md` + native `WHD_EXECUTION_RECORD_V2` + live lease/mutation_scope + atomic control transaction + `STALE_PLAN_MUST_DIE / ONE_ISSUE_ONE_MUTATION_WRITER`。若歷史敘述與 CURRENT contract 衝突，以 Flow v2 為準。


## SCHEDULER_PROMPT_AUTHORING_PITFALL_V1

### 事故

2026-09-24 的 WHD recurring lanes 出現一組可重複事故：

1. scheduler invocation 確實被喚醒，也留下 heartbeat，但沒有接著完成可執行 next_action，形成 **heartbeat-only**。
2. runtime 拿到 Remote Guard GREEN 後，在真正 consume / mutation / readback 前就結束 invocation，留下 **unconsumed GREEN**。
3. scheduler 把「自己其實能做的 run discovery / poll / readback」寫成 `BLOCKED`，再利用 BLOCKED 可結束 turn 的語意提前退出。
4. 為了縮短／重寫 automation prompt，authoring 過程曾把「fresh-read《遠端執行守門》」顯式 hard gate 刪掉，只剩《派工》，造成 transport / consume authority 依賴隱含記憶。
5. update API 回 SUCCESS 後若沒有 **post-update readback**，無法立即發現 schedule、lane identity、enabled 或 hard-gate marker 被誤改。
6. 前一輪 Guard GREEN 已經超過 `expires_at`，後一輪仍把它當作可 consume 的 authorization，形成 **expired GREEN / STALE_GUARD_RECEIPT** 漏洞。
7. branch / canonical checkpoint 已經有新的 durable mutation，但 `claim.head_sha` 與 next_action 還停在舊狀態；後一輪若只信 claim，可能重播已完成 mutation，而不是先對齊 **live branch HEAD**。

### 根因

- 把「prompt 有一句不能停」誤當成 machine enforcement。
- 把 heartbeat / Guard receipt / QA PASS 誤當 substantive progress。
- 把 `BLOCKED` 當成 turn-exit escape hatch，而不是 genuine external wait。
- 修改 prompt 使用 replacement semantics，卻沒有 baseline + invariant diff；刪一段文字就可能刪掉整個 Skill authority。
- 沒有把 schedule、durable lane owner、entrypoint identity 分開管理。
- 把 GREEN 誤當跨 invocation session token，沒有在 consume 當下驗 `now < expires_at`。
- 把 claim snapshot 誤當最高 runtime truth，沒有先比較 branch/checkpoint live durable evidence。

### CURRENT 永久規則

1. 建立／修改 WHD scheduler prompt 必須使用 `.agents/skills/engineering/寫排程/SKILL.md`，而 execution semantics 只 bridge 到 `flow-v2-execution`。
2. authoring 前 baseline-read automation 的 id/title/schedule/timing_mode/enabled/full prompt/updated_at/last_run_time；update 後必須 fresh readback。
3. prompt 不得要求 legacy Remote Guard / execution claim / checkpoint closure 作 CURRENT authority；owner/lease/mutation/closure 全由 `WHD_EXECUTION_RECORD_V2` + atomic transaction 決定。
4. 每次 wake fresh-read canonical scheduler view / ExecutionRecord；live lease、generation、record fingerprint、work/target HEAD 任一 drift 都丟棄 stale plan，從 structured `next_action` 重建。
5. authorization 不跨 invocation 保存為可重播 GREEN token。mutation 只能消費本次 Flow v2 transaction identity；副作用後 fresh readback。
6. exact-head terminal QA GREEN 已存在時優先 `CONSUME_QA`；GREEN 被接受且 continuation=MERGE 後立即 drain `MERGE → FINALIZE → DONE`，不得 YIELD。
7. WAKE / HEARTBEAT / progress / user-visible CHECKPOINT / QA GREEN 都不是 substantive completion 或 turn-exit authority。
8. `BLOCKED` 只給 fresh machine evidence 證明本 runtime 無合法 executable leaf 的 genuine blocker；read/poll/reconcile/CAS retry 本身不是 blocker。
9. `active_run` 存在時只追 exact `run_id + head_sha` 到 terminal；不得 duplicate dispatch。
10. 正常 return 前必須通過 `tools/execution_invocation_exit.py`；`CONTINUE_EXECUTION / CONTINUE_TERMINAL_TAIL / ACQUIRE_REQUIRED / SCHEDULER_EXECUTION_NO_PROGRESS` 都必須繼續。
11. scheduler runtime END / entrypoint observation 只屬 NON_AUTHORITY liveness；不得反向授權 owner、mutation、merge 或 closure。
12. 同一 logical lane 的 entrypoints 共用 durable lane owner；entrypoint 不是 owner。不同 lane 仍受 path reservation、single-writer 與 target drift fence。
13. repository-content implementation 不得在 scheduler/GitHub branch 直接 author/hotfix；必須 HANDOFF 到 canonical Google Drive root，完成 root tests/freeze/unlock 後才回 remote post-push tail。
14. 修改一個 prompt 發現 reusable authoring defect 時，要檢查 sibling / parallel lanes 與 permanent contract tests，不能只補單一入口。

### Documentation != enforcement

`寫排程` Skill 能避免 authoring 時刪錯 contract，但不能保證平台 runtime 永遠不會 hard-cut，也不能取代 Flow v2 ExecutionRecord / atomic transaction / invocation-exit machine。

真正判斷必須區分：

- prompt contract：下一個 runtime 應該怎麼做；
- Flow v2 transaction：這次 mutation 的 issue/generation/lease/record/head identity 是否仍有效；
- invocation-exit / structured next_action：目前是否必須繼續、YIELD、BLOCK 或 drain terminal tail；
- durable GitHub evidence：上一輪實際做到哪裡。

因此禁止說：「prompt 補好了，所以排程不會再停。」

正確說法只能是：prompt authoring contract 已補；是否持續施工要看下一輪的 durable mutation、exact run、turn-exit proof 與 END readback。

<!-- ISSUE646_PROMPT_AUTHORING_V1 -->
## #646 prompt authoring hard order — HISTORICAL/SUPERSEDED

歷史 prompt 曾固定使用 Guard recovery / helper / stale evaluator 鏈；**此 ordering 已被 Flow v2 structured next_action + generation fencing 取代，不得作 CURRENT prompt template。** 保留的教訓只有：不得以時間猜 stale、任何副作用後必須 durable readback。

CURRENT prompt 只保留可泛化 invariant：active exact remote run / delegated work 必須先 fresh-read；不得 replay stale authority；cadence/IDs/lane owner/recurring enabled policy不得因 task writeback改動。legacy helper/duplicate-GREEN 語意只作歷史事故索引。

Prompt/status provenance 要顯示 exact scheduler lane + invocation identity；interactive counterpart後續必須保存 conversation/chat identity + invocation identity並補 heartbeat。


<!-- ISSUE667_END_LIVENESS_V1 -->
## #667 Scheduler END / unified liveness / interactive takeover — HISTORICAL/SUPERSEDED

- heartbeat 與 invocation 終態使用 `WHD_SCHEDULER_RUNTIME_LIVENESS_V1` + exact matching `WHD_SCHEDULER_RUNTIME_END_V1`。
- 歷史 selector 曾綁 claim blob；CURRENT liveness只作 NON_AUTHORITY observation，execution identity以 record generation/fingerprint + live lease + invocation identity + branch/head 為準，任何 drift fail closed。
- matching END 後 machine status 是 `ENDED`；active exact remote run 仍是 absolute lock。
- runtime heartbeat maximum TTL 與 same-lane mutex 統一為 **<=300 秒**；不得另造 420 秒 prompt-only 判斷。
- user-directed takeover 的 legacy Remote Guard transport已退役；CURRENT 只允許 Flow v2 generation-fenced atomic owner transition，foreign live lease無失效證據即 fail closed。
- `/排程A` / `/排程B` activation 只 enable exact selected lane matching recurring entrypoints；post-update fresh readback，不改 cadence/prompt/title/owner，不碰另一 lane。

## EXECUTION_INTENT_ROUTING_PITFALL_V1

### 事故

2026-09-26 重新檢查 WHD scheduler / Skill 更新流程時，發現「更新控制面」與「執行工單」容易被同一套 continuity/dispatch wording 混在一起：

- 使用者只是要求修改排程 prompt、Skill、Issue body 或治理規則；
- runtime 卻因看到 open/unblocked Issue、空工作槽、next_action 或可用 Guard，順手取得 claim、建立 implementation branch，甚至自動接 successor；
- scheduler prompt 又把 drift/reconciliation/takeover capability 寫得像每輪固定前置 phase，造成正常工單也繞進 recovery。

### 永久規則

1. Scheduler authoring / automation update 預設是 `UPDATE_ONLY`；完成條件是 requested update + minimum validation/readback。
2. `UPDATE_ONLY` 不授權 implementation claim、implementation branch、successor chain 或 scheduler lane execution。
3. `/排程A` / `/排程B` 與真正 scheduled invocation 才是 `SCHEDULER_LANE` execution entrypoint。
4. `open / unblocked Issue`、空 work slot、legacy Guard 可用都不是 execution authority；只有 canonical READY/ACTIVE ExecutionRecord + valid transition/lease 能授權執行。
5. `NORMAL_PATH_FIRST`：正常 implementation 走 `READY → atomic ACQUIRE+reservation → root implementation/tests/freeze → Git candidate → QA → MERGE → FINALIZE/DONE`；不得復活 legacy claim-first / branch-first。
6. `RECOVERY_IS_EXCEPTION_NOT_PHASE`：takeover / reactivate / reconciliation / legacy repair 僅由 fresh machine evidence 觸發；condition 修復後立即回 normal path。
7. 修改 live recurring automation prompt 時只改本次 scope；cadence、enabled、lane owner 若未被使用者點名就保持原值，並 post-update fresh readback。

<!-- ISSUE693_COMBINED_ACCEPTANCE_WRITEBACK_V1 -->
## #693 Combined Acceptance durable readback

- domain: `scheduler_prompt`
- accepted chain: `#687/#688/#689/#690/#691/#692 -> #693`
- integration source head: `64a64d4a0ee8adae81396eaef52c16db97b57d4f`
- retained invariant: NO_MATCHING_HANDOFF is not NO_WORK; scheduler no-work requires exhaustive READY_WORK_CENSUS evidence.
- this writeback records durable acceptance/readback only; it does not create a second authority or state machine.
- deployment/readback manifest: `docs/governance/issue693_combined_acceptance_writeback_manifest.json`

<!-- ISSUE808_SCHEDULER_REMOTE_ONLY_EXECUTION_V1 -->
## 排程 remote control-plane 與 root content surface 邊界 — CURRENT

- 排程A/B 的 **control-plane / post-push integration** 保持 remote：GitHub/SCHEDULER/REMOTE_ACTION 負責 discovery、lease/transaction、preflight、CI/QA、merge、finalization/readback。
- 只要下一個 action 需要產生 repository-content diff，固定 HANDOFF 到 canonical `/Google Drive/WHD/work/active/...`；這不是 workstation/local-shell fallback，而是 CURRENT root-local-first content surface。
- `handoff_source=LOCAL` 等 legacy provenance 欄位不提供 authority；CURRENT authority仍是 Flow v2 record + live lease + mutation_scope。
- remote capability 暫時不可用時保存 genuine blocker；不得改走 Remote Desktop/任意 workstation repo，也不得以 legacy Remote Guard / GitHub-side hotfix繞過 root gate。
- root-tested/frozen candidate push 後，scheduler 再接回 remote QA/merge/finalization tail。
<!-- ISSUE702_MUTATING_TOOLCALL_CRASH_RECOVERY_WRITEBACK_V1 -->
## Mutating toolcall crash-recovery canonical invariant

- Mutating work must persist an operation identity before the side effect and recover from durable readback before any ordinary next action after re-entry.
- Canonical crash boundaries are: `prepare → authorize → post-effect → readback → pre-reconcile → post-reconcile`.
- `EFFECT_OBSERVED` means the requested effect is already proven by exact durable/live evidence: **do not replay the mutation**; reconcile the operation and continue from the reconciled state.
- `AMBIGUOUS` means identity/effect cannot be proven: fail closed and repair evidence/authority; never guess whether a mutation happened.
- **HISTORICAL mapping only**：#702 的 continuity/Guard/Claim Activation owners 只保留 crash-boundary 與 migration evidence；不得再被 scheduler prompt或Entry Skill引用為 CURRENT execution authority。
- CURRENT continuity/reconcile/owner transfer/turn exit/closure 由 `WHD_EXECUTION_RECORD_V2` + `tools/control_transaction.py` + structured `next_action` + `tools/execution_invocation_exit.py` 單一擁有。
- Amendment-wide fault matrix authority is `docs/governance/issue702_crash_fault_injection_matrix.json`; accepted provenance/readback is recorded separately in `docs/governance/issue702_combined_acceptance_writeback_manifest.json`.



## FLOW_V2_ROOT_LOCAL_FIRST_SCHEDULER_CONTENT_FENCE_V1

CURRENT：排程A/B、GITHUB_ONLY、REMOTE_ACTION 的 remote authority只涵蓋 control-plane與 post-push integration。只要下一步需要產生新的 repository-content diff，就必須 HANDOFF 到 canonical Google Drive root workspace完成修改、分類測試、full gate、test receipt與 diff freeze；GitHub branch 不得成為 scheduler 的直接施工／熱修面。CI/remote QA 若發現內容錯誤，回 root 修正、重測、refreeze、再推候選。

這條規則用來避免把「scheduler 有 GitHub write capability」誤解成「scheduler 可以跳過 root-local-first」。
