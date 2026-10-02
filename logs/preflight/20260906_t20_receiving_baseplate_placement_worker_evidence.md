# T20 / T2 Worker Preflight Evidence

Issue: #20 — Receiving 每門底板尺寸與 authoritative 3D Placement
Role: T2 實作者
Base: 5391c7b576b853f324c9bae8b291f9f8f0966680
Work branch: work/20260906-t2-receiving-baseplate-placement

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

Locked product invariants:
- dynamic Base Plate remains vertical like legacy base_plate
- Z plane/orientation is unchanged from legacy base semantics
- only per-cell W/H and authoritative X/Y center replace the global W/H and -H/2 shift
- Receiving 55/55/55/55 + bend 15 manufacturing policy remains unchanged
