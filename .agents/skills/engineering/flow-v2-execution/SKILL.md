---
name: flow-v2-execution
description: WHD Flow v2 唯一 execution/control-plane runtime contract。用於工單執行、排程 A/B、工作槽、remote QA、handoff、recovery、closure 與 runtime resume；所有入口都必須以 native ExecutionRecord、lease/YIELD、structured next_action 與 atomic terminal transaction 為準。
whd_doc_role: CURRENT
whd_contract: flow-v2-execution
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Flow v2 Execution


## PROJECT_STARTUP_HARD_GATE_V1

<!-- EXECUTION_ENTRY_AUTH_PURPOSE_BRIDGE_V1 -->

Flow v2 不得繞過專案啟動硬閘門。每一個新的 task/runtime/invocation（recurring scheduler、/排程A、/排程B、/工作0..3、互動執行、takeover、resume、recovery）在任何 substantive analysis、claim、Guard、repository mutation 或一般 workflow dispatch 前，固定依序：

0. **WORK_ROOT_BOOTSTRAP_HARD_GATE_V1**：任何一般 file/repo discovery 前先讀 root gate。互動式/chat runtime 先 bootstrap-read Google Drive mount → exact `/Google Drive/WHD` → `/Google Drive/WHD/WHD_WORK_ROOT_HARD_GATE_V1.json` → Current Source Manifest，產生 `WHD_WORK_ROOT_GATE_EVIDENCE_V1`（`read_mode=GOOGLE_DRIVE_CANONICAL`）。GitHub-only / `SCHEDULER_LANE` / trusted remote action 若沒有 Drive connector，先 fresh-read `.agents/contracts/WHD_WORK_ROOT_HARD_GATE_V1.json` pointer-only mirror 並產生 `read_mode=GITHUB_MIRROR` evidence；mirror 不得把 GitHub checkout 改成預設 workspace root。
1. ChatGPT execution surface 完成 AI Library pre-action gate：`AI_LIBRARY_SEARCHED → RELEVANT_HISTORY_READ → LIVE_VS_HISTORY_RECONCILED`。
2. 使用 canonical `tools/execution_entry_contract.py` 產生並 user-visible 顯示 `WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1`；每個 invocation 必須重新產生。
3. fresh-read project `AGENTS.md` 與本 `flow-v2-execution` Skill，完成 `SKILL_INVOCATION_ANNOUNCEMENT_GATE_V1`。此時仍未取得 execution mutation authority。
4. recurring scheduler / `/排程A` / `/排程B` 若尚不知道 exact owning Issue，才可使用下面的 `SCHEDULER_STARTUP_BOOTSTRAP_READ_ONLY_DISCOVERY_V1`；其他入口不得借此擴張 startup scope。
5. 對 exact owning Issue + branch + HEAD 執行 Phase6 Knowledge Preflight；GitHub-only runtime 只可送 trusted `WHD_REMOTE_PHASE6_PREFLIGHT_REQUEST_V1`。
6. fresh-read Preflight 回傳的全部 REQUIRED SKILLS / REQUIRED REFERENCES 並保留 evidence。
7. scheduler 若曾使用 bootstrap projection，必須丟棄該 projection 並再次 fresh-read canonical scheduler projection；只有到此時，才可進入 Flow v2 ExecutionRecord / transaction / lease / next_action 與正常 WAKE。

### SCHEDULER_STARTUP_BOOTSTRAP_READ_ONLY_DISCOVERY_V1

`READ_ONLY_BOOTSTRAP_ONLY` 是為解除「remote Preflight 需要 owning Issue，但 scheduler 必須先 discovery 才知道 owning Issue」循環依賴的窄例外；它不是 execution phase，也不是 authority。

- 前置條件固定為：work-root gate 已完成（scheduler 使用 `GITHUB_MIRROR`）、AI Library gate 已完成、fresh per-invocation startup declaration 已 user-visible 產生、且已 fresh-read `AGENTS.md` 與本 Skill。
- 唯一可讀範圍：`coord/execution-v2` 的 canonical ExecutionRecords、DERIVED_CACHE_ONLY `ready-index`、`tools/execution_scheduler_view.py` 的純 read-only scheduler projection，以及解析 exact owning Issue / work branch / target branch / HEAD 所需的 GitHub metadata。
- 唯一目的：取得 trusted remote Phase6 Preflight 所需的 exact owning Issue + branch + HEAD，然後送出該 Issue 上的 `WHD_REMOTE_PHASE6_PREFLIGHT_REQUEST_V1`。不得建立永久 bootstrap Issue；若 projection 確認沒有可執行工作，仍須完成本 invocation 的 project startup requirements後才能依正常 scheduler exit contract 判讀。
- `PRE_PREFLIGHT_MUTATION_FORBIDDEN`：Preflight GREEN 且全部 REQUIRED SKILLS / REQUIRED REFERENCES fresh-read 完成以前，禁止 WAKE / HEARTBEAT / PROGRESS monitor write、claim、ACQUIRE、transaction request、Guard、repository mutation、QA、merge、closure、takeover、lease mutation、ExecutionRecord mutation或任何其他 execution side effect。除了 owner-authored trusted Phase6 Preflight request 本身，不得 dispatch 其他 workflow / mutation transport。
- bootstrap projection 只用來綁 Preflight identity；Preflight 完成後必須丟棄並 fresh-read `coord/execution-v2` / scheduler view，禁止把 bootstrap 時看到的 state 直接拿去 ACQUIRE 或 mutation。

