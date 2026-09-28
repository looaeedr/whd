---
name: 派工
description: WHD PM→Implementer→QA 與 execution routing 入口。新工作只透過 explicit READY ingress 建立 Flow v2 ExecutionRecord。
whd_doc_role: MIRROR
whd_contract: dispatching-workflow
whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md
whd_schema: WHD_DOC_META_V1
---

# 派工

<!-- FLOW_V2_EXECUTION_BRIDGE_V1 -->

本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

## Dispatch
open Issue、dependency-unblocked、空工作槽都不等於 execution authority。新工作必須由 `tools/execution_dispatch_ingress.py` 以明確 authority建立 READY record，再由 ACQUIRE transaction取得 owner/lease。互動式新工作未指定 slot 時仍以 `/工作0` / `worker.slot.0` 為既有預設；建立 READY 前若 fresh-read 發現 slot0 已 BOUND，才使用 `tools/execution_work_slot_view.py::select_first_available_work_slot(...)` 往 `1→2→3` overflow；全滿即 fail closed，不得搶槽。
PM/Implementer/QA只是角色視角；branch/head/owner/QA/closure/next_action只寫同一 native record。
UPDATE_ONLY只完成被點名更新與readback；EXECUTE_TICKET/CHAIN/SCHEDULER_LANE scope由使用者授權與record.chain決定。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。
