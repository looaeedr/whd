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

### EXECUTION_ENTRY_AUTH_PURPOSE_BRIDGE_V1

此入口只 bridge 到 canonical `tools/execution_entry_contract.py` 與 `flow-v2-execution::PROJECT_STARTUP_HARD_GATE_V1`，不建立第二套 startup authority。每個新 invocation 在任何 substantive analysis、claim、Guard、repository mutation 或 workflow dispatch 前，必須重新產生 `WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1` 並依 runtime surface 留 startup communication evidence：interactive chat=`USER_VISIBLE_CHAT`；Codex/CLI/headless/scheduler=`STDOUT / TASK_EVENT / LOG` machine-visible `WHD_EXECUTION_STARTUP_COMMUNICATION_V1`。缺少 chat UI 或 AI Library surface 本身不得成為 blocker；之後完成 project Phase6 Preflight。不得以「已讀 Flow v2」或前一 runtime declaration 代替。


本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。


### REMOTE_AUTHORITY_NON_PROPAGATION_BRIDGE_V1

Machine validation 仍固定經 `tools/root_local_first_gate.py::assert_remote_connection_allowed(...)`，authority schema=`WHD_REMOTE_CONNECTION_AUTHORITY_V1`；同 scope 沿用/自動 mint 只是不重問使用者，**不是 bypass machine gate**。

派工/READY/ACQUIRE/owning Issue 語意本身不會憑空產生 GitHub network authority；但**使用者已明確要求執行 exact GitHub Issue/ticket** 時，該 user instruction 就是 `USER_EXPLICIT_REMOTE` 的來源，可由 machine 一次 mint 本 task 所需的 exact `ISSUE_READ / ISSUE_COMMENT / READBACK` 等 actions，並在同 invocation/task scope 內沿用；不得再向使用者重問同一授權。`coord/execution-v2` 的 baseline branch/read metadata仍服從 workspace baseline read policy。只有 scope 擴張、不同 repository/Issue 或額外 remote action 才需新的 explicit authority。


### EXPLICIT_ISSUE_DIRECT_EXECUTION_V1_BRIDGE

使用者若已明確輸入 `/接手 <issue>`、`/接手 #<issue>` 或等價 exact Issue 指令，固定 bridge 到 canonical `flow-v2-execution::EXPLICIT_ISSUE_DIRECT_EXECUTION_V1`：

- 不做 open Issue / READY / scheduler view / takeover candidate discovery；
- 只 fresh-read該 exact Issue、same-Issue ExecutionRecord、live refs/HEAD 與 required Preflight；
- record 缺失時只補同一 Issue 的 explicit ingress，不得改找別張；
- admission後立即施工／resume exact structured `next_action`，不得停在「找到工單／ACQUIRE 完成」。
- interactive `/接手 <issue>` 的實作固定 **Remote Desktop Commander（RC）→ 使用者本機 `/workspace/whd`**；不得在雲端 executor 私有 workspace 實作後只留未 push 狀態。
- Remote Desktop Commander（RC）本機實作完成後至少要形成該 Issue 可追蹤的 Git branch + commit；需交付時 push/PR，讓下一個執行器可見。RC/本機 root 不可用時回 `LOCAL_MACHINE_UNAVAILABLE`，禁止 cloud-workspace fallback。

只有**沒有指定 exact Issue**的自動派工／scheduler 才可進 candidate discovery。


### DISPATCH_LOCAL_MACHINE_PROHIBITION_HARD_GATE_V1

`/派工` 是 **GitHub canonical control-plane only** 入口。自進入 `/派工` 到 Issue sync / dependency readback / slot projection / Phase6 Preflight / READY ingress / ACQUIRE 與 control-plane readback 完成為止，固定禁止把使用者本機或任何 local execution surface 當作 evidence、fallback 或 transport。

硬規則：

