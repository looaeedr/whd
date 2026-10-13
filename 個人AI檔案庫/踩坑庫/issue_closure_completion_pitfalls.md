---
whd_doc_role: REFERENCE
whd_contract: issue-closure
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# GitHub Issue Closure / Completion 踩坑規則

> **REFERENCE／歷史事故與防錯紀錄，非結案交易權威**。下述舊 Preflight／Flow v2／Master checkpoint 等程序以當時日期留存；現行 Issue close、CI、localX 與正式 X 授權，均依正式 X `AGENTS.md`、當次 Issue／PR 和 GitHub readback。不得要求退役交易收據作為現行關單前置。



## 事故模式：把 code integrated 誤報成 process completed

WHD 曾發生以下錯誤流程：

1. production target 已完成合法 fast-forward / merge；
2. Combined / regression QA 也已 GREEN；
3. 但對應 T5 / T6 / Final Combined / Master Issue 仍是 OPEN；
4. AI 卻因「code 已在 target」直接對使用者宣告「正式完成」。

這是流程錯誤。**合併不等於關單；integration != completion。**

## 永久判定邊界

### Code-state gate

只回答：程式碼是否已進 authoritative target、target HEAD 是否正確、tested→cleaned drift 是否可接受。

常見證據：

- target before/after SHA；
- merge / fast-forward relationship；
- tested head / cleaned head；
- regression run / invariant；
- temporary QA workflow cleanup。

### Process-state gate

只回答：GitHub 工單鏈是否真的完成。

常見證據：

- leaf/current ticket `state=closed` + `state_reason=completed`；
- closing / Final Combined ticket CLOSED/completed；
- 所有 required child / dependency ticket terminal；
- Master/parent 最後才 CLOSED/completed；
- 每次 close 後 remote readback。

兩套 gate 都完成，才可說「正式完成／全部完成／已關單」。

若 code 已進 target 但仍有 required open issue，固定分類：

`code integrated, process incomplete`

## 關單順序

依 dependency 由葉節點往上：

`leaf/current ticket → closing/acceptance → Final Combined（若有） → Master/parent`

禁止：

- target fast-forward 後直接關 Master；
- Combined GREEN 後跳過仍 OPEN 的 T5/T6；
- 看到 PR merged 就假設 issue 自動 closed；
- 只靠 issue body 的 Depends on / child list 猜 dependency 已完成；
- 沒有遠端反讀就聲稱 `state_reason=completed`。

## OWNING_CHECKPOINT_GUARD_BYPASS_PITFALL

### 事故模式

只有「checkpoint 看起來 terminal」或 Skill 文字寫著「要呼叫 guard」，仍然不足以證明 closure 是由正確 owner 執行：

1. 可能載入別張工單／別分支／舊 HEAD 的 terminal checkpoint；
2. 可能完全沒有真正呼叫 executable guard，只在聊天或 evidence 中寫「guard PASS」；
3. 可能 guard 呼叫後又修改 checkpoint，卻拿舊結果去關單；
4. bare `assert_finalizable` 只驗 state terminal，不能證明 owning identity，也不能證明 closure boundary 真的執行過 guard。

### 當時的 fail-closed 規則（HISTORICAL／已退役）

- 當時的 executable owner（現已移除）：`tools/continuity_controller.py`。不能當作今日 closure 授權。
- `assert_finalizable` 僅為 state-only predicate；不得當 issue/workflow closure authorization。
- **當時的 proof 綁定要求（HISTORICAL）**：closure 綁 `issue + owning branch + owning HEAD SHA`，缺失或 checkpoint 不符便 fail closed；現行不能因這份 REFERENCE 重新要求舊 proof 交易。
- **當時的 finalization 呼叫（HISTORICAL，現已退役）**：曾要求實際呼叫 `authorize-finalization` 並產生 bound `FinalizationProof`，不得以聊天文字或 marker 假裝成功；現在不再呼叫這個已移除的交易入口。
- **當時的 proof 驗證（HISTORICAL）**：close/finalize mutation 前曾需 `verify-finalization-proof`，不代表當前 GitHub Issue close/readback 的新硬閘門。
- proof 不存在、malformed、owner 不符、version 不符或 checkpoint fingerprint 改變，立即 fail closed。
- checkpoint / issue / branch / HEAD 有任何 drift，舊 proof 失效，必須重新 authorization。
- Proof 是 process-integrity receipt，用於防 accidental bypass / wrong owner / stale mutation；不是 malicious-writer cryptographic signature，不得過度宣稱。
- GitHub close 後仍必須 remote readback `state=closed + state_reason=completed`；proof 不能取代 issue-state evidence。

