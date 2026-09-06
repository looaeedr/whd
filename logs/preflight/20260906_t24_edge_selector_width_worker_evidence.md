# T24 / T6 Worker Preflight Evidence

Issue: #24 — 封頭/尾四向 Selector 再縮窄至 width <= 5
Role: T6 實作者
Base: ff1544cee9eb28ed27d7a5e5d492bf00016b02b6
Work branch: work/20260906-t6-edge-selector-width

READ_SKILL: diagnosing-bugs
READ_SKILL: tdd
READ_SKILL: monitoring-remote-qa

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md

Preflight:
- REQUIRED SKILLS: 3/3 PASS
- REQUIRED REFERENCES: 2/2 PASS

Boundary:
UI width only. AssemblyJoint / Corner / Relief / geometry semantics must remain unchanged.
