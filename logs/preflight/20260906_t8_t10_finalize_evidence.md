# T8–T10 Finalization Knowledge Preflight Evidence

- source_head: 920521bfe35f5981ca55df0f6e9d76706a649b57
- branch: cleanup/t8-t10-finalize-20260906
- backup_tag: backup-20260906-110833

READ_SKILL: phase6-corner-3d-model-integrity
READ_SKILL: phase6-release-packaging
READ_SKILL: diagnosing-bugs
READ_SKILL: tdd
READ_SKILL: dispatching

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
READ_REFERENCE: release_required_artifacts.json

Notes:
- 本輪先做 #8/#9 QA 證據修正與 #10 release verification；若正式 gate 發現 production RED，再另依 diagnosing-bugs + TDD 進入修正。
- 不以舊 2026-09-02 Xvfb gate 代替 2026-09-06 HEAD 的正式 GUI gate。
