---
name: 排程模擬
description: WHD A/B recurring scheduler lane 與 /排程A、/排程B same-lane resume 入口。只透過 Flow v2 ExecutionRecord、lease/YIELD 與 structured next_action 執行。
whd_doc_role: MIRROR
whd_contract: scheduler-interactive-lane-resume
whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md
whd_schema: WHD_DOC_META_V1
---

# 排程模擬

<!-- FLOW_V2_EXECUTION_BRIDGE_V1 -->

### EXECUTION_ENTRY_AUTH_PURPOSE_BRIDGE_V1

此入口只 bridge 到 canonical `tools/execution_entry_contract.py` 與 `flow-v2-execution::PROJECT_STARTUP_HARD_GATE_V1`，不建立第二套 startup authority。每個新 invocation 在任何 substantive analysis、claim、Guard、repository mutation 或 workflow dispatch 前，必須重新 user-visible 產生 `WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1`，並完成 project Phase6 Preflight；不得以「已讀 Flow v2」或前一 runtime declaration 代替。


本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

## Lane identity
- A owner=`scheduler.6ab13fa557fc8191935c671214b865e2`；entrypoints=`00/20/40`。
- B owner=`scheduler.e58ea936e7d0b12bd0d475314709d6f1`；entrypoints=`B15/B45`。
- entrypoint 不是 owner；scheduled 與 interactive resume 必須保存真實 invocation provenance。

### SCHEDULER_STARTUP_BOOTSTRAP_READ_ONLY_DISCOVERY_V1

若新 scheduler invocation 在 project startup 階段還不知道 exact owning Issue，先依 canonical Flow v2 做 `READ_ONLY_BOOTSTRAP_ONLY`：只讀 `coord/execution-v2`、derived ready-index、`tools/execution_scheduler_view.py` scheduler projection 與 Issue/branch/HEAD identity，用來綁 trusted Phase6 Preflight request。此 bootstrap projection 不得授權 WAKE、HEARTBEAT、claim、ACQUIRE、transaction、Guard 或任何 mutation。

Preflight GREEN 且 required Skill/reference 全部 fresh-read 後，必須丟棄 bootstrap projection，再 fresh-read canonical scheduler state，才進入下面的 Wake。禁止建立永久 bootstrap Issue，也不得把這個 bridge 擴張成第二套 scheduler authority。

## Wake
每次 wake 先 fresh-read `coord/execution-v2`，優先 same-lane nonterminal record；其次才讀 derived ready-index。live lease退讓、expired lease走 atomic reacquire。沒有 current record且ready-index empty才可回 NO_EXECUTABLE_WORK。

`RESUME_CURRENT` 若先 ACQUIRE，ACQUIRE 後同一 invocation 必須立即 fresh-read並執行原 exact `next_action`；不得把拿到 lease 當 progress/停止點。`READY_CANDIDATES` 必須使用 scheduler view 的 deterministic `selected_issue` 立即 ACQUIRE；race/conflict後 fresh-read重選。

正常 return 前必須通過 canonical `SCHEDULER_CYCLE_PROGRESS_HARD_GATE_V1`：WAKE/讀取/回報/HEARTBEAT/單獨 ACQUIRE 都不算 substantive progress。只有 DONE、LANE_BUSY、合法 BLOCKED、active remote QA wait，或本 invocation 已完成 substantive transaction 後的合法 YIELD 可離開；`SCHEDULER_EXECUTION_NO_PROGRESS` 必須繼續施工，不得停止。

## Lifecycle
不得自行 disable/delete/complete/reschedule自己或 sibling。cadence與 lane owner只由 host automation config管理。

### HOST_LIFECYCLE_WATCHDOG_V1 bridge

scheduler invocation 在 project startup hard gate 完成後、寫 WAKE 前，可且應執行 **read-only host lifecycle inspection**，取得 A00/A20/A40/B15/B45 的 task `enabled / last_run_time`，並以 NON_AUTHORITY snapshot CAS 更新 `coord/monitor-v2:.dispatch/monitor/host/chatgpt-automations.json`。此為唯一 read-only automation introspection 例外；禁止任何 lifecycle mutation API。

每個 entrypoint 必須把自己的 WAKE/HEARTBEAT/PROGRESS/EXIT 同步 mirror 到 exact entrypoint observation file，使用 canonical `WHD_SCHEDULER_ENTRYPOINT_OBSERVATION_V1`。host snapshot 與 entrypoint mirror 都只是 observability，不可當 claim/lease/transaction authority。

GitHub independent watchdog `whd-scheduler-host-watchdog.yml` 每 5 分鐘獨立檢查 expected occurrence；120 秒 grace 後沒有 durable WAKE 即 fail-visible，並依 fresh host snapshot分類 `HOST_ENTRY_FAILURE / HOST_AUTO_PAUSE / HOST_STATE_UNKNOWN`。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。


## TASK_START_AUTHORITY_DECLARATION_V1_BRIDGE

本入口只 bridge 到 `執行開發任務::TASK_START_AUTHORITY_DECLARATION_V1` 與 canonical `tools/execution_entry_contract.py`，不得建立第二套 startup authority。

對 `SCHEDULER_LANE`，startup declaration 必須先於任何 claim 或 mutation，並明確保留本 invocation 的 lane/entrypoint provenance；若沒有已成立的 durable resume authority，`resume_authority=NONE`。
