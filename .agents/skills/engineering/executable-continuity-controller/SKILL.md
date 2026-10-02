---
name: executable-continuity-controller
description: Flow v2 長任務／runtime interruption／remote QA resume bridge。continuity 只讀 native ExecutionRecord、lease 與 structured next_action。
whd_doc_role: MIRROR
whd_contract: continuous-execution-operations
whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md
whd_schema: WHD_DOC_META_V1
---

# executable-continuity-controller

<!-- FLOW_V2_EXECUTION_BRIDGE_V1 -->

### EXECUTION_ENTRY_AUTH_PURPOSE_BRIDGE_V1

此入口只 bridge 到 canonical `tools/execution_entry_contract.py` 與 `flow-v2-execution::PROJECT_STARTUP_HARD_GATE_V1`，不建立第二套 startup authority。每個新 invocation 在任何 substantive analysis、claim、Guard、repository mutation 或 workflow dispatch 前，必須重新 user-visible 產生 `WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1`，並完成 project Phase6 Preflight；不得以「已讀 Flow v2」或前一 runtime declaration 代替。


本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

## Continuity
fresh runtime、stream interruption、scheduled/work-slot re-entry或 durable reconnect：fresh-read `coord/execution-v2`，驗 generation/branch/head/lease/active_run/next_action；live lease退讓，可resume時 atomic reacquire；active remote run只poll exact run；task未terminal而runtime到邊界時 YIELD。status/reconstruction不是停止點。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。
