# DM4 Phase6 Knowledge Preflight Evidence

- Owning Issue: #54
- Repository: `looaeedr/whd`
- Branch: `work/dm4-divider-resolved-sinks`
- Base: `work/dm3-divider-canonical-relief@6da176c316523042a73e41883e532b7fb52a3123`
- Role: `[當前角色：#54 實作者]`

READ_SKILL: phase6-corner-3d-model-integrity
READ_SKILL: diagnosing-bugs
READ_SKILL: tdd
READ_SKILL: monitoring-remote-qa
READ_SKILL: dispatching
READ_SKILL: implement

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
READ_CONTEXT: CONTEXT.md

## Gate
Local reproduction of the repository's `tools/phase6_skill_preflight.py` route logic returned all required Skills and references GREEN before any DM4 production/test write.

## Scope authority
DM4 must make 2D / single 3D / assembly 3D / DXF / Save-Reload consume the resolved Divider geometry/final material and must not reintroduce raw Fold/FW-index/placement/relief oracles in sinks.
