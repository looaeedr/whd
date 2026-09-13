# Issue #190 / T5 Phase6 Knowledge Preflight Evidence

Task: 派工 #190 T5 Combined Acceptance：驗證 3D Primary Workspace UI、Corner Data、multipart physical part、Save→Reload、DXF、regression matrix、remote QA 與 production integration；完成 caller-proof dead-code cleanup、durable Skill/AI writeback、invariants、drift audit。

Baseline lineage: `work/issue185-3d-primary-workspace-20260913 @ 68f0cc24a33ace3c22d5665ae96d3d63b8daa391`
T5 branch base: `fix/issue190-combined-acceptance-20260913 @ 68f0cc24a33ace3c22d5665ae96d3d63b8daa391`
Production drift authority: `cleanup/2d-3d-sync @ 06da676e18a365075cbfa0a517ff73a1784b2a6d`
Discovery run: `34756850687 @ 20c5ae97778f61dd9eaa2b966d3f0d083878fa01`

## READ SKILLS

- 截角資料入口收斂
- UI設計與去AI味
- 派工
- issue-closure-gate
- phase6-corner-3d-model-integrity
- diagnosing-bugs
- tdd
- monitoring-remote-qa
- 驗證板件與DXF

## READ REFERENCES

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD截角資料與2D入口收斂規則.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/dm7_part_navigation_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/issue_closure_completion_pitfalls.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md

## T5 authority notes

- T5 must remain on the accepted #185 work-order lineage; production is drift/integration authority only until the single final non-force integration.
- Validation is one-way; QA measurements/expected values must never become production calculation inputs.
- Explicit `box_body` parent selection and exact physical-child identity must remain distinct; stale explicit children fail closed.
- Combined Acceptance must include canonical physical-part/DXF reopen/Save→Reload parity, UI text-scale/readability, direct 3D startup/lifecycle, config/protected invariants, caller-proof-before-delete, durable writeback, temporary-QA cleanup and tested→closing drift audit.
- Registry HIT remains manufacturing authority; 3D/collision is shadow validation for certified rules.
- No fake feature RED is manufactured if the baseline Combined matrix is already GREEN; real gaps get a red-capable regression at the correct public seam before the minimal fix.
