# T21 / T3 Worker Preflight Evidence

Issue: #21 — 3D 已開啟後切 Receiving 時刷新 Dynamic Part Selector
Role: T3 實作者
Base: cef3ab34b1dce5c7989e3f82993086738b0a7425
Work branch: work/20260906-t3-live-switch-selector

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
金庫型 → 開啟 3D Designer → 在 Designer 內切受電箱 → selector 立即刷新
Reverse seam:
受電箱 → 已開 Designer → 切金庫型 → stale dynamic entries 立即清除
