---
whd_doc_role: REFERENCE
whd_contract: continuous-execution-machine
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# Executable Continuity Controller / 文件規則不等於執行鎖

## EXECUTABLE_CONTINUITY_CONTROLLER_PITFALL_V1

### 事故

WHD 已經有 `NONTERMINAL_NEXT_ACTION_GATE`、`REMOTE_QA_ACTIVE_LOCK`、`STALE_WAIT_WATCHDOG`、30 秒 polling、`使用者不是 scheduler` 等完整文字規則，但實際長流程仍會出現「規則說不能停，工作卻在 non-terminal 狀態結束回合」。

根因不是再少一句提醒，而是舊 machine guard 多數只做：讀 Skill / AI Library 文字，再 `assert` 某些 marker 字串存在。這只能證明**文件寫了規則**，不能證明 runtime state 可保存、可恢復，也不能真的拒絕 non-terminal finalization。

### 永久判定

1. **Documentation != enforcement.** `final 禁止`、`使用者不是 scheduler`、`STALE_WAIT_WATCHDOG` 等 marker 只能當文件相容性 guard，不能再被描述為「已鎖死停頓路徑」。
2. 長流程 durable state 的 executable authority 是 `tools/continuity_controller.py`，操作/語意 authority 是 `.agents/skills/engineering/executable-continuity-controller/SKILL.md`。
3. Non-terminal states 固定為 `RUNNING / WAITING_REMOTE / RECOVERING / BLOCKED`，每一個都必須有非空 `next_action`；沒有就 fail closed。
4. `WAITING_REMOTE` 必須有 exact positive `run_id + head_sha`，並在可得時保存 `job_id / log_cursor / evidence`。文字寫著 WAITING 不是遠端真相。
5. checkpoint 必須 versioned + atomic persistence；runtime cut 後 `load_checkpoint → identity/drift verification → exact next_action`，不得重新把使用者當 scheduler，也不得無條件重跑已完成 phase。
6. `assert_finalizable` 是 workflow/issue/acceptance closure 的 machine gate。任何 non-terminal checkpoint 都必須拒絕 finalization；只有 `TERMINAL_SUCCESS / TERMINAL_FAILURE` 可通過 controller gate。
7. Remote run terminal 不等於整張工作 terminal。若 counts / invariants / cleanup / drift / issue closure 還有 next action，state 應回 `RUNNING(next_acceptance_action)`，不得提前落 `TERMINAL_SUCCESS`。
8. `BLOCKED` 代表工作暫時需要外部 authority，但在 controller 層仍是 non-terminal；它不能被拿來繞過 workflow completion gate。
9. 真正驗收必須是 behavior tests：建立 checkpoint、模擬 runtime cut、reload、驗 exact identity/cursor/evidence、嘗試 non-terminal finalization 並確認被拒絕、驗 terminal transition lock。只搜文字不算。
10. 平台仍可能硬切聊天 Runtime；repo controller 無法控制平台。但正確目標是 **platform cut != workflow state loss / remote work stop**：遠端 runner 自己續跑，下一 Runtime 從 durable checkpoint 精準接續。

### 對應 Machine Guard

- `tools/continuity_controller.py`
- `tests/process/test_continuity_controller.py`
- `.agents/skills/engineering/executable-continuity-controller/SKILL.md`
- `.agents/skills/engineering/執行開發任務/SKILL.md::EXECUTABLE_CONTINUITY_CONTROLLER_V1_BRIDGE`
- `.agents/skills/engineering/monitoring-remote-qa/SKILL.md::EXECUTABLE_CONTINUITY_CONTROLLER_V1_BRIDGE`
- `.agents/skills/engineering/issue-closure-gate/SKILL.md::EXECUTABLE_CONTINUITY_CONTROLLER_V1_BRIDGE`

### 禁止說法

