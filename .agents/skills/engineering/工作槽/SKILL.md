---
name: 工作槽
description: 固定 /工作0、/工作1、/工作2、/工作3 routing/projection 入口；/工作0 是預設互動入口，新工作遇到已佔用槽時由 0 起自動遞增到第一個空槽。slot 不擁有獨立狀態，全部由 Flow v2 ExecutionRecord.slot_id 投影。
whd_doc_role: MIRROR
whd_contract: work-slot-routing
whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md
whd_schema: WHD_DOC_META_V1
---

# 工作槽

<!-- FLOW_V2_EXECUTION_BRIDGE_V1 -->

本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

## WORK_SLOT_FIXED_IDENTITY_V2

固定對應：
- `/工作0` → `worker.slot.0`（預設互動入口）
- `/工作1` → `worker.slot.1`
- `/工作2` → `worker.slot.2`
- `/工作3` → `worker.slot.3`

不得動態重新編號；`worker.slot.N` 的 identity 永遠固定。`/工作0` 的自動 +1 只是一個「新工作 routing」選槽規則，不會改寫任何既有 record 的 slot_id；explicit `/工作1/2/3` 永遠優先於 default gate。

## DEFAULT_INTERACTIVE_WORK_SLOT_GATE_V1

使用者明確要求執行 ticket，但沒有寫 `/工作0/1/2/3`、也沒有指定排程 A/B 時，視為「從 `/工作0` 開始選槽」。這只是 routing default：真正 authority 仍必須來自 Flow v2 explicit READY ingress / ACQUIRE / HANDOFF。

## WORK_SLOT_AUTO_INCREMENT_FROM_ZERO_V1

對**新工作**使用 `/工作0`（或未指定工作槽而落到預設工作0）時，必須先 fresh-read canonical `coord/execution-v2`，用 `tools/execution_work_slot_view.py::select_first_available_work_slot(...)` 從 `worker.slot.0` 起找第一個 EMPTY：`0 → 1 → 2 → 3`。

- slot0 EMPTY → 使用 `worker.slot.0`。
- slot0 BOUND → 自動檢查 slot1；依序遞增到第一個 EMPTY。
- 0–3 全部 BOUND → fail closed，回 `NO_AVAILABLE_WORK_SLOT`；不得覆蓋、搶占、偷換 owner，也不得建立 duplicate slot occupancy。
- 選槽只發生在**建立新 READY record 前**；若該工單已有 nonterminal ExecutionRecord，必須 resume 原 record / 原 slot，不得因「有人」而跳槽。
- 裸 `/工作0` 狀態查詢仍然查 slot0，不自動跳到別槽。
- 明確 `/工作1`、`/工作2`、`/工作3` 是固定指定，不套用自動 +1。
- selection/readback 發生 drift 或 transaction conflict 時，必須 fresh-read 後重新選槽，不得沿用 stale 空槽判斷。

以下不套用預設工作0：
- 純狀態查詢、監控、列空槽；
- `/排程A`、`/排程B` 或 `SCHEDULER_LANE`；
- chain successor 已帶既有 `slot_id`；
- explicit `/工作1/2/3`。

## Query / execution

裸 `/工作0`、`/工作1`、`/工作2`、`/工作3` 只查 projection，不取得 authority。
`/工作槽` 可聚合顯示四槽狀態。

指派使用 explicit READY ingress；繼續讀該 slot record；接手走 atomic ACQUIRE/HANDOFF；交給排程或收回互動只改 owner/routing/lease並保留 slot_id。不得建立第二套 slot/handoff state。

## Observability

每次 `/工作0/1/2/3` runtime 依 canonical `WHD_RUNTIME_OBSERVABILITY_V1` 寫 `WAKE / PROGRESS / EXIT` 到 `coord/monitor-v2`。這些 observation 只供 whd-monitor/HA 顯示，絕對不能反向授權施工。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。
