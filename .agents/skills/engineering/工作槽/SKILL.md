---
name: 工作槽
description: 固定 /工作1、/工作2、/工作3 routing/projection 入口。slot 不擁有獨立狀態，全部由 Flow v2 ExecutionRecord.slot_id 投影。
whd_doc_role: MIRROR
whd_contract: work-slot-routing
whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md
whd_schema: WHD_DOC_META_V1
---

# 工作槽

<!-- FLOW_V2_EXECUTION_BRIDGE_V1 -->

本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

## Slot
裸工作槽指令只查 projection，不取得 authority。指派使用 explicit READY ingress；繼續讀該 slot record；接手走 atomic ACQUIRE/HANDOFF；交給排程或收回互動只改 owner/routing/lease並保留 slot_id。不得建立第二套 slot/handoff state。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。
