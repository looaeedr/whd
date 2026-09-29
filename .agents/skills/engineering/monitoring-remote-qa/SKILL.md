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

此入口只 bridge 到 canonical `tools/execution_entry_contract.py` 與 `flow-v2-execution::PROJECT_STARTUP_HARD_GATE_V1`，不建立第二套 startup authority。每個**新 invocation** 在任何 substantive analysis、ExecutionRecord/lease mutation、repository mutation 或 workflow dispatch 前，必須重新 user-visible 產生 `WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1` 並完成 project Phase6 Preflight；同一 live invocation 的 continuation 依 Flow v2 session-reuse 規則，不把 startup gate重跑成每顆 transaction 的步驟。


本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

## Remote QA
**先 fresh-read 是否已有 exact-head terminal GREEN**：若有且符合 canonical fast-path 前置條件，直接 `CONSUME_QA` 一顆完成接受與 continuation；不得再繞 `START_QA → ACCEPT_QA`。只有沒有可消費 terminal GREEN、必須真的啟動新 run 時，才 `START_QA` 建 exact run/head；active期間只 `POLL_QA` 不重送，success→`ACCEPT_QA`，failure→`FAIL_QA`/structured repair。大型 log 用 artifact/pointer，不把 log prose 當 authority。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。
