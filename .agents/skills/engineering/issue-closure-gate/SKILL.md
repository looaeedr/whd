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

本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

## Closure
QA PASS或merge不等於完成。FINALIZE驗 target/merge/accepted QA，close Issue後fresh-read，再把同一 record寫成 DONE、清 lease/owner、next_action=null並保存 closure evidence。successor只由record.chain structured fields決定。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。