- 「Skill 已經寫了，所以不會再停。」——錯，除非 executable state / finalization behavior 有實證。
- 「pytest 有檢查 marker，所以 runtime guard 已完成。」——錯，那只是 documentation contract。
- 「remote run 還在跑，等使用者下次打繼續再查。」——錯；chat runtime 可用時主動 poll，runtime 被硬切後則從 durable run identity 恢復。
- 「平台切掉就沒辦法，所以 checkpoint 沒意義。」——錯；無法控制平台不代表可以接受 state loss 或把 remote scheduler 交給使用者。

## TURN_EXIT_ENFORCEMENT_V2

`assert_finalizable` 只能拒絕「把 non-terminal workflow 宣告完成」，不能單獨拒絕「assistant 在 non-terminal progress 回報後結束目前 turn」。這兩個 boundary 必須分離：

- workflow/issue completion → `assert_finalizable`；
- assistant response/turn boundary → `assert_turn_exitable`。

`RUNNING / WAITING_REMOTE / RECOVERING` 有可自主 next action，因此 turn exit fail closed；`BLOCKED` 代表真正外部 wait，可結束 turn但仍不可 finalizable；terminal states 可通過兩者。特別是 remote run terminal 後，只要 cleanup/drift/closure 未完，必須回 `RUNNING(next_acceptance_action)` 並由 turn-exit guard 接手，不能因 remote lock 解除就回報後停止。

對應 machine guard：`tools/continuity_controller.py` + `tests/process/test_continuity_controller.py`。Skill/AI marker tests 只保護 bridge 存在，不得再次被誤稱為 runtime enforcement。


## MASTER_CHAIN_CHILD_TERMINAL_EXIT_PITFALL_20260921

### 事故

#467/T1 已完成 remote QA、cleanup、drift audit 並 CLOSED/completed，下一張 #468/T2 已 OPEN、exact parent 已寫回、沒有 blocker；assistant 卻把「child terminal」誤當成「整條 Master #464 terminal」，在回報 #467 完成後結束 turn，留下 #468 未 claim。

### 根因

舊 `assert_turn_exitable` 只看單一 checkpoint 的 `RUNNING / WAITING_REMOTE / RECOVERING / BLOCKED / TERMINAL_*`。它不知道 terminal checkpoint 是 leaf/child 還是 Master，因此 `TERMINAL_SUCCESS` 會直接放行 turn exit，無法表示「這張 child 完成，但 Master 還有可自主執行的 next child」。

### 永久硬閘門

- Canonical executable owner：`tools/continuity_controller.py`。
- terminal child 若屬 Master/work-order chain，checkpoint 必須結構化保存 `master_issue + chain_state + next_issue + chain_next_action/chain_reason`。
- `NEXT_CHILD_EXECUTABLE`：child 可關，但 turn exit **必須拒絕**；scheduled resume / CLI resume 皆回 exact `chain_next_action`。
- `NEXT_CHILD_BLOCKED`：只允許 genuine external authority/capability wait，且需 reason。
- `CHAIN_COMPLETE`：只有整條 Master 已真正 terminal。
- `USER_STOPPED`：只有使用者明確停止／取消 chain。
- 外層已知 Master 時必須傳 `expected_master_issue`；checkpoint 漏填或填錯 Master handoff 一律 fail closed。
- 不得從聊天文字、Issue comment、commit message 或 evidence 字串推理 handoff authority。

Primary regression：`tests/process/test_issue473_master_chain_turn_exit_gate.py`。判斷式固定為：

`run terminal != child terminal != Master-chain terminal`


## TERMINAL_CLOSURE_HALF_STATE_PITFALL_V1

### 症狀
- child checkpoint 已 `TERMINAL_SUCCESS`，但 owning Issue 還 open、claim 還在 `RECOVERING/CLOSING`；
- 或 Issue/PR 已 close/merge，但 shared claim 還 active、next_action 還停在舊的 pre-merge 動作；
- scheduler 把「terminal checkpoint」誤當成「整個 process 可以停」。

### 根因
acceptance terminal 與 process closure 被拆成不同 transaction，但舊 `assert_turn_exitable` 只看 continuity state / Master handoff，沒有 machine-readable closure lifecycle。

