---
name: monitoring-remote-qa
description: Flow v2 remote CI/QA 監控入口。只追 ExecutionRecord.active_run 的 exact run/head，terminal結果回寫同一 record。
whd_doc_role: MIRROR
whd_contract: remote-qa-monitoring
whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md
whd_schema: WHD_DOC_META_V1
---

# monitoring-remote-qa

<!-- FLOW_V2_EXECUTION_BRIDGE_V1 -->

### EXECUTION_ENTRY_AUTH_PURPOSE_BRIDGE_V1

此入口只 bridge 到 canonical `tools/execution_entry_contract.py` 與 `flow-v2-execution::PROJECT_STARTUP_HARD_GATE_V1`，不建立第二套 startup authority。每個**新 invocation** 在任何 substantive analysis、ExecutionRecord/lease mutation、repository mutation 或 workflow dispatch 前，必須重新產生 `WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1` 並依 runtime surface 留 startup communication evidence：interactive chat=`USER_VISIBLE_CHAT`；Codex/CLI/headless/scheduler=`STDOUT / TASK_EVENT / LOG` machine-visible `WHD_EXECUTION_STARTUP_COMMUNICATION_V1`。缺 chat UI/AI Library surface 不得成為 blocker；之後完成 project Phase6 Preflight。同一 live invocation 的 continuation 依 Flow v2 session-reuse 規則，不把 startup gate重跑成每顆 transaction 的步驟。

本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

## Remote QA

### REMOTE_AUTHORITY_GATE_V1

Machine validation 仍固定經 `tools/root_local_first_gate.py::assert_remote_connection_allowed(...)`，authority schema=`WHD_REMOTE_CONNECTION_AUTHORITY_V1`；同 scope 沿用/自動 mint 只是不重問使用者，**不是 bypass machine gate**。

任何 GitHub Actions workflow/run/job/artifact status read 都是 GitHub network action，但同一已授權 repository-content task 的 `WORKSPACE_DELIVERY` 固定包含 `WORKFLOW_READ / REMOTE_QA`；因此 Codex/workspace executor 在 push/PR 後必須直接沿同 scope做 QA read/consume，不得再要求使用者第二次授權。`/推推` delivery authority與 user-authored GitHub-only scheduler authority也可包含這些 actions。只有沒有任何適用 authority、scope 擴張或跨 repository時才 `REMOTE_CONNECTION_DENIED`。


### REMOTE_QA_NONBLOCKING_WAIT_HARD_GATE_V1

本 mirror 不建立第二套 QA state machine；active wait 規則直接服從 canonical Flow v2：同一 `issue + run_id + head_sha` 若仍為 `queued / in_progress / pending / waiting / requested`，同一 invocation 依合理 cadence **持續輪詢** structured run/job/status，classifier 固定回 `CONTINUE_REMOTE_QA_POLL`。第一次看到 terminal 後立即停止 status polling：success→`CONSUME_QA / ACCEPT_QA`，terminal non-success→`FAIL_QA`。terminal observation 之後若再讀第二次相同 run/job/status，固定由 `assert_remote_qa_active_observation_budget` fail closed 為 `REMOTE_QA_TERMINAL_REOBSERVATION_FORBIDDEN`。

<!-- REMOTE_QA_NONBLOCKING_WAIT_HARD_GATE_V1 -->
**先 fresh-read 是否已有 exact-head terminal GREEN**：若有且符合 canonical fast-path 前置條件，直接 `CONSUME_QA` 一顆完成接受與 continuation；不得再繞 `START_QA → ACCEPT_QA`。只有沒有可消費 terminal GREEN、必須真的啟動新 run 時，才 `START_QA` 建 exact run/head；active期間只 `POLL_QA` 不重送，success→`ACCEPT_QA`，failure→`FAIL_QA`/structured repair。大型 log 用 artifact/pointer，不把 log prose 當 authority。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。