**歷史測試／Skill 名稱（已退役）**：`tests/process/test_finalization_owner_guard.py`、`.agents/skills/engineering/executable-continuity-controller/SKILL.md`、`.agents/skills/engineering/issue-closure-gate/SKILL.md` 只保留當時源流。不能據此要求已移除的關單守衛；現行權威依正式 X `AGENTS.md`、GitHub Issue／PR／CI 回讀。

## 當時對應 Skill / Machine Guard（HISTORICAL，非現行路由）

當時的 Canonical Skill（HISTORICAL／已退役）：

`.agents/skills/engineering/issue-closure-gate/SKILL.md`

當時的 Machine guards（HISTORICAL；不可作今日必經驗收）：

- `tests/process/test_finalization_owner_guard.py`
- `tests/process/test_continuity_controller.py`
- `tests/test_issue_closure_completion_skill_contract.py`

當時的 Registry route（HISTORICAL；不代表現行啟用）：

`.agents/skills/skill_registry.json` → `issue-closure-gate`

**歷史流程（已退役）**：當時要求派工收尾、Final Combined、production integration、關單與 Master completion 由 Preflight 命中此 Skill。現在不再要求 Preflight receipt；仍須依現行 `AGENTS.md` 驗證真正的 PR／CI、Issue close/readback 與剩餘可執行工作。

## CHILD_CLOSE_MASTER_CHAIN_HANDOFF_PITFALL

### 事故模式

leaf/child Issue 已 `closed/completed`、自己的 checkpoint 也 terminal，不代表 assistant turn 可結束。只要 Master 還有 required open child 且 next child 可自主執行，child close 後直接回 final 就是 process-state 停工。

### 永久規則

- child close 前後 fresh-read parent/Master 與 next dependency；
- terminal child checkpoint 必須帶 structured chain handoff；
- caller 以 fresh `expected_master_issue` 驗 Master ownership；
- `NEXT_CHILD_EXECUTABLE` → 立即 claim/start next child，turn exit fail closed；
- genuine external block / explicit user stop / whole-chain complete 才是合法 turn boundary；
- GitHub child closure evidence不能取代 Master-chain continuation evidence。

當時 executable owner：`tools/continuity_controller.py`；回歸為 `tests/process/test_issue473_master_chain_turn_exit_gate.py`。兩者已不在現行 X，不能重啟 Master-chain checkpoint／claim。

## OPEN_PR_BASE_REF_CLEANUP_PITFALL

### 事故

2026-09-15 分支整理曾使用「已是 X ancestor + 非 OPEN PR head」作安全刪除條件。這個條件仍然不完整：它只保護 OPEN PR 的 `head.ref`，漏掉 `base.ref`。結果四張仍 OPEN 的 PR 保留 head branch，但 base branch 被 cleanup 刪除；之後只能依 PR metadata 記錄的 exact base SHA 原樣恢復 refs。

### 永久規則

- OPEN PR 是雙端 ref contract：**`head.ref` 與 `base.ref` 都是 protected refs**。
- branch 已 merged、已是 X ancestor、對應 issue 已 CLOSED/completed、或名稱看似 QA/runner，都不足以覆蓋 OPEN PR ref protection。
- 每批刪除前 fresh live-fetch OPEN PR；不能沿用上一輪 inventory。
- 任一 OPEN PR 的 head/base ref evidence 缺失、空白或 malformed，整批 branch deletion fail closed，不能「先刪確定的」。
- Canonical executable guard 是 `tools/branch_cleanup_ref_guard.py`；刪除候選必須先經 `assert_delete_candidates_safe`。
- **2026-10-11 實際測試回讀**：原 `tests/process/test_branch_cleanup_ref_guard.py` 現已不存在，不能再聲稱它是正在執行的 Primary regression。正式 X 的 `tools/branch_cleanup_ref_guard.py` **確實仍存在**且提供 `assert_delete_candidates_safe`／`protected_open_pr_refs`；現行回歸改由 `tests/governance/test_default_branch_explicit_x_contract.py::DefaultBranchExplicitXContract::test_open_pr_head_and_base_refs_fail_closed` 驗證 head/base、`refs/heads/`、malformed evidence 的 fail-closed 行為，並由 Knowledge Governance Bootstrap 現有測試步驟執行。舊測試路徑只作歷史追溯，文字 marker 本身不是 runtime protection。
- 若誤刪 OPEN PR ref，修復必須使用該 PR remote metadata 記錄的 exact ref + SHA；不得猜 branch tip、不得從 current X 重建冒充原 base。

## INVALID_FINALIZATION_EVIDENCE_PITFALL

