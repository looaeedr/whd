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

`worker.slot.1/2/3` 只是 routing/projection tag，沒有獨立 state database。HANDOFF 只能變更 owner/routing/lease，不得順手改 branch/head/slot/next_action。

## Generation fencing + salvage

偵測到可能仍存活的舊 writer時：bump generation、換 canonical branch、綁 exact base/head/fingerprint。舊 generation後續寫入=`ORPHAN_WRITE`，不可直接 merge/accept。舊成果仍可 freeze donor HEAD 後分類 `ADOPTABLE / PARTIAL / STALE_CONFLICT`；可用部分收編到 current generation，只重做不能證明相容的部分。

## Remote QA

START_QA 綁 exact head；同 record/head只允許一個 active run。active只 POLL_QA；success→ACCEPT_QA；failure→structured repair/reconcile action。

## Blocker

只有 `EXTERNAL_DEPENDENCY / MISSING_CAPABILITY / AUTHORITY_DENIED / PLATFORM_FAILURE` 可進 BLOCKED。一般 poll/readback/reconcile/retry不是 blocker。

## Finalization

FINALIZE 驗 merge/target/QA，close Issue後 fresh-read，再把 record寫成 DONE、清 lease/owner、next_action=null並保存 closure evidence。

## Legacy compatibility

2026-09-28 前的舊 coordination、prewrite、heartbeat/end、separate finalization 與 turn-exit artifacts只作 audit/migration evidence。保留 workflow 已 fail-closed，不得重新啟用成 execution authority。

## Progress

進度/status是 non-blocking checkpoint。scheduler/長任務第一行固定：
`【處理者：<handler>｜owner=<record owner|NONE>｜工單：#<issue|NONE>】`
回報後只要 current invocation 還能合法施工，就立即繼續。

## Production transaction transport

<!-- FLOW_V2_PRODUCTION_TRANSACTION_V1 -->

production state mutation 的 trusted writer 是 `.github/workflows/whd-control-transaction-v2.yml`，實作者為 `tools/control_transaction_production_executor.py`。

scheduler/interactive runtime 不可直接手寫 `coord/execution-v2`。需要 ACQUIRE/ACCEPT_QA/MERGE/FINALIZE/YIELD 等 state transition 時：
1. fresh-read native record / exact external readback。
2. dispatch `whd-control-transaction-v2.yml`，輸入 exact issue、kind、lane_id、invocation_identity、effect_json。
3. 鎖定該 workflow run 到 terminal。
4. success 後 fresh-read `coord/execution-v2`，必須看到 generation +1、transaction.status=RECONCILED 與 exact next_action/state。
5. CONFLICT/FAILED 時重新 fresh-read，不得 replay 舊 effect。

`lease=null` 的 same-lane nonterminal record：先 dispatch ACQUIRE（effect_json 可為 `{}`），readback成功後在同一 scheduler invocation 繼續原 next_action。

POLL_QA 是 observation，不直接 mutation。若 exact run terminal success，先 fresh-read run/head，再以 ACCEPT_QA transaction 寫入 QA acceptance與下一個 MERGE action。MERGE/FNALIZE 的外部 GitHub side effect 必須先做 fresh readback，再把該 readback作 effect_json交給 production transaction writer。
