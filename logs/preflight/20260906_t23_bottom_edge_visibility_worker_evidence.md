# T23 / T5 Worker Preflight Evidence

Issue: #23 — Medium 下封頭/尾 BOTTOM 控制區不得被裁切
Role: T5 實作者
Base: a613eb0f1712fa36f04f959096b2e765b596a168
Work branch: work/20260906-t5-bottom-edge-visibility

READ_SKILL: phase6-corner-3d-model-integrity
READ_SKILL: diagnosing-bugs
READ_SKILL: tdd
READ_SKILL: monitoring-remote-qa

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md

Preflight:
- REQUIRED SKILLS: 4/4 PASS
- REQUIRED REFERENCES: 4/4 PASS

Exact seam:
1120×720 → Receiving → Head/Tail → 文字大小中 → 參數解鎖
Assertion:
all four edge-control hosts are viewable and fully inside the renderer canvas bounds.
