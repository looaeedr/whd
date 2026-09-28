---
name: 排程模擬
description: WHD A/B recurring scheduler lane 與 /排程A、/排程B same-lane resume 入口。只透過 Flow v2 ExecutionRecord、lease/YIELD 與 structured next_action 執行。
whd_doc_role: CURRENT
whd_contract: scheduler-interactive-lane-resume
whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md
whd_schema: WHD_DOC_META_V1
---

# 排程模擬

<!-- FLOW_V2_EXECUTION_BRIDGE_V1 -->

本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

## Lane identity
- A owner=`scheduler.6ab13fa557fc8191935c671214b865e2`；entrypoints=`00/20/40`。
- B owner=`scheduler.e58ea936e7d0b12bd0d475314709d6f1`；entrypoints=`B15/B45`。
- entrypoint 不是 owner；scheduled 與 interactive resume 必須保存真實 invocation provenance。

## Wake
每次 wake 先 fresh-read `coord/execution-v2`，優先 same-lane nonterminal record；其次才讀 derived ready-index。live lease退讓、expired lease走 atomic reacquire。沒有 current record且ready-index empty才可回 NO_EXECUTABLE_WORK。runtime 邊界用 YIELD。

## Lifecycle
不得自行 disable/delete/complete/reschedule自己或 sibling。cadence與 lane owner只由 host automation config管理。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。
