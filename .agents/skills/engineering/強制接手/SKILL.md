---
name: 強制接手
description: 使用者明確要求接手既有 WHD 工作時使用。Flow v2 以 generation fencing + atomic owner transition處理，不直接覆寫 foreign runtime。
whd_doc_role: CURRENT
whd_contract: user-directed-force-takeover
whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md
whd_schema: WHD_DOC_META_V1
---

# 強制接手

<!-- FLOW_V2_EXECUTION_BRIDGE_V1 -->

本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

## Takeover
先fresh-read native record與lease。foreign live lease無明確失效證據則fail closed；expired/orphan runtime以atomic ACQUIRE/HANDOFF/RECONCILE轉移。無法安全判斷舊writer時bump generation+新canonical branch。superseded generation成果先當donor，可證明相容就收編。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。
