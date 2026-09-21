---
whd_doc_role: REFERENCE
whd_contract: issue-closure
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# GitHub Issue Closure / Completion 踩坑規則

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

### 永久 fail-closed 規則

- Canonical executable owner：`tools/continuity_controller.py`。
- `assert_finalizable` 僅為 state-only predicate；不得當 issue/workflow closure authorization。
- closure 必須 fresh 綁定 `issue + owning branch + owning HEAD SHA`，三者任一缺失或與 checkpoint 不完全一致，立即 fail closed。
- 必須實際呼叫 `authorize-finalization` 並產生 bound `FinalizationProof`；聊天文字、stdout 摘錄、marker、舊 acceptance 記錄不能代替 proof。
- 真正 close/finalize mutation 前必須再次 `verify-finalization-proof`。
- proof 不存在、malformed、owner 不符、version 不符或 checkpoint fingerprint 改變，立即 fail closed。
- checkpoint / issue / branch / HEAD 有任何 drift，舊 proof 失效，必須重新 authorization。
- Proof 是 process-integrity receipt，用於防 accidental bypass / wrong owner / stale mutation；不是 malicious-writer cryptographic signature，不得過度宣稱。
- GitHub close 後仍必須 remote readback `state=closed + state_reason=completed`；proof 不能取代 issue-state evidence。

Primary behavior regression：`tests/process/test_finalization_owner_guard.py`。Canonical Skill：`.agents/skills/engineering/executable-continuity-controller/SKILL.md`；closure bridge：`.agents/skills/engineering/issue-closure-gate/SKILL.md`。

## 對應 Skill / Machine Guard

Canonical Skill：

`.agents/skills/engineering/issue-closure-gate/SKILL.md`

Machine guards：

- `tests/process/test_finalization_owner_guard.py`
- `tests/process/test_continuity_controller.py`
- `tests/test_issue_closure_completion_skill_contract.py`

Registry route：

`.agents/skills/skill_registry.json` → `issue-closure-gate`

任何派工收尾、Final Combined、production integration、關單、Master completion 都必須讓 Preflight 命中此 Skill，不得靠聊天記憶。

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

Executable owner：`tools/continuity_controller.py`；regression：`tests/process/test_issue473_master_chain_turn_exit_gate.py`。

## OPEN_PR_BASE_REF_CLEANUP_PITFALL

### 事故

2026-09-15 分支整理曾使用「已是 X ancestor + 非 OPEN PR head」作安全刪除條件。這個條件仍然不完整：它只保護 OPEN PR 的 `head.ref`，漏掉 `base.ref`。結果四張仍 OPEN 的 PR 保留 head branch，但 base branch 被 cleanup 刪除；之後只能依 PR metadata 記錄的 exact base SHA 原樣恢復 refs。

### 永久規則

- OPEN PR 是雙端 ref contract：**`head.ref` 與 `base.ref` 都是 protected refs**。
- branch 已 merged、已是 X ancestor、對應 issue 已 CLOSED/completed、或名稱看似 QA/runner，都不足以覆蓋 OPEN PR ref protection。
- 每批刪除前 fresh live-fetch OPEN PR；不能沿用上一輪 inventory。
- 任一 OPEN PR 的 head/base ref evidence 缺失、空白或 malformed，整批 branch deletion fail closed，不能「先刪確定的」。
- Canonical executable guard 是 `tools/branch_cleanup_ref_guard.py`；刪除候選必須先經 `assert_delete_candidates_safe`。
- Primary regression 是 `tests/process/test_branch_cleanup_ref_guard.py`，其中必須保留「base ref deletion 被拒絕」案例。文字 marker 不是 runtime protection。
- 若誤刪 OPEN PR ref，修復必須使用該 PR remote metadata 記錄的 exact ref + SHA；不得猜 branch tip、不得從 current X 重建冒充原 base。
