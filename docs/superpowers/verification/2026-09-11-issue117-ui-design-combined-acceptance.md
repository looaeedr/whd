# Issue #117 — UI設計與去AI味 Combined Acceptance Evidence

## Owning Issue / Authority

- Owning Issue: #117 `UI設計與去AI味 Combined Acceptance / cleanup / drift / integration readiness`
- Approved RED IDs: R1, R2, R3, R4, R5, R6.
- Requirement RED: run `34604972890 @ 2eeab44083c9445f1a0f99939f774053917ce465`.
- T1 / #115 evidence: `docs/superpowers/verification/2026-09-11-issue115-ui-design-skill.md` → ACCEPTED.
- T2 / #116 evidence: `docs/superpowers/verification/2026-09-11-issue116-ui-design-governance.md` → ACCEPTED.
- T3 branch: `qa/issue117-ui-design-combined-acceptance-20260911` from exact T2 final `baaf966f35a76c7a0773dc43a8f231fb232fa368`.
- Fourth-batch accepted comparison base: `1f3fa065ace5893a6c327ce780efc980767da5a1`.
- Production target `cleanup/2d-3d-sync` must not be updated without explicit user `合`.

## T3 fresh read evidence

READ_SKILL: UI設計與去AI味
READ_SKILL: phase6-release-packaging
READ_SKILL: monitoring-remote-qa
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: release_required_artifacts.json
READ_EVIDENCE: docs/superpowers/verification/2026-09-11-issue115-ui-design-skill.md
READ_EVIDENCE: docs/superpowers/verification/2026-09-11-issue116-ui-design-governance.md
READ_PROJECT_RULES: AGENTS.md

## Combined Acceptance matrix

1. Evidence-backed Phase6 Knowledge Preflight for UI redesign + release + remote QA acceptance.
2. `python tests/test_ui_design_de_ai_skill_contract.py` for exact R1–R6 result.
3. Project Skill/governance guards: Chinese identity, authoring/discovery, prior Skill batches, DXF scope, Preflight gate, release packaging, release integrity.
4. JSON parse guards for Registry + release manifest.
5. `config.ini` before/after SHA256 invariant and `git diff --exit-code` clean-tree guard.
6. On terminal GREEN: remote readback, one-shot workflow/sentinel cleanup, 404 proof, tested-head→cleaned-head drift audit.
7. Fourth-batch accepted base→fifth-batch final scope audit and production/final topology audit.

## First Combined run — harness failure, not product failure

- locked run: `34611424136 @ 3195a0f76d74f2069c14b14449e0c6757460b425`.
- Phase6 Knowledge Preflight: PASS; required Skills `UI設計與去AI味`, `phase6-release-packaging`, `monitoring-remote-qa`; required references AI06, AI08, release manifest all PASS.
- Fifth-batch R1–R6 contract: `11 passed / 0 failed`.
- Project-guard step did not collect tests because runner returned `/usr/bin/python3: No module named pytest`.
- `config.ini` before/after remained canonical `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`; clean-tree guard PASS.
- Failure classification: QA harness/runtime provisioning failure. No project guard reported a test failure.
- Same-repo working workflow `.github/workflows/receiving-divider-broader-acceptance.yml` provisions Python then installs pytest before pytest guards. Replacement run changed only the temporary QA harness to provision pytest; formal test scope stayed unchanged.

## Replacement Combined GREEN / tested head

- tested head: `c0d0d1f5654101619f8afc94cdea37cdc2120342`.
- locked replacement run: `34611703340 @ c0d0d1f5654101619f8afc94cdea37cdc2120342` → terminal `SUCCESS`.
- `actions/setup-python@v5` resolved to SHA `a26af69be951a213d495a4c3e4e4022e16d87065`; CPython `3.11.16`; pytest provisioned successfully.
- Knowledge Preflight: PASS with required Skills `UI設計與去AI味`, `phase6-release-packaging`, `monitoring-remote-qa`; required references AI06, AI08, release manifest PASS.
- Fifth-batch R1–R6 formal contract: `11 passed / 0 failed`.
- Project Skill / governance / release guards: `87 passed / 0 failed / 0.53s`.
- Registry JSON parse: PASS.
- Release manifest JSON parse: PASS.
- `config.ini` before/after SHA256 = canonical `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`.
- `git diff --exit-code`: PASS.

## Remote readback at tested head

- Final Skill blob: `a378e2825df065bd53fb70101d1fb9b5454d717a`.
- Final Registry blob: `56acab1ce5c3aee9694daf5b5cbdc38aeb17028f`; route is intent-scoped and has no broad `gui.py` glob.
- Final AI08 blob: `66dd736c433ef4a7b6265a1c32cb57a9ca7bd0d5`; fifth-batch section is consistent with final Skill authority boundaries and safeguards.
- Final release manifest blob: `8d4f9868f4c9f2a20177828e86f0032e54920bac`; requires the canonical Skill and contract test.
- Final formal contract blob: `3d5bfd32e254b99124fc0193868446ed3afd34b9`.

## Current state

- T3 Preflight: GREEN.
- Fifth-batch formal contract: GREEN `11/0`.
- Project guards: GREEN `87/0`.
- Machine-readable governance parse: GREEN.
- Config / clean-tree invariant: GREEN.
- Temporary QA cleanup: PENDING.
- Integration readiness: PENDING final cleanup/scope/topology audit.
