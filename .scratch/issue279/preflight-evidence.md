# Issue #279 / T4 remote QA preflight evidence

TASK: TEST cleanup GUI characterization replacement proof, pytest, remote QA, UI contract, issue closure preparation

READ_SKILL: Python測試實務
READ_SKILL: UI設計與去AI味
READ_SKILL: 派工
READ_SKILL: issue-closure-gate
READ_SKILL: executable-continuity-controller
READ_SKILL: monitoring-remote-qa
READ_SKILL: long-log-context-safe-execution
READ_SKILL: diagnosing-bugs
READ_SKILL: tdd

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md

BOUNDARY:
- Test-governance cleanup only.
- No production source, geometry, DXF, persistence, schema, or runtime identity mutation.
- Replacement proof must run old #206 and permanent successors together before retirement.
- No skip/xfail masking and no assertion weakening to manufacture GREEN.
