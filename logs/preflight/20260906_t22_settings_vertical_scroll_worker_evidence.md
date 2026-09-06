# T22 / T4 Worker Preflight Evidence

Issue: #22 — Medium + 參數解鎖設定區真正 Vertical Scroll
Role: T4 實作者
Base: 224283acc41803d6616e08a4d5d4a8d0c271c7e3
Work branch: work/20260906-t4-settings-vertical-scroll

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
1120×720 → Receiving → Head → 文字大小中 → 參數解鎖
Required ownership:
Header/Footer fixed; central settings fields own a real vertical Canvas + Scrollbar.
