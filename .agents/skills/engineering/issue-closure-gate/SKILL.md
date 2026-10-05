---
name: issue-closure-gate
description: Flow v2 merge/acceptance/Issue closure bridge。完成只由 FINALIZE transaction 與 native DONE record證明。
whd_doc_role: MIRROR
whd_contract: issue-closure
whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md
whd_schema: WHD_DOC_META_V1
---

# issue-closure-gate

<!-- FLOW_V2_EXECUTION_BRIDGE_V1 -->

### EXECUTION_ENTRY_AUTH_PURPOSE_BRIDGE_V1

此入口只 bridge 到 canonical `tools/execution_entry_contract.py` 與 `flow-v2-execution::PROJECT_STARTUP_HARD_GATE_V1`，不建立第二套 startup authority。每個新 invocation 在任何 substantive analysis、claim、Guard、repository mutation 或 workflow dispatch 前，必須重新產生 `WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1` 並依 runtime surface 留 startup communication evidence：interactive chat=`USER_VISIBLE_CHAT`；Codex/CLI/headless/scheduler=`STDOUT / TASK_EVENT / LOG` machine-visible `WHD_EXECUTION_STARTUP_COMMUNICATION_V1`。缺少 chat UI 或 AI Library surface 本身不得成為 blocker；之後完成 project Phase6 Preflight。不得以「已讀 Flow v2」或前一 runtime declaration 代替。


本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

## Closure

### REMOTE_AUTHORITY_GATE_V1

FINALIZE 的 execution authority 不等於 GitHub Issue network authority。若 closure 需要 GitHub Issue read/comment/close/readback，trusted executor 必須先用 `tools/root_local_first_gate.py::assert_remote_connection_allowed(...)` 驗 `WHD_REMOTE_CONNECTION_AUTHORITY_V1` 對 exact action 的允許；interactive/default 缺 remote authority 時不得因 FINALIZE/closure bridge 自動連 GitHub。`/推推` delivery window可包含 owning-Issue finalization actions；scheduler 則必須來自 user-authored GitHub-only entry contract。

QA PASS或merge不等於完成。FINALIZE驗 target/merge/accepted QA，close Issue後fresh-read，再把同一 record寫成 DONE、清 lease/owner、next_action=null並保存 closure evidence。successor只由record.chain structured fields決定。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。
