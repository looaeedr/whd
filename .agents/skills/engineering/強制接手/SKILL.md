---
name: 強制接手
description: 使用者明確要求接手既有 WHD 工作時使用。Flow v2 以 generation fencing + atomic owner transition處理，不直接覆寫 foreign runtime。
whd_doc_role: MIRROR
whd_contract: user-directed-force-takeover
whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md
whd_schema: WHD_DOC_META_V1
---

# 強制接手

<!-- FLOW_V2_EXECUTION_BRIDGE_V1 -->

### EXECUTION_ENTRY_AUTH_PURPOSE_BRIDGE_V1

此入口只 bridge 到 canonical `tools/execution_entry_contract.py` 與 `flow-v2-execution::PROJECT_STARTUP_HARD_GATE_V1`，不建立第二套 startup authority。每個新 invocation 在任何 substantive analysis、claim、Guard、repository mutation 或 workflow dispatch 前，必須重新 user-visible 產生 `WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1`，並完成 project Phase6 Preflight；不得以「已讀 Flow v2」或前一 runtime declaration 代替。


本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

## Takeover
先fresh-read native record與lease。foreign live lease無明確失效證據則fail closed；expired/orphan runtime以atomic ACQUIRE/HANDOFF/RECONCILE轉移。無法安全判斷舊writer時bump generation+新canonical branch。superseded generation成果先當donor，可證明相容就收編。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。


## TASK_START_AUTHORITY_DECLARATION_V1_BRIDGE

本入口只 bridge 到 `執行開發任務::TASK_START_AUTHORITY_DECLARATION_V1` 與 canonical `tools/execution_entry_contract.py`，不得建立第二套 startup authority。
