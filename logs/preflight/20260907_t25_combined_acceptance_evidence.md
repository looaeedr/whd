# T25 / T7 Combined Acceptance Preflight Evidence

Issue: #25 — Receiving 本輪 Combined Acceptance
Role: 總控審查
Base: b14cc8a7e47a90e0d49ef3104e4688bb3c460d35
QA branch: qa/20260907-t7-combined-acceptance

READ_SKILL: monitoring-remote-qa
READ_SKILL: tdd
READ_SKILL: phase6-release-packaging
READ_REFERENCE: AGENTS.md
READ_REFERENCE: release_required_artifacts.json
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md

Dependencies:
- #19 ACCEPTED
- #20 ACCEPTED
- #21 ACCEPTED
- #22 ACCEPTED
- #23 ACCEPTED
- #24 ACCEPTED

Combined gate:
- one end-to-end live family-switch operator-path test
- T11/T13/T14/T16/T19/T20/T21/T22/T23/T24
- Receiving multipart
- 2D↔3D round-trip
- multi-door GUI
- assembly placement divider
- config.ini SHA256 before/after invariant
- durable runner journal/state with collection identity and terminal nodeids
