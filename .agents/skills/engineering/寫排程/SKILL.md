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
A/B prompt固定只描述 lane owner、entrypoint、fresh-read `coord/execution-v2`、same-lane-first、lease、structured next_action、atomic transaction、YIELD、generation fencing與 recurring lifecycle。
修改時保留 title/entrypoint/lane owner/cadence，除非使用者明確要求。update後 fresh-read exact automation。單輪 task terminal不代表 recurring automation terminal。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。
