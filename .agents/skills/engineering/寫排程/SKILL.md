---
name: 寫排程
description: 建立、修改與修復 WHD recurring scheduler automation。prompt 必須是 Flow v2 wake/resume bridge，不得內嵌第二套 execution state machine。
whd_doc_role: MIRROR
whd_contract: scheduler-authoring
whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md
whd_schema: WHD_DOC_META_V1
---

# 寫排程

<!-- FLOW_V2_EXECUTION_BRIDGE_V1 -->

本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

## Authoring
A/B prompt固定只描述 lane owner、entrypoint、fresh-read `coord/execution-v2`、same-lane-first、lease、structured next_action、atomic transaction、YIELD、generation fencing、`SCHEDULER_CYCLE_PROGRESS_HARD_GATE_V1` 與 recurring lifecycle。
prompt 必須明寫：ACQUIRE 不是 progress/停止點；READY_CANDIDATES 使用 deterministic selected_issue；正常 return 前若 machine decision 為 `SCHEDULER_EXECUTION_NO_PROGRESS / CONTINUE_EXECUTION / ACQUIRE_REQUIRED`，同一 invocation 必須繼續 exact next_action，不得回報後停止。
修改時保留 title/entrypoint/lane owner/cadence，除非使用者明確要求。update後 fresh-read exact automation。單輪 task terminal不代表 recurring automation terminal。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。
