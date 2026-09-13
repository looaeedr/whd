# Issue #186 Knowledge Preflight Evidence

Task: 派工 執行 #186 T1：修正 #163 後 3D UI 鈑金／板件選單不可見 regression；恢復板件顯示與板件切換，組合體 / Corner Data / Receiving multipart stable identity；使用 real Tk/Xvfb RED→GREEN、remote QA、完整板件驗收。

Base: cleanup/2d-3d-sync @ 2e27870497927fa8912135998ef7c4be3ab4220b
Work branch: fix/issue186-restore-sheetmetal-selector-20260913

READ_SKILL: 派工
READ_SKILL: issue-closure-gate
READ_SKILL: UI設計與去AI味
READ_SKILL: phase6-corner-3d-model-integrity
READ_SKILL: diagnosing-bugs
READ_SKILL: tdd
READ_SKILL: monitoring-remote-qa
READ_SKILL: 驗證板件與DXF
READ_SKILL: 截角資料入口收斂
READ_SKILL: 執行開發任務

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD截角資料與2D入口收斂規則.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/dm7_part_navigation_pitfalls.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md

Notes:
- UI rehost structural presence is not sufficient; critical selector must be mapped/reachable/interactive.
- Explicit parent/child identity remains owned by DM7 navigation; no new selector may become identity authority.
- Validation is judge-only; no manufacturing/DXF geometry authority change is permitted in T1.
