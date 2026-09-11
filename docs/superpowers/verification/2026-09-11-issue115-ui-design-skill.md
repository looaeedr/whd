# Issue #115 — UI設計與去AI味 Skill Evidence

## Owning Issue / Authority

- Owning Issue: #115 `建立 canonical UI設計與去AI味 Skill 與正式 contract`
- Approved RED IDs: R1, R2, R3
- Requirement RED: run `34604972890 @ 2eeab44083c9445f1a0f99939f774053917ce465` → `0 PASS / 6 FAIL`; R1–R6 user-approved.
- Stacked accepted base: `feat/add-property-dimension-skills-zh-20260911 @ 1f3fa065ace5893a6c327ce780efc980767da5a1`
- Work branch: `feat/issue115-ui-design-de-ai-skill-20260911`
- Production `cleanup/2d-3d-sync` is not modified without explicit user `合`.

## Read Evidence

READ_SKILL: 寫技能
READ_SKILL: Python測試實務
READ_SKILL: phase6-release-packaging
READ_SKILL: monitoring-remote-qa
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: release_required_artifacts.json

## External input provenance — not WHD authority

- `anthropics/skills@34040c9c568585f6929bedeaad110ad08f079624`, `skills/frontend-design/SKILL.md`, blob `a5333457c414d20d625f307df945842c0952ecc3`.
- `funboy322/avoid-ai-design@8337060636a8cf12e32e883eb367becd702aa526`, `SKILL.md`, blob `afaf14a7fef6396b6121a2c2126d5a41e92b2856`.
- WHD user-approved spec and project governance override both external sources.

## T1 scope

T1 owns only R1–R3:

1. canonical Chinese `UI設計與去AI味` identity and Audit / Rewrite / New Design modes;
2. per-component / per-region safe rewrite contract, no global presentation replace, behavior preservation;
3. Action Color / monospace width / foreground elevation / hierarchy replacement / text-scale and scroll safeguards.

Registry / README / AI08 / release manifest are T2 (#116), not T1 implementation scope.

## Bootstrap status

- Preflight: PENDING
- Formal T1 contract RED: PENDING until Preflight GREEN
- Skill implementation: NOT STARTED
