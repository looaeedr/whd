---
name: flow-v2-execution
description: WHD Flow v2 唯一 execution/control-plane runtime contract。用於工單執行、排程 A/B、工作槽、remote QA、handoff、recovery、closure 與 runtime resume；所有入口都必須以 native ExecutionRecord、lease/YIELD、structured next_action 與 atomic terminal transaction 為準。
whd_doc_role: CURRENT
whd_contract: flow-v2-execution
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Flow v2 Execution

<!-- FLOW_V2_EXECUTION_CANONICAL_V1 -->

本 Skill 是 WHD execution/control-plane 的唯一 CURRENT operational contract。其他 workflow Skills 只可做入口 bridge，不得建立第二套 ownership、resume、closure、scheduler 或 recovery state machine。

## Canonical authority

- code / PR / CI authority：GitHub repository。
- execution semantic state branch：`coord/execution-v2`。
- per-Issue state：`.dispatch/execution/issue-<N>.json`，schema=`WHD_EXECUTION_RECORD_V2`。
- record/store：`tools/execution_record.py` + `tools/execution_record_store.py`。
- action vocabulary：`tools/execution_action_contract.py`。
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

machine logic 只能讀 `next_action.kind + args`，不得解析 prose。主要 action：`ACQUIRE / START_BRANCH / APPLY_COMMIT / START_QA / POLL_QA / ACCEPT_QA / MERGE / HANDOFF / FINALIZE / YIELD / RECONCILE / BLOCK / WAIT_EXTERNAL`。

## Atomic transaction

所有 mutation 綁定 issue + generation + canonical branch + expected record fingerprint + expected branch/head/target。結果只能是 `APPLIED / CONFLICT / FAILED`；不存在可跨 runtime 保存的中間授權 token。副作用後必須 fresh readback。

## Lease / YIELD

live lease 時其他 invocation 回 busy，不覆寫。`lease=null` 的 same-lane nonterminal record 必須先做 ACQUIRE；expired lease 只允許符合 owner/lane contract 的原子 reacquire。ACQUIRE 成功後同一 invocation 立即續原本 structured next_action，不得把『拿到 lease』當停止點。runtime 物理邊界但 task 未 terminal時用 YIELD 清 lease、保留 exact next_action。YIELD 不是 task complete；DONE 才是 terminal。

## Scheduler A/B

A owner=`scheduler.6ab13fa557fc8191935c671214b865e2`，entrypoints=`00/20/40`。
B owner=`scheduler.e58ea936e7d0b12bd0d475314709d6f1`，entrypoints=`B15/B45`。

每次 wake：fresh-read `coord/execution-v2` → same-lane nonterminal record優先 → 無 current record才讀 derived ready-index → exact structured action。active exact QA run只 poll；沒有 current record且ready-index empty才是 NO_EXECUTABLE_WORK。scheduler只走 GitHub/remote capability，不 fallback local。

## Work slot / handoff

固定 work-slot projection 為 `worker.slot.0/1/2/3`。slot 只是 routing/projection tag，沒有獨立 state database。HANDOFF 只能變更 owner/routing/lease，不得順手改 branch/head/slot/next_action。

### DEFAULT_INTERACTIVE_WORK_SLOT_GATE_V1

- 互動式使用者明確要求執行 ticket，且未指定任何 `/工作N` / slot 時，machine ingress 必須把 `slot_id` 正規化為 `worker.slot.0`。
- `/工作1`、`/工作2`、`/工作3` 明確指定時保持原 slot，不得被工作0覆蓋。
- `SCHEDULER_LANE`、chain successor、純 query/status 不得因本 gate 自動取得 `worker.slot.0`。
- `/工作0` 是預設互動入口，不是新的 claim/lease/ExecutionRecord authority。

## Runtime observability

<!-- WHD_RUNTIME_OBSERVABILITY_V1 -->

聊天室輸出不是 liveness authority。每個 scheduler A/B 與 `/工作0/1/2/3` runtime 都必須把非權威 observation 投影到 `coord/monitor-v2:.dispatch/monitor/runtime/<source>.json`。

固定事件：
- `WAKE`：runtime 成功進場並 fresh-read 本 Skill 後立即寫入。
- `PROGRESS`：每次 substantive durable action/readback 後更新。
- `EXIT`：正常離開前更新；結果只使用 `IDLE_NO_WORK / LANE_BUSY / YIELDED / BLOCKED / DONE` 等可判讀狀態。

至少包含：source、handler、entrypoint、issue、slot_id、owner_id、state、action、last_wake_at、last_progress_at、exit_state、observed_at、record_fingerprint（有 record 且可可靠取得時）。

監控 branch 僅供 observability：
- `coord/monitor-v2` 永遠不是 execution authority。
- monitor observation 不得授權 ACQUIRE、mutation、merge、closure 或 takeover。
- observation 與 `coord/execution-v2` 衝突時，以 ExecutionRecord 為準；monitor 只能標記 `OBSERVATION_DRIFT`。
- 缺少 EXIT 或長時間沒有 progress 可被 whd-monitor 判為 `STALE_RUNTIME_SUSPECTED`，但不能因此直接改 execution state。

## Generation fencing + salvage

偵測到可能仍存活的舊 writer時：bump generation、換 canonical branch、綁 exact base/head/fingerprint。舊 generation後續寫入=`ORPHAN_WRITE`，不可直接 merge/accept。舊成果仍可 freeze donor HEAD 後分類 `ADOPTABLE / PARTIAL / STALE_CONFLICT`；可用部分收編到 current generation，只重做不能證明相容的部分。

