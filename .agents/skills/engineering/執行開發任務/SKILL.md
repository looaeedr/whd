---
name: 執行開發任務
description: 依核准規格／工單執行實作的 Flow v2 入口。execution intent轉成 native READY/ACTIVE record，不使用平行 ownership state。
whd_doc_role: MIRROR
whd_contract: development-task-execution
whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md
whd_schema: WHD_DOC_META_V1
---

# 執行開發任務

<!-- FLOW_V2_EXECUTION_BRIDGE_V1 -->

## TASK_START_AUTHORITY_DECLARATION_V1

<!-- EXECUTION_ENTRY_AUTH_PURPOSE_BRIDGE_V1 -->

canonical machine owner 固定是 `tools/execution_entry_contract.py`，本 Skill 不建立第二套 authority。每一個新 invocation 都必須先完成 `AGENTS.md::SKILL_INVOCATION_ANNOUNCEMENT_GATE_V1`，再依 runtime surface 記錄同一份 startup declaration：interactive chat=user-visible；Codex/CLI/headless/scheduler=`STDOUT / TASK_EVENT / LOG` machine-visible。缺 chat UI/AI Library surface 不得成為 blocker。declaration 至少包含：
- `authorization_source`
- `execution_intent`
- `purpose`
- `authorized_scope`
- `prohibited_scope`
- `resume_authority`

沒有 durable resume authority 時固定 `resume_authority=NONE`。公告後仍必須完成 Preflight，以及 Flow v2 的 ExecutionRecord/lease、atomic admission+reservation、root-local-first Git unlock、mutation-writer guard 與 repository mutation hard gates；這份 declaration **不是安全檢查的 bypass**。legacy claim/Remote Guard 不得重新升格成 CURRENT authority。

`UPDATE_ONLY` 不得因 open Issue、open/unblocked Issue、ready candidate 或旁支工作而擴張 authorized scope；只有使用者授權的範圍可執行。


本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。


### EXPLICIT_ISSUE_DIRECT_EXECUTION_V1_BRIDGE

`EXECUTE_TICKET` 若由使用者以 exact Issue（例如 `/接手 1331`）啟動，task selection 已完成。不得在 execution startup 重新跑 AUTO DISCOVERY、READY census、open-Issue scan、scheduler candidate selection 或 takeover search。fresh-read same-Issue state後，直接做 exact ingress/resume + primary implementation。只有 entry 沒有 exact Issue 時才允許由合法 auto-selection owner 執行 discovery。

對 interactive `/接手 <issue>`，primary implementation surface 固定為 GitHub canonical durable work branch；不得要求 Remote Desktop、使用者本機或固定 `/workspace/whd`。mutation 只可落在 non-production issue branch，GitHub Actions 對 exact head GREEN 後走 PR/checks；禁止 direct-push production X。


## Intent
UPDATE_ONLY只做指定更新與readback；EXECUTE_TICKET只做指定Issue並依structured chain續接；EXECUTE_CHAIN依record.chain連續施工；SCHEDULER_LANE交由A/B lane。
任何mutation前確認current generation、canonical branch/head與record fingerprint。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。