2026-09-23 發生 marker-only false finalization：terminal checkpoint 與 code integration 本身有效，但 scheduler 在沒有 trusted executor run / proof artifact 的情況下，把手寫 `FINALIZATION_GUARD_PASS` / `FINALIZATION_PROOF_VALID` 留在 Issue comment後直接關單。這不符合 `OWNING_FINALIZATION_GUARD_V2`。

**當時的 finalization 規則（HISTORICAL／已退役）**：no-shell scheduler 使用 `.github/workflows/whd-remote-finalization.yml`；workflow fixed-schema 綁 issue/worker/branch/head/checkpoint blob+fingerprint/claim blob/authority，只能跑 canonical authorize+verify。合法 closure evidence 是 terminal workflow run + `WHD_REMOTE_FINALIZATION_RECEIPT_V1` + uploaded proof artifact。marker/comment-only 一律分類 `INVALID_FINALIZATION_EVIDENCE`；誤關票必須 reopen → repair capability/process-state → fresh proof → close/readback。

## MALFORMED_TERMINAL_CHECKPOINT_CLOSURE_PITFALL_V1

#733 證明「code integrated, process incomplete」還可能進一步卡在 malformed terminal checkpoint：checkpoint 已 `TERMINAL_SUCCESS`，但 closure lifecycle 值不屬於 canonical enum，導致 finalization、ordinary Guard 與一般 reactivate 都無法合法前進。

**當時交易系統中的處理限制（HISTORICAL）**：當時禁止直接編輯 durable checkpoint，唯一合法入口曾是 Claim Activation `transition=terminal-checkpoint-repair`，exact 綁 prior claim/checkpoint blob 與 coord parent；candidate claim 必須 byte-identical，candidate checkpoint 必須等於 `repair_malformed_terminal_checkpoint()` 的 canonical repair 結果，且只能回到 `FINALIZATION_PENDING`。

Repair 只是恢復 closure transaction 的可執行狀態；它不代表 Issue 已關、不代表 claim 已 RELEASED，也不能取代 fresh finalization proof。之後仍照 `FINALIZATION_PENDING → ISSUE_CLOSE_PENDING → proof → close/readback → RELEASE_HANDOFF_PENDING → CLOSED + RELEASED` 完整收尾。

<!-- ISSUE693_COMBINED_ACCEPTANCE_WRITEBACK_V1 -->
## #693 Combined Acceptance durable readback

- domain: `issue_closure`
- accepted chain: `#687/#688/#689/#690/#691/#692 -> #693`
- integration source head: `64a64d4a0ee8adae81396eaef52c16db97b57d4f`
- 當時的 retained invariant（歷史）：Issue Closure owner 驗證 finalization、closed/completed readback，再持久化 checkpoint CLOSED／claim RELEASED；現行不要求退役 checkpoint／claim，應核對合法 Issue close 與 GitHub readback。
- this writeback records durable acceptance/readback only; it does not create a second authority or state machine.
- deployment/readback manifest: `docs/governance/issue693_combined_acceptance_writeback_manifest.json`

<!-- ISSUE702_MUTATING_TOOLCALL_CRASH_RECOVERY_WRITEBACK_V1 -->
## Mutating toolcall crash-recovery canonical invariant

- Mutating work must persist an operation identity before the side effect and recover from durable readback before any ordinary next action after re-entry.
- Canonical crash boundaries are: `prepare → authorize → post-effect → readback → pre-reconcile → post-reconcile`.
- `EFFECT_OBSERVED` means the requested effect is already proven by exact durable/live evidence: **do not replay the mutation**; reconcile the operation and continue from the reconciled state.
- `AMBIGUOUS` means identity/effect cannot be proven: fail closed and repair evidence/authority; never guess whether a mutation happened.
- **當時的 semantic owners（HISTORICAL）**：operation continuity = `tools/continuity_controller.py`；Guard = `tools/execution_claim_guard.py`；scheduler = `tools/scheduler_state_reconciliation.py`；Claim Activation = `tools/claim_activation_recovery.py`。四者均已從現行 X 移除，不得重新升格；以 `AGENTS.md`、CURRENT Skills、實際 GitHub 回讀為準。
- **歷史入口描述**：當時 Entry Skills 曾路由至上述 owners；此路由已退役，不能用 REFERENCE 文件建立第二套 continuity／Guard／scheduler／claim-activation。
- Amendment-wide fault matrix authority is `docs/governance/issue702_crash_fault_injection_matrix.json`; accepted provenance/readback is recorded separately in `docs/governance/issue702_combined_acceptance_writeback_manifest.json`.