startup declaration 只提供 provenance/intent，不取代 claim、Guard、Preflight、ExecutionRecord 或 transaction fencing；bootstrap read-only discovery 也不提供任何 mutation authority。缺任一步固定 `FAIL_CLOSED`。前一聊天、前一 runtime 或前一 scheduler wake 的宣告不得沿用。

<!-- FLOW_V2_EXECUTION_CANONICAL_V1 -->

本 Skill 是 WHD execution/control-plane 的唯一 CURRENT operational contract。其他 workflow Skills 只可做入口 bridge，不得建立第二套 ownership、resume、closure、scheduler 或 recovery state machine。

## Canonical authority

- code / PR / CI authority：GitHub repository。
- execution semantic state branch：`coord/execution-v2`。
- per-Issue state：`.dispatch/execution/issue-<N>.json`，schema=`WHD_EXECUTION_RECORD_V2`。
- record/store：`tools/execution_record.py` + `tools/execution_record_store.py`。
- action vocabulary：`tools/execution_action_contract.py`。
- merge precheck：`tools/flow_v2_merge_precheck.py`。
- atomic transition：`tools/control_transaction.py`。
- terminal transport：`tools/control_transaction_transport.py` + `tools/control_transaction_terminal_executor.py`。
- scheduler view：`tools/execution_scheduler_view.py`。
- invocation exit：`tools/execution_invocation_exit.py`。
- work-slot projection：`tools/execution_work_slot_view.py`。
- explicit READY ingress：`tools/execution_dispatch_ingress.py`。
- mutation policy：`tools/execution_authority_policy.py`。
- runtime observability (NON_AUTHORITY)：`coord/monitor-v2:.dispatch/monitor/runtime/*.json`。

`.dispatch/execution/ready-index.json` 固定 `authority=DERIVED_CACHE_ONLY`；它可重建，永遠不能授權 mutation 或 ownership。

## Main state machine

只有 `READY / ACTIVE / VERIFYING / INTEGRATING / BLOCKED / DONE`。Recovery 不是 phase；readback、poll、reconcile、generation fencing、retry 都由 structured action/fields 表達。

## Structured next_action

machine logic 只能讀 `next_action.kind + args`，不得解析 prose。主要 action：`ACQUIRE / START_BRANCH / APPLY_COMMIT / START_QA / POLL_QA / ACCEPT_QA / FAIL_QA / MERGE / SYNC_TARGET / HANDOFF / FINALIZE / YIELD / RECONCILE / BLOCK / WAIT_EXTERNAL`。

### MERGE_PRECHECK_AND_TARGET_SYNC_V1

Flow v2 的 `MERGE` 不是「accepted QA 後直接呼叫 GitHub merge API」。任何 external PR merge side effect 固定由 trusted `control_transaction_production_executor.py` 擁有，且在 side effect 前執行 live merge precheck。

MERGE precheck 必須 fresh-read並 exact 比對：

- current ExecutionRecord `head_sha / target_branch / target_sha`；
- PR number、open/merged state、PR head SHA、base branch、base SHA、mergeable；
- live target branch HEAD；
- target branch ruleset 的 required status checks，以及 current PR head 上對應 check conclusion。

固定結果：

- identity mismatch → fail closed，不得 merge。
- required checks 尚未 success → 保留 `MERGE`，只 poll/retry required checks；不得先撞 GitHub 405 再把 405 當流程判斷。
- live target 或 PR base 已前進 → **不得嘗試 stale MERGE**。該 `MERGE` transaction 必須原子轉為 `semantic_state=TARGET_DRIFT_REQUIRES_SYNC`，更新 fresh `target_sha`，並把 structured `next_action` 改成 `SYNC_TARGET`。
- exact identity + target current + required checks GREEN + mergeable=true → trusted executor 自己執行 PR merge，fresh-read target SHA 後才寫 `MERGE / RECONCILED`。