### 永久防線
`tools/continuity_controller.py` 的 canonical closure progression 是：

```text
FINALIZATION_PENDING
→ ISSUE_CLOSE_PENDING
→ RELEASE_HANDOFF_PENDING
→ CLOSED
```

terminal 但 `closure_state != CLOSED` 一律拒絕 turn exit，並由 `closure_next_action` 繼續。舊 terminal JSON 缺 closure metadata 時 fail-safe 回復成 `FINALIZATION_PENDING`。

最後一步不可「先 claim RELEASED，再補 checkpoint CLOSED」，因 release 後已失去 active owner。必須在**同一個 coordination closure commit**原子寫入：

1. checkpoint `closure_state=CLOSED`；
2. shared claim `phase=RELEASED`；
3. successor / Master chain handoff。

即使 child CLOSED，`NEXT_CHILD_EXECUTABLE` 仍由 Master chain gate 阻擋 turn exit並直接續下一票。


## ISSUE633_FINALIZATION_PROOF_ORDER_PITFALL — proof 前先進 ISSUE_CLOSE_PENDING

2026-09-25 在 #632 整合後 fresh-read closure contract 發現：若流程採「`FINALIZATION_PENDING` 先 authorize/verify proof → 再把 checkpoint 改成 `ISSUE_CLOSE_PENDING` → close Issue」，第二步會改變 checkpoint fingerprint，導致剛取得的 proof 在真正 close 前立即 stale。

永久順序只有一個：

```text
FINALIZATION_PENDING
→ durable advance to ISSUE_CLOSE_PENDING
→ authorize-finalization + verify-finalization-proof on exact current checkpoint
→ NO CHECKPOINT MUTATION
→ close owning Issue
→ fresh readback closed/completed
→ advance RELEASE_HANDOFF_PENDING
→ atomic CLOSED + RELEASED + successor handoff
```

Machine 防線：`tools/continuity_controller.py::authorize_finalization` 必須拒絕任何 `closure_state != ISSUE_CLOSE_PENDING`。proof 產生後若 checkpoint evidence、closure state 或任何 serialized field 被改動，舊 proof 一律 stale；不得用舊 proof 關單。


## ACTIVE_DELEGATED_WORK_FALSE_STALE_PITFALL_V1
#631 → #636 證明 parent 可安靜但 delegated helper 仍在合法工作。

1. stale evaluator 先解析 parent structured delegated pointers。
2. open + active child = `ACTIVE_DELEGATED_WORK`、non-actionable；沿鏈到 child leaf。
3. child stale 才接 child；不得 takeover parent 再開 helper。
4. parent 宣告 child但 evidence missing/malformed → fail closed。
5. 同 `parent_issue + helper_key` 只能一個 active helper，已有就 resume/reuse。
6. child terminal = Issue closed + claim terminal/released；half-terminal 先 reconciliation。

Canonical machine owner：`tools/stale_claim_takeover.py`。


## EQUIVALENT_DUPLICATE_GREEN_PITFALL_V1

2026-09-25 #648 收尾時，同一個 `pr-write` mutation identity 被重複送出 Remote Guard，產生兩張仍有效且完全等價的 GREEN（runs `36095688419` / `36095692365`）。舊 classifier 只要看到兩張 matching GREEN 就一律 `AMBIGUOUS → FAIL_CLOSED`，導致合法收尾只能等 TTL 全數過期。

永久規則：

