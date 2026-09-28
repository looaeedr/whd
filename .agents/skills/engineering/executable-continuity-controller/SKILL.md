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

本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

## Continuity
fresh runtime、stream interruption、scheduled/work-slot re-entry或 durable reconnect：fresh-read `coord/execution-v2`，驗 generation/branch/head/lease/active_run/next_action；live lease退讓，可resume時 atomic reacquire；active remote run只poll exact run；task未terminal而runtime到邊界時 YIELD。status/reconstruction不是停止點。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。
