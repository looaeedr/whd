# 2026-09-06 Late Process Pitfall Evidence

Task: 補記派工期間新增的 orchestration / remote-QA trigger 錯誤
Base: cleanup/2d-3d-sync@8d1957a2ea12b96391f5447d2ccea50299ff8a8c

READ_SKILL: phase6-release-packaging
READ_SKILL: diagnosing-bugs
READ_SKILL: tdd
READ_REFERENCE: release_required_artifacts.json
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
READ_REFERENCE: AGENTS.md

Recorded incidents:
- T19 accidental journal/state-triggered QA runs: 34041407619, 34041410346
- T21 orchestration ReferenceError for undeclared base variable; zero remote write before failure