`SYNC_TARGET` 是正式 machine action，不是 recovery prose。固定走既有 scheduler-compatible `WHD_CONTROL_TRANSACTION_PUSH_REQUEST_V1` / `whd-control-transaction-v2-request.yml` trusted transport；chat/runtime 不得以 local git、Remote Desktop 或 connector `update_ref` 取代。trusted executor 使用 GitHub merge transport把 exact live target non-force merge 進 exact work branch：

- target/work ref 任一 SHA drift → CONFLICT，fresh-read重算；禁止 replay。
- merge conflict → fail closed，進 explicit repair；禁止 force push。
- sync 後 work HEAD 前進 → accepted QA 立即因 head mismatch失效，固定 `QA_INVALIDATED_BY_TARGET_SYNC → START_QA(exact new head) → POLL_QA → ACCEPT_QA → MERGE`。
- sync 判定 work branch 已包含 target、HEAD 不變 → 可只更新 target identity，回到 `MERGE`；既有 exact-head QA 可保留。
- `START_QA / POLL_QA / ACCEPT_QA` 必須把 post-sync PR identity與 revalidation workflow 以 structured args/effect 延續；不得靠聊天記憶找回 PR。

每次重新回到 `MERGE` 都必須再跑一次 live precheck，因 target 可在 QA 完成後再次前進。這個 gate 專門避免 #889 類「QA 已 GREEN，但 target 已 drift，最後到 GitHub merge 才報 required-check/merge error」事故。

## Atomic transaction

所有 mutation 綁定 issue + generation + canonical branch + expected record fingerprint + expected branch/head/target。結果只能是 `APPLIED / CONFLICT / FAILED`；不存在可跨 runtime 保存的中間授權 token。副作用後必須 fresh readback。

### CANONICAL_TRANSACTION_REQUEST_BUILDER_V1

所有 non-SEED Flow v2 push transaction request 必須由 `tools/control_transaction_request_builder.py` 建立 envelope；caller 不得手工拼接 `startup_evidence.declaration / execution_mode / work_root_gate`。builder 必須呼叫 canonical `tools/execution_entry_contract.py::build_startup_evidence`，並由 lane identity 唯一決定 `INTERACTIVE` 或 `SCHEDULER_LANE`。

若 push ingress 回 `CONFLICT` 且 `retryable=true`，固定執行 `FRESH_READ_REBUILD_SAME_SEMANTIC_ACTION`：fresh-read `coord/execution-v2`、generation、lease、target/head，再用 builder 重建**同一 semantic action**。不得沿用 stale request payload，也不得因 coord/generation/live-lease race 重放外部副作用。startup evidence 驗證失敗不是 retryable conflict；先由 builder 重建 fresh evidence。

### MERGE_LIVE_TARGET_PRECHECK_V1

`MERGE` 不是單純「QA 已接受就直接合併」。每次執行 structured `MERGE` 前，trusted production executor 必須 fresh-read exact PR、PR head/base、live target HEAD、target ruleset required checks 與 current-head check conclusions，並先執行 `tools/flow_v2_merge_precheck.py`。

硬規則：

1. PR 必須仍為 open、head 必須等於 current `ExecutionRecord.head_sha`、base branch 必須等於 `record.target_branch`。
2. 若 live target HEAD 或 PR base SHA 不等於 `record.target_sha`，分類固定為 `TARGET_DRIFT`；禁止先嘗試 GitHub merge，也不得把 stale required-check GREEN 當有效。
3. `TARGET_DRIFT` 必須由 MERGE transaction 原子改寫成 structured `SYNC_TARGET`，保存 exact live target SHA、PR number、target branch 與 revalidation workflow；不得靠聊天 prose 或臨時人工步驟續跑。
4. `SYNC_TARGET` 由 trusted GitHub-only production executor 使用 GitHub merge API 將 exact target SHA non-force 合入 current work branch。work HEAD 漂移、target SHA 漂移、merge conflict 一律 fail closed。
5. target sync 若推進 work HEAD，accepted QA 自動失效，下一步必須 `START_QA`；exact-head QA GREEN 後才可 `ACCEPT_QA → MERGE`。若 target 已是 work branch ancestor、work HEAD 未變，只可在 target identity 已 reconciliation 後回到 `MERGE`。
6. live target 未漂移時，required checks 必須對 current PR head 全部 success，GitHub 必須回報 mergeable=true，才可執行 actual PR merge。required check pending 是可重讀狀態，不得被誤判成 terminal blocker。
7. actual merge side effect、fresh PR merged readback、fresh target SHA readback全部由 trusted executor擁有；caller 不得提供假的 `merged_sha/target_sha` 來繞過 live precheck。

