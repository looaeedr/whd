---
name: 執行開發任務
description: 依核准規格／工單執行實作的 Flow v2 入口。execution intent轉成 native READY/ACTIVE record，不使用平行 ownership state。
whd_doc_role: CURRENT
whd_contract: development-task-execution
whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md
whd_schema: WHD_DOC_META_V1
---

# 執行開發任務

<!-- FLOW_V2_EXECUTION_BRIDGE_V1 -->

本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

## Intent
UPDATE_ONLY只做指定更新與readback；EXECUTE_TICKET只做指定Issue並依structured chain續接；EXECUTE_CHAIN依record.chain連續施工；SCHEDULER_LANE交由A/B lane。
任何mutation前確認current generation、canonical branch/head與record fingerprint。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。
