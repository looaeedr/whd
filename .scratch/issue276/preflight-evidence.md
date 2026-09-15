# Issue #276 / T1 preflight evidence

MASTER_ID: #274
TASK_ID: #276 / T1
TARGET_X: cleanup/2d-3d-sync
FROZEN_X_BASE_SHA: 269a2972f0f88ffc7085ee3f1483a57145d8b2e8
EXPECTED_PARENT_SHA: b5ae852e4aaa236413b0a1acaf097ffb5dbb2776
WORK_ORDER_BRANCH: work/test-cleanup-274-20260915
TASK_BRANCH: test-cleanup/issue276-taxonomy-20260915
ROLE: T1 implementer

READ_SKILL: Python測試實務
READ_SKILL: 派工
READ_SKILL: monitoring-remote-qa
READ_SKILL: long-log-context-safe-execution
READ_SKILL: executable-continuity-controller
READ_SKILL: issue-closure-gate

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/09_X第二主分支與獨立工單鏈治理規格.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md

TDD RED CONTRACT:
- RED is created before test-lane implementation.
- Current baseline only registers requires_tk_display, has no canonical tools/test_lane_policy.py, and has no taxonomy collection hook.
- The RED tests must fail for those missing taxonomy features, not due to import/setup errors.

BOUNDARY:
- T1 may classify and select tests only.
- T1 must not add skip/xfail or change expected product behavior.
- T1 must not modify production geometry, state, DXF, project schema, or runtime identity semantics.
- Every collected test must remain in exactly one primary lane; secondary markers may overlap.