此 gate 專門防止「accepted QA 綁舊 base、target 已前進、直到 GitHub merge 才 405/required-check failure」的 #889 類型錯誤。

### MERGE_ANCHOR_DESCENDANT_FINALIZATION_V1

accepted merge SHA is an anchor，不是「target branch 永遠不可再前進」的 freeze point。ticket 已有 exact-head accepted QA 且 `closure.merged_sha` 已成立後，其他合法 ticket 可繼續推進同一 target branch；FINALIZE 不得因此強迫原 ticket 重跑 merge/QA/ancestry。

FINALIZE trusted executor 必須 fresh-read `record.target_branch`：
- current target == `closure.merged_sha`：直接使用 exact anchor readback。
- current target > anchor：只有在 machine proof 證明 `closure.merged_sha` 仍是 current target ancestor 時，才可把 `record.target_sha` 原子更新到 current target 並 FINALIZE。
- anchor 不是 current target ancestor、ref identity 不明、或 readback 無法證明：固定 fail closed；不得把 diverged history 當合法 target advance。

descendant proof 只能由 trusted `tools/control_transaction_production_executor.py` fresh-read GitHub ref/compare 後產生 `WHD_FLOW_V2_TARGET_ADVANCE_PROOF_V1`；caller-supplied prose/boolean 不構成 authority。

## Governance ancestry reconciliation

<!-- GOVERNANCE_ANCESTRY_RECONCILIATION_V1 -->

Paired governance deployment不得只停在 main / cleanup 兩個獨立 mirror merge。**cleanup/2d-3d-sync owns the final ancestry reconciliation**；main 只提供已接受的治理 history input，cleanup 仍是 product authority。

Future governance ticket 固定順序：
1. **merge the paired main governance PR first**，fresh-read accepted main SHA 與 cleanup SHA，並確認 governed content parity 已 GREEN。
2. 以 `.github/workflows/whd-governance-ancestry-reconcile.yml` 傳入 exact `expected_main_sha + expected_cleanup_sha`。workflow 僅允許 **history-only second-parent merge**：在 cleanup exact head 上建立 two-parent `ours` candidate，candidate tree 必須與 merge 前 cleanup tree 完全相同。
3. 若 ancestry 尚未存在，candidate 固定先推到非保護 `governance/ancestry-reconcile-*` branch，並以 `mode=ANCESTRY_CANDIDATE` dispatch `Governance Mirror Hard Gate`；只有 exact candidate SHA required check GREEN 後，才可 non-force fast-forward protected `cleanup/2d-3d-sync`。禁止先 direct-push protected cleanup 再期待 required check。
4. reconciliation 禁止 force-push / history rewrite；任何 input SHA drift、tree drift、parent identity drift、candidate-check failure 一律 fail closed。
5. workflow 成功後 fresh-read `WHD_GOVERNANCE_ANCESTRY_RECONCILIATION_RESULT_V1` 並再次執行 live ancestry gate，證明 accepted main SHA 已是 cleanup ancestor。receipt 的 cleanup SHA 是 ancestry anchor；後續合法 descendant target advance 不使 receipt 失效。
6. paired governance ticket 的 `FINALIZE` 前必須有 result receipt + live ancestry GREEN；若 current cleanup 已前進，套用 `MERGE_ANCHOR_DESCENDANT_FINALIZATION_V1`，不得無條件重跑 ancestry。

此 contract 的 machine owner 仍是 `tools/governance_parity_gate.py` + governance mirror/reconciliation workflows；不得新增第二套 ancestry state database。

## Lease / YIELD

live lease 時其他 invocation 回 busy，不覆寫。`lease=null` 的 same-lane nonterminal record 必須先做 ACQUIRE；expired lease 只允許符合 owner/lane contract 的原子 reacquire。ACQUIRE 成功後同一 invocation 立即續原本 structured next_action，不得把『拿到 lease』當停止點。runtime 物理邊界但 task 未 terminal時用 YIELD 清 lease、保留 exact next_action。**trusted writer 必須先以 `tools/execution_invocation_exit.py::classify_invocation_exit(..., host_boundary=True)` 驗證 `requires_yield=true` 才能接受 YIELD；`ACQUIRE → 無 substantive action → YIELD` 必須 fail closed。** YIELD 不是 task complete；DONE 才是 terminal。

## Scheduler A/B

A owner=`scheduler.6ab13fa557fc8191935c671214b865e2`，entrypoints=`00/20/40`。
B owner=`scheduler.e58ea936e7d0b12bd0d475314709d6f1`，entrypoints=`B15/B45`。

每次 wake：fresh-read `coord/execution-v2` → same-lane nonterminal record優先 → 無 current record才讀 derived ready-index → exact structured action。active exact QA run只 poll；沒有 current record且ready-index empty才是 NO_EXECUTABLE_WORK。scheduler只走 GitHub/remote capability，不 fallback local。