- 禁止呼叫或依賴 Remote Desktop Commander（RC）、host/local shell、local repo/worktree、`/workspace/whd`、Windows 本機路徑或任何本機檔案來做派工判定、Preflight、slot/READY、claim 或 control-plane mutation。
- 上述派工階段只可使用 GitHub Issue/PR/Actions、`coord/execution-v2`、canonical request branches/workflows 與其他 Flow v2 明定的 GitHub durable surfaces。
- GitHub canonical capability 暫時不可用時，固定 fail closed / 回 capability blocker；**不得 fallback 到本機**。
- 唯一 RC 例外是使用者明確輸入 `/接手 <issue>`、`/接手 #<issue>` 或等價 exact-Issue takeover 指令後，依 `EXPLICIT_TAKEOVER_RC_WORKSPACE_V1` 進入 **repository-content implementation**。這是另一個 entrypoint，不是 `/派工` 的 fallback。
- `/派工` 不得借用上述 `/接手` 例外先碰本機再回來建立 READY；即使 exact Issue 已知，dispatch control plane 仍須留在 GitHub canonical。
- machine gate owner=`tools/execution_dispatch_ingress.py::validate_dispatch_transport`；READY request 的 `dispatch_transport` 只接受 `GITHUB_CANONICAL`。

## Dispatch
open Issue、dependency-unblocked、空工作槽都不等於 execution authority。新工作必須由 `tools/execution_dispatch_ingress.py` 以明確 authority建立 READY record，再由 ACQUIRE transaction取得 owner/lease。互動式新工作未指定 slot 時仍以 `/工作0` / `worker.slot.0` 為既有預設；建立 READY 前若 fresh-read 發現 slot0 已 BOUND，才使用 `tools/execution_work_slot_view.py::select_first_available_work_slot(...)` 往 `1→2→3` overflow；全滿即 fail closed，不得搶槽。
PM/Implementer/QA只是角色視角；branch/head/owner/QA/closure/next_action只寫同一 native record。
UPDATE_ONLY只完成被點名更新與readback；EXECUTE_TICKET/CHAIN/SCHEDULER_LANE scope由使用者授權與record.chain決定。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。

### DRIVE_WORK_ROOT_WORDING_HARD_GATE_V1

任何 dispatch / handoff / 接手文字都不得再使用或生成以下語意：

- 「讀取專案指定的 Google Drive 工作根目錄」
- 「以 /Google Drive/WHD 作為施工 root / canonical work root」
- 「Drive mount 不可見所以 repository-content 工作 blocked」
- 「先讀 Drive 才能解析施工根或開始修改／測試」

CURRENT 固定語意：

- repository-content 施工根 = executor 自己的 repo workspace；
- fresh baseline = GitHub production X `cleanup/2d-3d-sync`；
- 先 fresh-read owning Issue / native ExecutionRecord / live refs，再依 Flow v2 續跑；
- Google Drive 僅在任務明確涉及 backup / mirror / disaster recovery data 時使用；
- Drive 不可見不得形成 startup/root blocker；
- 若沒有 native ExecutionRecord，判定為 execution-state / ingress 問題，不得改判成 Drive root 問題；
- 真正沒有可寫、可測 executor repo workspace 時，才 handoff 到 workspace-capable runtime。

推薦 handoff wording：

> 追加使用 flow-v2-execution 技能。讀取目標 Issue 的 fresh 接手／ExecutionRecord 狀態；repository-content 施工根依 CURRENT Flow v2 固定使用 executor 自己的 repo workspace，fresh 對齊 GitHub cleanup/2d-3d-sync。Google Drive 僅在本任務明確涉及備份／災難復原資料時使用；不得讀取 Drive 來解析施工 root、不得把 /Google Drive/WHD 當 startup gate，也不得因 Drive 未掛載而停止。



## TASK_START_AUTHORITY_DECLARATION_V1_BRIDGE

本入口只 bridge 到 `執行開發任務::TASK_START_AUTHORITY_DECLARATION_V1` 與 canonical `tools/execution_entry_contract.py`，不得建立第二套 startup authority。
