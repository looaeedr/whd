# #237 Preflight Evidence

Parent: #209 / #203
Base: T5 tested head `296aa4376efa25bae5cc47c51fb6b871eceb720e`
Branch: `docs/issue237-failclosed-qa-rules-20260914`

READ_SKILL: monitoring-remote-qa
READ_SKILL: long-log-context-safe-execution
READ_SKILL: Python測試實務
READ_PROCESS: AGENTS.md Knowledge Preflight / Fail-closed / Remote QA
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md

## Incident reread
- GitHub step conclusion can be false GREEN when a failing left-hand command is piped to `tee` without pipefail.
- Acceptance authority is the actual validator/test terminal result, not wrapper/job color alone.
- Move-Only/characterization validators must pin immutable accepted SHA; movable branch refs are not evidence anchors.
- Symbol owner/class must come from AST/dependency inventory or exact source reread, not assumed subclass/public surface.
