# Issue #63 Phase6 Knowledge Preflight Evidence

- task: Receiving multipart BoxBody GUI input sections + Divider relief + fixed-hole geometry regression
- repository: looaeedr/whd
- branch: fix/receiving-multipart-divider-geometry
- parent: main@134739610d15a7d7549e70f0006a8e3e51b90774

READ_SKILL: phase6-corner-3d-model-integrity
READ_SKILL: phase6-overlay-relief-basis
READ_SKILL: diagnosing-bugs
READ_SKILL: tdd
READ_SKILL: monitoring-remote-qa

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
READ_CONTEXT: CONTEXT.md

## Hard constraints
- exact GUI user path must be red-capable; backend part-count green is insufficient.
- multipart BoxBody physical pieces, not aggregate box_body, are ownership/collision authority.
- 中隔.dxf fixed holes/features are authoritative; its outer CUTTING contour is not relief truth.
- Divider relief requires valid FW-face-flush placement, real side-piece collision, backprojection, refold verification.
- no magic 174 / 47-26 / 1mm / bbox / renderer-origin oracle.
- config.ini invariant.