### SCHEDULER_CYCLE_PROGRESS_HARD_GATE_V1

- `RESUME_CURRENT`：若 lease 缺失/expired，先 ACQUIRE；**ACQUIRE 成功只是續跑前置，不是本輪 progress，也不是停止點**。同一 invocation 必須立即 fresh-read，繼續執行 ACQUIRE 前保存的 exact `next_action`。
- `READY_CANDIDATES`：`execution_scheduler_view.py` 必須提供 deterministic `selected_issue`（fresh ready-index 中最小 Issue）；scheduler 必須對該 Issue 送 ACQUIRE。若 CAS/claim race 輸掉，fresh-read 後重新投影與選擇，不得以「有多張可選」停止。
- 本輪只有以下 evidence 可合法離開：`DONE`、`LANE_BUSY`、合法 `BLOCKED`、active remote QA wait，或本 invocation 已有至少一個 reconciled substantive transaction（`START_BRANCH/APPLY_COMMIT/START_QA/ACCEPT_QA/MERGE/HANDOFF/FINALIZE/RECONCILE/BLOCK`）後因 host boundary 執行 YIELD。
- `WAKE`、讀取、文字回報、HEARTBEAT、單獨 ACQUIRE 都不是 substantive progress。
- scheduler 在任何正常 return 前必須等價執行 `classify_invocation_exit(..., host_boundary=True)`。若結果為 `SCHEDULER_EXECUTION_NO_PROGRESS`、`CONTINUE_EXECUTION` 或 `ACQUIRE_REQUIRED`，本輪**不得結束**；必須繼續 exact `next_action`。若 runtime 被外部強制切斷，視為 execution failure，不得宣稱 IDLE/DONE。

## Host scheduler lifecycle immutability

<!-- FLOW_V2_HOST_LIFECYCLE_IMMUTABILITY_V1 -->

Recurring scheduler entrypoints are persistent host infrastructure, not per-Issue execution state. A scheduled runtime MUST NOT call automation-management APIs or mutate its own or sibling A/B automation lifecycle, title, schedule, timing mode, prompt, or enabled state. Invocation completion is only a cycle return; it never means the recurring task object is terminal. Host lifecycle changes are allowed only from an explicit interactive user request or a dedicated host-reconciliation action outside the scheduled runtime. ExecutionRecord DONE, LANE_BUSY, BLOCKED, NO_EXECUTABLE_WORK, or any other per-cycle outcome must leave the recurring task object unchanged.

### HOST_LIFECYCLE_WATCHDOG_V1

Host lifecycle observation is NON_AUTHORITY and must remain separate from Flow v2 execution state.

- independent durable watchdog workflow: `.github/workflows/whd-scheduler-host-watchdog.yml`
- evaluator: `tools/scheduler_host_watchdog.py`
- watchdog output: `coord/monitor-v2:.dispatch/monitor/host/watchdog.json`
- optional ChatGPT host snapshot: `coord/monitor-v2:.dispatch/monitor/host/chatgpt-automations.json`
- exact entrypoint mirrors:
  - A00 → `.dispatch/monitor/host/entrypoints/a00.json`
  - A20 → `.dispatch/monitor/host/entrypoints/a20.json`
  - A40 → `.dispatch/monitor/host/entrypoints/a40.json`
  - B15 → `.dispatch/monitor/host/entrypoints/b15.json`
  - B45 → `.dispatch/monitor/host/entrypoints/b45.json`

Expected cadence is A=`:00/:20/:40`, B=`:15/:45`. After 120 seconds grace:
- expected occurrence without matching durable WAKE + fresh host snapshot enabled=true → `HOST_ENTRY_FAILURE`.
- expected occurrence without matching durable WAKE + fresh host snapshot enabled=false → `HOST_AUTO_PAUSE`.
- expected occurrence without matching durable WAKE and missing/stale host snapshot → `HOST_STATE_UNKNOWN`;不得猜成 auto-pause。
- matching WAKE but heartbeat expires before EXIT → `RUNTIME_LIVENESS_FAILURE`.

Scheduled runtimes may perform **read-only** host lifecycle inspection for observability and mirror `enabled / last_run_time` for all five A/B automations into the host snapshot. This explicit read-only exception does not permit any automation lifecycle mutation. Scheduled runtime仍不得 create/update/disable/delete/reschedule/complete任何 automation。

