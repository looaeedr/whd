---
name: 遠端執行守門
description: Flow v2 remote mutation compatibility入口。舊式中間授權 protocol已退役；新的遠端 mutation 只接受 atomic transaction terminal result。
whd_doc_role: MIRROR
whd_contract: remote-execution-guard
whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md
whd_schema: WHD_DOC_META_V1
---

# 遠端執行守門

<!-- FLOW_V2_EXECUTION_BRIDGE_V1 -->

### EXECUTION_ENTRY_AUTH_PURPOSE_BRIDGE_V1

此入口只 bridge 到 canonical `tools/execution_entry_contract.py` 與 `flow-v2-execution::PROJECT_STARTUP_HARD_GATE_V1`，不建立第二套 startup authority。每個新 invocation 在任何 substantive analysis、claim、Guard、repository mutation 或 workflow dispatch 前，必須重新 user-visible 產生 `WHD_EXECUTION_ENTRY_AUTHORIZATION_PURPOSE_V1`，並完成 project Phase6 Preflight；不得以「已讀 Flow v2」或前一 runtime declaration 代替。


本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

## Retired compatibility
此名稱只為舊引用相容，不得 mint/consume/恢復舊式中間授權。新的 remote mutation直接使用 Flow v2 transaction request，綁 expected generation/fingerprint/head/target；結果只能 APPLIED、CONFLICT、FAILED。缺 trusted capability時分類 MISSING_CAPABILITY並 fail closed。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。


## TASK_START_AUTHORITY_DECLARATION_V1_BRIDGE

本入口只 bridge 到 `執行開發任務::TASK_START_AUTHORITY_DECLARATION_V1` 與 canonical `tools/execution_entry_contract.py`，不得建立第二套 startup authority。

此 declaration 不建立 execution authority，也不能把 Guard GREEN 當成 owner/claim；Flow v2 transaction fencing 仍是唯一 CURRENT mutation authority。