## Remote QA

START_QA 綁 exact head；同 record/head只允許一個 active run。active只 POLL_QA；success→ACCEPT_QA；failure→structured repair/reconcile action。

## Blocker

只有 `EXTERNAL_DEPENDENCY / MISSING_CAPABILITY / AUTHORITY_DENIED / PLATFORM_FAILURE` 可進 BLOCKED。一般 poll/readback/reconcile/retry不是 blocker。

## Finalization

<!-- FLOW_V2_FINALIZE_ISSUE_CLOSE_HARD_GATE_V1 -->

FINALIZE 是 Issue closure 的唯一 terminal gate。trusted production executor 必須先 fresh-read current ExecutionRecord 並驗證 current HEAD 已有 accepted QA、MERGE 已有 fresh target readback，然後由 trusted FINALIZE path 自己 fresh-read GitHub Issue：

1. Issue 若仍 open，立即以 state=`closed`、state_reason=`completed` 關閉；不得把「PR 已 merge」當作 Issue 已 close。
2. close 後必須再次 fresh-read GitHub Issue；只有 `state=closed + state_reason=completed` 才能產生 closure evidence。
3. caller 傳入的 `issue_closed=true` 不具 authority，trusted writer 必須以 GitHub fresh readback 覆寫。
4. close/readback 失敗、Issue 仍 open、state_reason 非 completed、QA/merge identity 不符時，FINALIZE 必須 fail closed；ExecutionRecord 保持 nonterminal，不得寫 DONE。
5. Issue 已 closed/completed 時仍必須 fresh-read確認，不得因為舊 comment、PR body 的 `Closes #N`、或 default/non-default branch 自動關單假設而跳過。
6. 只有 hard gate 成功後，才把 record寫成 DONE、清 lease/owner、next_action=null並保存 closure evidence。

因此「merge + acceptance 完成但 Issue 還開著」不是合法 terminal；同一 FINALIZE 必須把 Issue 收乾淨並 readback。

## Legacy compatibility

2026-09-28 前的舊 coordination、prewrite、heartbeat/end、separate finalization 與 turn-exit artifacts只作 audit/migration evidence。保留 workflow 已 fail-closed，不得重新啟用成 execution authority。

## Progress

進度/status是 non-blocking checkpoint。scheduler/長任務第一行固定：
`【處理者：<handler>｜owner=<record owner|NONE>｜工單：#<issue|NONE>】`
回報後只要 current invocation 還能合法施工，就立即繼續。

## Production transaction transport

<!-- FLOW_V2_PRODUCTION_TRANSACTION_V2 -->

Scheduler runtime 的 canonical mutation ingress 是 **push request**，不是 workflow_dispatch。

- A request branch: `coord/transaction-requests-a`
- B request branch: `coord/transaction-requests-b`
- request path: `.dispatch/transaction-request.json`
- trusted push workflow: `.github/workflows/whd-control-transaction-v2-request.yml`
- trusted writer: `tools/control_transaction_request_ingress.py` → `tools/control_transaction_production_executor.py`

每次需要 ACQUIRE/ACCEPT_QA/MERGE/FINALIZE/YIELD 等 transaction：
1. fresh-read `coord/execution-v2` exact HEAD 與 native record generation。
2. 本 lane request branch 必須已存在 `.dispatch/transaction-request.json` bootstrap seed；fresh-read 其 blob SHA，scheduler 只允許 CAS update，禁止在 runtime 走首次 `create_file`。若 seed 缺失，fail closed 並交由治理/bootstrap 修復。
3. 寫 `WHD_CONTROL_TRANSACTION_PUSH_REQUEST_V1`：
   - request_id：本 invocation/action 唯一值
   - issue / kind / lane_id / invocation_identity
   - expected_coord_head：步驟1 fresh HEAD
   - expected_generation：步驟1 record.generation
   - effect：fresh external readback payload
4. 記住 request commit SHA；push 會自動觸發 request workflow。
5. 只接受 event=push、workflow=`whd-control-transaction-v2-request.yml`、head_sha=request commit SHA 的 exact run。
6. 鎖 exact run 到 terminal；success 後 fresh-read `coord/execution-v2`，必須看到 generation+1、transaction.status=RECONCILED 與 expected post state。
7. CONFLICT/FAILED 時 fresh-read重算；不得 replay 舊 request/effect。

`coord/transaction-requests-a` / `coord/transaction-requests-b` 的 seed 使用同一 request schema、`kind=SEED`、`issue=0`；trusted ingress 必須回 `APPLIED / SEED_NOOP` 且不得讀寫 `coord/execution-v2`。seed 只負責確保後續 scheduler mutation 永遠走 existing-file CAS。\n\n`lease=null` 的 same-lane nonterminal record必須先送 ACQUIRE request（effect=`{}`），成功後同一 invocation 立即續原 structured next_action。

POLL_QA 是 observation。exact QA terminal success後，先 fresh-read run/head，再送 ACCEPT_QA request。PR merge 仍是 GitHub external side effect：merge前驗 exact PR identity，merge後 fresh-read target SHA，再送 MERGE request。FINALIZE由 trusted production writer自行 close/readback Issue；request workflow固定具有 `issues: write`。

手動 `whd-control-transaction-v2.yml` 只保留管理/診斷用途；scheduler不得依賴 connector 未提供的 workflow_dispatch。
