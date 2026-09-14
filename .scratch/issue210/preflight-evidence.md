# #210 / T6 Final Acceptance Knowledge Evidence

Current cleaned code head before this evidence-only commit: `2e354528791eec4307f039c805bed4b743b3c265`
Role: `[當前角色：T6 實作者]`
Purpose: trigger final Save→Reload + DXF reopen/manufacturing acceptance without changing production/test code.

Skills read and applied:
- phase6-corner-3d-model-integrity
- 驗證板件與DXF
- monitoring-remote-qa

Required reference evidence:
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md

Locked boundaries:
- ProjectController / ProjectSession remain the persistence transaction authority.
- `.p6fold` schema/read/write owners remain unchanged.
- The four extracted wrappers must remain AST-body identical to accepted T5 baseline.
- Save→Reload, DXF reopen and manufacturing checks are validation only and may not redefine production geometry.
- config.ini and all baseline/reference files are invariant.