1. 只有 **mutation-relevant identity 完全相同**的 GREEN 才能折成 equivalent group；identity 包含 issue / worker / executor / action / branch / base / head / claim blob / guard authority / tested target / changed files，以及 takeover 專屬 identity。
2. equivalent group 沒有 durable mutation readback、且仍有 live member 時，整組只代表**一個** `PENDING` mutation。
3. 可 consume 的 canonical receipt 固定取「仍有效成員中 `issued_at` 最早者；同時則 `run_id` 最小者」。已過期 member 不得因另一張 duplicate 還活著而重新取得 mutation authority。
4. shadow receipt 永遠不可獨立 consume；請求 shadow `run_id` 必須 identity-mismatch fail closed。
5. 任一 equivalent member 的 action-specific durable readback 若證明 mutation 已發生，整組一起折成 `CONSUMED` 或 `MUTATION_DONE_RECONCILE_ONLY`，避免 shadow replay。
6. 全組皆 expired 才是 `EXPIRED_UNCONSUMED`；TTL 語意不因 dedupe 改變。
7. 只要任一 mutation-relevant identity 不同，仍維持真正的 `AMBIGUOUS → FAIL_CLOSED`，不得用 dedupe 掩蓋衝突。

Canonical machine owner：`tools/execution_claim_guard.py`。Primary regression：`tests/process/test_issue643_guard_transaction_gate.py`。#651 focused acceptance：run `36097453177`，23 passed / 0 failed。

<!-- ISSUE646_PITFALL_WRITEBACK_V1 -->
## #641 fingerprint normalization pitfall

#641 first finalization run 36051135751 因 raw JSON fingerprint 與 canonical Checkpoint normalization 不一致而 FAIL；改走 load_checkpoint + checkpoint_fingerprint 後 run 36051265277 GREEN。永久禁止自行 hash raw checkpoint JSON。

## EXPIRED_UNCONSUMED recovery pitfall
GREEN 過期且沒有 durable mutation proof時，舊 receipt 永久不可 consume。正確恢復：fresh exact identity → EXPIRED_UNCONSUMED → mint fresh recovery Guard。不得因『以前 GREEN』直接 mutation。

## Interactive liveness / provenance gap
#646 暴露 scheduler 有 heartbeat、chatgpt_interactive 沒有對稱 runtime liveness，且 generic executor_source 無法指出哪個聊天室。Required follow-up：interactive heartbeat；conversation/chat identity + invocation identity；scheduler lane + invocation identity；heartbeat不得取代 ownership authority。

## 2026-09-26 — legacy post-commit receipt-window drift

症狀：historical work commit 已存在、claim/checkpoint 尚停在 H0；H1 又確實是 H0 direct child、changed files 也與 prior GREEN Guard 完全一致，但 commit timestamp 晚於該 receipt 的 `expires_at`。ordinary post-commit reconciliation 會正確 FAIL，不能因「看起來就是那顆 commit」直接補 claim HEAD。

修復規則：只走 `LEGACY_POSTCOMMIT_RECONCILIATION_REPAIR_V1`。owner-authored `WHD_LEGACY_POSTCOMMIT_RECONCILE_V1` 必須 exact 綁 current claim blob、H0/H1、prior Guard run/request 與 actual changed files；trusted Remote Guard 再 fresh-read GitHub durable evidence。只允許 direct-child、唯一 expired matching receipt，且只做 claim/checkpoint HEAD reconciliation。任何 identity drift、merge/multi-hop、extra file 或 multiple candidate 都 fail closed。此 escape hatch 不得取代 normal receipt-window discipline。

## 2026-09-26 — local Guard stdout GREEN 不等於 durable post-commit authority

症狀：runtime 本機執行 `tools/execution_claim_guard.py` 得到 `EXECUTION_CLAIM_GUARD_GREEN` 後完成 commit，但 shared claim 仍停在 H0；既有 reconciler 只會消耗 Remote Guard request/receipt，因此 H1 雖合法卻無 durable receipt 可被 machine 反讀。

永久修正：local Guard mutation 若會讓 branch H0→H1，必須把結果持久化成 owning Issue 上唯一的 owner-authored `WHD_LOCAL_GUARD_RECONCILE_V1`，exact 綁 issue/worker/source/branch/base/current claim blob/H0/H1/actual changed files；reconciler 透過 `--local-guard-proof` fresh-read 驗證。local proof 僅允許單一 direct-child H1，duplicate/malformed/foreign/mismatched proof 一律 fail closed。若無法 durable 化 local GREEN，該 mutation 改走 Remote Guard，禁止再留下只有 stdout 的 Guard authority。