每個 scheduler runtime 在寫 canonical lane observation 時，還必須 mirror 同一 invocation 的 `WAKE / HEARTBEAT / PROGRESS / EXIT` 到自己的 exact entrypoint file，保留 `invocation_identity / last_wake_at / last_heartbeat_at / heartbeat_expires_at / last_progress_at / exit_at / exit_state`。host snapshot、entrypoint mirror與watchdog result都不得授權 ACQUIRE、mutation、merge、closure、takeover 或 owner 變更。

## Work slot / handoff

固定 work-slot projection 為 `worker.slot.0/1/2/3`。slot 只是 routing/projection tag，沒有獨立 state database。HANDOFF 只能變更 owner/routing/lease，不得順手改 branch/head/slot/next_action。`worker.slot.N` identity 永遠固定；下面的自動遞增只決定新工作要綁哪個既有 fixed slot。

### DEFAULT_INTERACTIVE_WORK_SLOT_GATE_V1

- 互動式使用者明確要求執行新 ticket，且未指定任何 `/工作N` / slot 時，**預設就是 `/工作0` / `worker.slot.0`**；這個既有 default 不變，`tools/execution_dispatch_ingress.py` 的 default normalization 仍保留 `worker.slot.0`。
- 只有在**建立新 READY record 前**，fresh-read canonical ExecutionRecords 發現預設 slot0 已 BOUND 時，才呼叫 `tools/execution_work_slot_view.py::select_first_available_work_slot(...)` 做 overflow，依 `worker.slot.1 → 2 → 3` 找第一個 EMPTY；slot0 EMPTY 時仍使用原本預設 `worker.slot.0`。
- 新工作明確使用 `/工作0` 時同樣套用上述 overflow；這不是改變 default identity，而是「0 忙時才 +1」的 capacity routing。
- 0–3 全部 BOUND 時，結果固定為 fail closed / `NO_AVAILABLE_WORK_SLOT`；不得覆蓋現有 occupant、不得 takeover、不得建立 duplicate slot occupancy。
- 若 ticket 已有 nonterminal ExecutionRecord，必須 resume 其原 `slot_id`，不得重新跑自動遞增。
- 裸 `/工作0` query/status 仍只查 slot0；不因 slot0 BOUND 而跳去 slot1。
- `/工作1`、`/工作2`、`/工作3` 明確指定時保持原 fixed slot，不套用 auto-increment。
- `SCHEDULER_LANE`、chain successor、純 query/status 不得因本 gate 自動取得任何工作槽。
- selection 後若發生 stale read / CAS / transaction conflict，必須 fresh-read 後重新選槽，不得沿用舊 EMPTY 判斷。
- `/工作0` 是預設互動 routing 入口，不是新的 claim/lease/ExecutionRecord authority。

## Runtime observability

<!-- WHD_RUNTIME_OBSERVABILITY_V1 -->

聊天室輸出不是 liveness authority。每個 scheduler A/B 與 `/工作0/1/2/3` runtime 都必須把非權威 observation 投影到 `coord/monitor-v2:.dispatch/monitor/runtime/<source>.json`。

固定事件（語意不得合併）：
- `WAKE`：invocation 開始；runtime 成功進場並 fresh-read 本 Skill 後立即寫入。
- `HEARTBEAT`：invocation 仍存活；scheduler 沿用 `tools/scheduler_runtime_liveness.py`，interactive 工作槽沿用 #679 `tools/interactive_runtime_liveness.py` machine owner，Flow v2 只做 adapter/projection，不另造 heartbeat authority。
- `PROGRESS`：durable 工作有 substantive 進展；trusted Flow v2 transaction APPLIED 後必須自動投影。PROGRESS 可刷新 `last_heartbeat_at / heartbeat_expires_at`，但 event 仍必須是 PROGRESS。
- `EXIT`：invocation 結束；正常離開前更新；結果只使用 `IDLE_NO_WORK / LANE_BUSY / YIELDED / BLOCKED / DONE` 等可判讀狀態。

`last_progress_at`、host `last_run_time`、聊天室輸出都不是 liveness。heartbeat TTL 沿用既有 machine owner 的 maximum 300 秒。

Flow v2 adapter 固定為 `tools/flow_v2_runtime_observation.py`；它不是 authority，只把既有 scheduler/#679 liveness evidence 與 trusted transaction progress 投影到 `coord/monitor-v2`。

工作槽 observation 最低欄位：
`slot_id / issue / claim_worker / invocation_identity / conversation_identity / branch / head_sha / last_wake_at / last_heartbeat_at / heartbeat_expires_at / last_progress_at / exit_at / exit_state / liveness_state`。
`conversation_identity` host 無法提供時可用 machine-readable `UNAVAILABLE`，不得猜測。
`liveness_state` 只由 heartbeat/exit evidence 推導（`LIVE / EXPIRED / ENDED / UNKNOWN`），不得授權 execution/takeover。

