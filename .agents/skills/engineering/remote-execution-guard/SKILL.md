---
name: 遠端執行守門
description: Flow v2 remote mutation compatibility入口。舊式中間授權 protocol已退役；新的遠端 mutation 只接受 atomic transaction terminal result。
whd_doc_role: MIRROR
whd_contract: remote-execution-guard
whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md
whd_schema: WHD_DOC_META_V1
---

# 遠端執行守門

<!-- FLOW_V2_EXECUTION_BRIDGE_V1 -->

本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

## Retired compatibility
此名稱只為舊引用相容，不得 mint/consume/恢復舊式中間授權。新的 remote mutation直接使用 Flow v2 transaction request，綁 expected generation/fingerprint/head/target；結果只能 APPLIED、CONFLICT、FAILED。缺 trusted capability時分類 MISSING_CAPABILITY並 fail closed。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。
