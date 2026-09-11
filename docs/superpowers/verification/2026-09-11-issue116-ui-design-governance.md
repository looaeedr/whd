# Issue #116 — UI設計與去AI味 Governance Evidence

## Owning Issue / Authority

- Owning Issue: #116 `接上 UI設計與去AI味 Registry / README / AI08 / release governance`
- Approved RED IDs: R4, R5, R6
- Parent T1 / #115: CLOSED / ACCEPTED at `d3f3ed0c5671f9ef3e6eec84d9c2ec33a84056f7`.
- Requirement RED: run `34604972890 @ 2eeab44083c9445f1a0f99939f774053917ce465` → `0 PASS / 6 FAIL`; R4–R6 user-approved.
- Work branch: `feat/issue116-ui-design-governance-20260911` from exact #115 final head.
- Production `cleanup/2d-3d-sync` remains untouched without explicit user `合`.

## Read Evidence

READ_SKILL: UI設計與去AI味
READ_SKILL: 寫技能
READ_SKILL: Python測試實務
READ_SKILL: phase6-release-packaging
READ_SKILL: monitoring-remote-qa
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: release_required_artifacts.json

## Current governance gaps

- `.agents/skills/skill_registry.json`: no `ui-design-de-ai` route yet.
- `.agents/skills/engineering/README.md`: no canonical `UI設計與去AI味` entry yet.
- AI08 ends at fourth-batch durable guidance; no fifth-batch UI section yet.
- `release_required_artifacts.json`: does not yet require the canonical UI Skill or `tests/test_ui_design_de_ai_skill_contract.py`.

## T2 scope

T2 owns R4–R6 only:

1. machine routing / README discovery;
2. AI08 durable writeback including user-approved anti-global-replace / per-component / Action Color / monospace / elevation / text-scale / visual-capability rules;
3. release mandatory artifacts and contract integration.

T1 Skill body is treated as accepted input and is not rewritten unless a T2 integration RED proves a required seam is missing.

## Bootstrap state

- Preflight: PENDING.
- Formal T2 R4–R6 contract RED: PENDING until Preflight GREEN.
- Governance writes: NOT STARTED.
