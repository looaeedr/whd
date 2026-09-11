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

## Preflight

- run `34607445439 @ c2da43a1b77f1050d92d61f064e4365d26cc0eaa` → SUCCESS.
- Required Skills: `寫技能`, `phase6-release-packaging`, `monitoring-remote-qa` → all PASS.
- Required references: AI06, AI08, `release_required_artifacts.json` → all PASS.
- `config.ini` before/after SHA256 = `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`.

## Formal T1 RED

- run `34607648037 @ bb57470203aca1e62e042c15e65feb3a3d898480` → terminal FAILURE at T1 contract after Preflight PASS.
- Result: `0 passed / 8 failed`.
- Failure cause: canonical `.agents/skills/engineering/UI設計與去AI味/SKILL.md` did not yet exist; no setup/import/collection noise.
- `config.ini` invariant PASS; `git diff --exit-code` PASS.

## T1 GREEN tested head

- tested head: `cd66afa3e53a22e3f3a61663b6e8f30b28bdd367`.
- run `34607852950 @ cd66afa3e53a22e3f3a61663b6e8f30b28bdd367` → SUCCESS.
- Formal contract: `8 passed / 0 failed`.
- Preflight PASS before contract.
- `config.ini` before/after = canonical `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`.
- `git diff --exit-code` PASS.
- Remote readback Skill blob: `a378e2825df065bd53fb70101d1fb9b5454d717a`.
- Remote readback contract-test blob: `ba7837be47bd1acd0f6fbd9b6eb23e49d59bf035`.

## Dispatch checkpoint

- Task: Fifth batch `UI設計與去AI味`
- Ticket: #115 / T1
- Current role: T1 Implementer, preparing QA handoff
- Branch: `feat/issue115-ui-design-de-ai-skill-20260911`
- Completed: branch-first, authority read, external provenance pin, Preflight GREEN, formal RED, minimal Skill implementation, focused GREEN, tested-head remote readback.
- Pending: temporary workflow/sentinel cleanup, 404 verification, tested-head→cleaned-head drift audit, final remote readback, Issue #115 terminal evidence, QA ACCEPT.
- Failed/blocked: none.
- Relevant files: `.agents/skills/engineering/UI設計與去AI味/SKILL.md`, `tests/test_ui_design_de_ai_skill_contract.py`, this evidence file.
- Verification run IDs: `34607445439`, `34607648037`, `34607852950`.
- Resume command/operation: re-read temp workflow/sentinel on this branch → delete workflow then sentinel → verify 404 → compare `cd66afa3...` to cleaned head → QA review.

## Acceptance state

- Focused T1 contract: GREEN.
- T1 final acceptance: PENDING cleanup/drift/QA review.
