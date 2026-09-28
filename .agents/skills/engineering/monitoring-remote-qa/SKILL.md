---
name: monitoring-remote-qa
description: Flow v2 remote CI/QA 監控入口。只追 ExecutionRecord.active_run 的 exact run/head，terminal結果回寫同一 record。
whd_doc_role: MIRROR
whd_contract: remote-qa-monitoring
whd_canonical: .agents/skills/engineering/flow-v2-execution/SKILL.md
whd_schema: WHD_DOC_META_V1
---

# monitoring-remote-qa

<!-- FLOW_V2_EXECUTION_BRIDGE_V1 -->

本 Skill 是入口／角色 bridge，不擁有 execution state machine。所有 execution authority、resume、mutation、lease、handoff、recovery、scheduler 與 closure 語意一律服從 `.agents/skills/engineering/flow-v2-execution/SKILL.md`。

## Remote QA
START_QA建立exact run/head後，active期間只POLL_QA，不重送。success→ACCEPT_QA；failure把evidence寫入record並產生structured repair/reconcile action。GitHub Actions使用者可見名稱維持繁中。大型log用artifact/pointer，不把log prose當authority。

任何與 canonical Flow v2 衝突的歷史 evidence 或相容工具都只可作 audit/reference，不得恢復成 CURRENT execution authority。