Scheduler observation 亦必須保留 exact `invocation_identity`、branch/head、heartbeat timestamps 與 liveness_state。

監控 branch 僅供 observability：
- `coord/monitor-v2` 永遠不是 execution authority。
- monitor observation 不得授權 ACQUIRE、mutation、merge、closure 或 takeover。
- observation 與 `coord/execution-v2` 衝突時，以 ExecutionRecord 為準；monitor 只能標記 `OBSERVATION_DRIFT`。
- 缺少 EXIT 或長時間沒有 progress 可被 whd-monitor 判為 `STALE_RUNTIME_SUSPECTED`，但不能因此直接改 execution state。

## Generation fencing + salvage

偵測到可能仍存活的舊 writer時：bump generation、換 canonical branch、綁 exact base/head/fingerprint。舊 generation後續寫入=`ORPHAN_WRITE`，不可直接 merge/accept。舊成果仍可 freeze donor HEAD 後分類 `ADOPTABLE / PARTIAL / STALE_CONFLICT`；可用部分收編到 current generation，只重做不能證明相容的部分。

## Remote QA

START_QA 綁 exact head；同 record/head只允許一個 active run。START_QA 可從 ACTIVE / VERIFYING / INTEGRATING 進入 VERIFYING：INTEGRATING 只用於「原 accepted head 後續因合法 APPLY_COMMIT / target reconciliation 前進而需要重新 exact-head QA」；不得把這條路徑當成跳過既有 acceptance。active只 POLL_QA；success→ACCEPT_QA；若來源是 integration revalidation，ACCEPT_QA 必須以 next_state=INTEGRATING 回到 merge gate，且 MERGE 仍強制 qa.accepted_head_sha == current head。terminal non-success→FAIL_QA。FAIL_QA 必須綁 exact run_id + run_head_sha，清除 active_run、保持 work_branch/head/target/owner/lane/slot 不變，回 ACTIVE/QA_FAILED_REPAIR，並寫入一個 executable repair next_action；不得把 failed QA 當 blocker 或 acceptance。

## Blocker

只有 `EXTERNAL_DEPENDENCY / MISSING_CAPABILITY / AUTHORITY_DENIED / PLATFORM_FAILURE` 可進 BLOCKED。一般 poll/readback/reconcile/retry不是 blocker。

## Finalization

<!-- FLOW_V2_FINALIZE_ISSUE_CLOSE_HARD_GATE_V1 -->

FINALIZE 是 Issue closure 的唯一 terminal gate。trusted production executor 必須先 fresh-read current ExecutionRecord 並驗證 current HEAD 已有 accepted QA、MERGE 已有 fresh target readback，然後由 trusted FINALIZE path 自己 fresh-read GitHub Issue：

1. Issue 若仍 open，立即以 state=`closed`、state_reason=`completed` 關閉；不得把「PR 已 merge」當作 Issue 已 close。
2. close 後必須再次 fresh-read GitHub Issue；只有 `state=closed + state_reason=completed` 才能產生 closure evidence。
3. caller 傳入的 `issue_closed=true` 不具 authority，trusted writer 必須以 GitHub fresh readback 覆寫。caller 傳入的 `released_at` 同樣不具 authority；`released_at` 固定優先使用 fresh Issue `closed_at`，只有 GitHub 未提供 `closed_at` 時才可用 trusted writer current UTC time fallback；caller 不得因漏填 `released_at` 讓合法 FINALIZE 失敗。
4. close/readback 失敗、Issue 仍 open、state_reason 非 completed、QA/merge identity 不符時，FINALIZE 必須 fail closed；ExecutionRecord 保持 nonterminal，不得寫 DONE。
5. Issue 已 closed/completed 時仍必須 fresh-read確認，不得因為舊 comment、PR body 的 `Closes #N`、或 default/non-default branch 自動關單假設而跳過。
6. 只有 hard gate 成功後，才把 record寫成 DONE、清 lease/owner、next_action=null並保存 closure evidence。

因此「merge + acceptance 完成但 Issue 還開著」不是合法 terminal；同一 FINALIZE 必須把 Issue 收乾淨並 readback。

## Legacy compatibility

2026-09-28 前的舊 coordination、prewrite、separate finalization 與 turn-exit artifacts只作 audit/migration evidence。**例外：scheduler runtime liveness 與 #679 interactive runtime liveness 的既有 machine owners 仍為 CURRENT liveness capability，但只可經 Flow v2 observation adapter 投影為 NON_AUTHORITY observability，不得恢復成 execution authority。** 其他 legacy workflow 仍 fail-closed。

## Progress

進度/status是 non-blocking checkpoint。scheduler/長任務第一行固定：
`【處理者：<handler>｜owner=<record owner|NONE>｜工單：#<issue|NONE>】`
回報後只要 current invocation 還能合法施工，就立即繼續。

