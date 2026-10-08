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

### EXECUTION_ENTRY_AUTH_PURPOSE_BRIDGE_V1

此入口只 bridge 到 canonical `tools/execution_entry_contract.py` 與 `flow-v2-execution::PROJECT_STARTUP_HARD_GATE_V1`，不建立第二套 startup authority。每個新 invocation 在任何 substantive analysis、claim、Guard、repository mutation 或 workflow dispatch 前，必須重新產生 `WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1` 並依 runtime surface 留 startup communication evidence：interactive chat=`USER_VISIBLE_CHAT`；Codex/CLI/headless/scheduler=`STDOUT / TASK_EVENT / LOG` machine-visible `WHD_EXECUTION_STARTUP_COMMUNICATION_V1`。缺少 chat UI 或 AI Library surface 本身不得成為 blocker；之後完成 project Phase6 Preflight。不得以「已讀 Flow v2」或前一 runtime declaration 代替。


本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

## Authoring
A/B prompt固定描述 lane owner、entrypoint、project startup hard gate、fresh-read `coord/execution-v2`、same-lane-first、lease、structured next_action、atomic transaction、YIELD、generation fencing、`SCHEDULER_CYCLE_PROGRESS_HARD_GATE_V1` 與 recurring lifecycle。每個 fresh invocation 必須先產生 `WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1` 並依 runtime surface留下 startup communication：interactive chat=user-visible；scheduler/headless=machine-visible。每個 non-SEED transaction request 必須帶 canonical `startup_evidence`，exact 綁本 invocation_identity，過期或跨 invocation 不得重用。
prompt 必須明寫：A/B scheduler 先找同 lane/Issue/branch/HEAD、40 分鐘內的 trusted push GREEN receipt並用 `WHD_SCHEDULER_PHASE6_PREFLIGHT_RECEIPT_REF_V1` 續接；只有無 eligible receipt 才走 `coord/preflight-requests-a|b:.dispatch/preflight-request.json` existing-file CAS + trusted push workflow。**不得自行 create Phase6 Issue request comment，也不得有可 consume GREEN 時重複 mint Preflight**；scheduler view 順序固定 same-lane current → `TAKEOVER_CANDIDATE` → READY → explicit ingress；`TAKEOVER_CANDIDATE` 必須對 deterministic `selected_issue` 執行 HANDOFF→fresh-read→ACQUIRE→exact next_action，且 HANDOFF/ACQUIRE 都不是 progress/停止點；READY_CANDIDATES 使用 deterministic selected_issue；正常 return 前若 machine decision 為 `SCHEDULER_EXECUTION_NO_PROGRESS / CONTINUE_EXECUTION / ACQUIRE_REQUIRED`，同一 invocation 必須繼續 exact next_action，不得回報後停止。
修改時保留 title/entrypoint/lane owner/cadence，除非使用者明確要求。update後 fresh-read exact automation。單輪 task terminal不代表 recurring automation terminal。


### ISSUE_COMMENT_PROGRESS_AND_INTERVENTION_BRIDGE_V1

每個 A/B scheduler 在 native ACQUIRE 成功後**立即**向 owning GitHub Issue 發布具 `WHD_ISSUE_OWNER_PROGRESS_V1` 的接取者留言；執行中每 10 分鐘於同一 Issue 發布有效 `PROGRESS`，含身份、已完成、正在進行、障礙與下一步。這是 Issue-plane action（非 Phase6 preflight request comment），只能在 Preflight/admission/claim 成功且該 Issue COMMENT authority 存在時進行。COMMENT API write 後應 readback server-created timestamp。

`TAKEOVER_CANDIDATE` 必須 fresh-fetch Issue comments 並傳入 `tools/execution_scheduler_view.py::build_scheduler_view(issue_comments=..., trusted_comment_authors=...)`。未讀留言、有效留言 <=600 秒均不得介入；只有 **>600 秒**才產生候選，交易仍用 native CAS。舊的 heartbeat/lease/END/active run/family liveness 不得另設介入時間判斷；不改 A00/A20/A40/B15/B45 cadence、enabled 與 owner identity。每輪 return 不等於取消後續 progress 責任。

## REPORT_HANDLER_IDENTITY_PREFIX_V1

所有生成或修復的 recurring **scheduler prompt** 都必須保留以下 user-visible **第一行** contract，且 progress / CHECKPOINT / terminal / exit 全部適用：

`【處理者：<handler>｜owner=<exact owner|NONE>｜工單：#<issue|NONE|UNBOUND>｜slot=<worker.slot.N|NONE|UNBOUND>｜invocation_identity=<exact invocation_identity>】`

- machine owner 固定為 `tools/runtime_report_identity.py`；所有 progress / CHECKPOINT / terminal / exit 必須先經 `build_runtime_report_identity(...)` 驗完整 identity，再由 `format_runtime_report_prefix(..., event=...)` 產生第一行。生成的 scheduler prompt 必須要求 `TERMINAL/EXIT` 使用 current `WHD_FLOW_V2_HOST_EXIT_PROOF_V1`，並由 formatter fresh revalidate；`may_return=false`、缺 proof 或 stale proof 不得正常結束 invocation。progress/CHECKPOINT 不是 exit authority。缺欄、空白或 invocation_identity=`NONE/UNBOUND/UNAVAILABLE` 一律 fail closed；不得手工拼 prefix 冒充合法回報。

相容核心模板：`【處理者：<handler>｜owner=<exact owner|NONE>｜工單：#<issue|NONE|UNBOUND>】`。

- prompt 必須明寫從 fresh durable state 取得 lane owner、active Issue、claim owner 與 slot；不得把 prompt 內靜態文字當 runtime identity。
- 每個 progress / CHECKPOINT 都要重用 fresh identity；handoff/ACQUIRE 後下一次回報必須立即反映新 owner。
- prompt 必須要求輸出本輪 exact `invocation_identity`；禁止沿用上一輪 invocation、用排程 task id/entrypoint/時間字串猜 invocation identity。
- 產生或更新 scheduler prompt 時不得刪除本 section / marker / template；contract test 會 fail closed。
- 此 prefix 只做 provenance，**不建立 execution authority**；ownership 仍由 Flow v2 canonical state machine 決定。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。


## TASK_START_AUTHORITY_DECLARATION_V1_BRIDGE

本入口只 bridge 到 `執行開發任務::TASK_START_AUTHORITY_DECLARATION_V1` 與 canonical `tools/execution_entry_contract.py`，不得建立第二套 startup authority。
