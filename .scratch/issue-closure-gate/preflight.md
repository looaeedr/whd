# issue-closure-gate Skill change preflight evidence

Branch baseline: cleanup/2d-3d-sync @ 1d78f418abbe9a7e3b60b90e7bfdb4cc520b5ac2
Work branch: docs/skill-issue-closure-gate-20260911

READ_SKILL: 寫技能
READ_SKILL: phase6-release-packaging
READ_SKILL: monitoring-remote-qa
READ_SKILL: issue-closure-gate

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: release_required_artifacts.json

Additional durable authority read:
READ_REFERENCE: 個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md

Purpose: prevent code integration / target merge from being misreported as GitHub ticket or Master completion. Require leaf → closing/Final Combined → Master remote issue-state readback before any official-complete claim.
