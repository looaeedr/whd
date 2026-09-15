# Issue #275 T0 — fail-closed preflight evidence

MASTER_ID: #274
TASK_ID: #275 / T0
TARGET_X: cleanup/2d-3d-sync
FROZEN_X_BASE_SHA: 269a2972f0f88ffc7085ee3f1483a57145d8b2e8
WORK_ORDER_BRANCH: work/test-cleanup-274-20260915
TASK_BRANCH: test-cleanup/issue275-inventory-v2-20260915
ROLE: T0 implementer

READ_SKILL: Python測試實務
READ_SKILL: 派工
READ_SKILL: issue-closure-gate
READ_SKILL: monitoring-remote-qa
READ_SKILL: long-log-context-safe-execution
READ_SKILL: executable-continuity-controller

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/09_X第二主分支與獨立工單鏈治理規格.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md

BOUNDARY:
- T0 is inventory/classification only.
- Tests are judges, never production geometry/dimension/DXF/runtime identity authority.
- No test deletion, assertion weakening, production behavior change, geometry change, DXF change, schema change, or baseline rewrite is authorized.
- Historical #212 evidence may identify already-proven inherited nodeids, but #212 is not executed or monitored by T0.
- Any unclassified node defaults to KEEP_CURRENT_CONTRACT.