## Production transaction transport

<!-- FLOW_V2_PRODUCTION_TRANSACTION_V2 -->

Scheduler runtime 的 canonical mutation ingress 是 **push request**，不是 workflow_dispatch。

- A request branch: `coord/transaction-requests-a`
- B request branch: `coord/transaction-requests-b`
- interactive work-slot request branches:
  - `/工作0` → `coord/transaction-requests-work0`
  - `/工作1` → `coord/transaction-requests-work1`
  - `/工作2` → `coord/transaction-requests-work2`
  - `/工作3` → `coord/transaction-requests-work3`
- request branch/lane identity 是 hard gate：A/B branch 只接受各自 scheduler owner；work0~3 branch 只接受對應 `chatgpt.flowv2.workN`。禁止 scheduler 與 interactive runtime 共用 request branch，也禁止跨 lane 借道。
- request path: `.dispatch/transaction-request.json`
- trusted push workflow: `.github/workflows/whd-control-transaction-v2-request.yml`
- trusted writer: `tools/control_transaction_request_ingress.py` → `tools/control_transaction_production_executor.py`

每次需要 ACQUIRE/ACCEPT_QA/FAIL_QA/MERGE/FINALIZE/YIELD 等 transaction：
1. fresh-read `coord/execution-v2` exact HEAD 與 native record generation。
2. 本 lane request branch 必須已存在 `.dispatch/transaction-request.json` bootstrap seed；fresh-read 其 blob SHA，scheduler 只允許 CAS update，禁止在 runtime 走首次 `create_file`。若 seed 缺失，fail closed 並交由治理/bootstrap 修復。
3. 寫 `WHD_CONTROL_TRANSACTION_PUSH_REQUEST_V1`：
   - request_id：本 invocation/action 唯一值
   - issue / kind / lane_id / invocation_identity
   - startup_evidence：由 canonical `tools/execution_entry_contract.py::build_startup_evidence(...)` 產生，exact 綁定本 invocation_identity / repository / execution_mode / purpose / issued_at / expires_at / canonical declaration，並內嵌 fresh `WHD_WORK_ROOT_GATE_EVIDENCE_V1`；非 SEED request 必填。
   - expected_coord_head：步驟1 fresh HEAD
   - expected_generation：步驟1 record.generation
   - effect：fresh external readback payload
4. 記住 request commit SHA；push 會自動觸發 request workflow。
5. 只接受 event=push、workflow=`whd-control-transaction-v2-request.yml`、head_sha=request commit SHA 的 exact run。
6. 鎖 exact run 到 terminal；success 後 fresh-read `coord/execution-v2`，必須看到 generation+1、transaction.status=RECONCILED 與 expected post state。
7. trusted ingress 在任何 ExecutionRecord state read/mutation 前，先用 `validate_startup_evidence(...)` 驗 startup_evidence；缺失、過期（TTL>300 秒或已到期）、repository / execution_mode 不符、declaration 被改、invocation_identity 不符、root-gate evidence 缺失或 root identity/read_mode 不符，一律 FAILED/fail closed。
8. CONFLICT/FAILED 時 fresh-read重算；不得 replay 舊 request/effect。fresh runtime 必須重建 startup evidence；前一 invocation evidence 不得重放。

`coord/transaction-requests-a` / `coord/transaction-requests-b` / `coord/transaction-requests-work0~3` 的 seed 使用同一 request schema、`kind=SEED`、`issue=0`；trusted ingress 必須先驗 request branch 與 `lane_id` exact match，再回 `APPLIED / SEED_NOOP`，且不得讀寫 `coord/execution-v2`。seed 只負責確保後續 mutation 永遠走 existing-file CAS。\n\n`lease=null` 的 same-lane nonterminal record必須先送 ACQUIRE request（effect=`{}`），成功後同一 invocation 立即續原 structured next_action。

POLL_QA 是 observation。exact QA terminal success後，先 fresh-read run/head，再送 ACCEPT_QA request；terminal non-success 後先 fresh-read exact run/head/conclusion，再送 FAIL_QA request 回 repair。PR merge 仍是 GitHub external side effect：merge前驗 exact PR identity，merge後 fresh-read target SHA，再送 MERGE request。FINALIZE由 trusted production writer自行 close/readback Issue，並由 fresh `closed_at` 產生 authoritative `released_at`；caller 的 FINALIZE effect 不得必填或授權 `released_at`。request workflow固定具有 `issues: write`。

手動 `whd-control-transaction-v2.yml` 只保留管理/診斷用途；scheduler不得依賴 connector 未提供的 workflow_dispatch。
