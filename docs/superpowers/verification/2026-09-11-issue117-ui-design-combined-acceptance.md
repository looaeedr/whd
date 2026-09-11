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
3. Project Skill/governance guards:
   - `tests/test_chinese_skill_identity_contract.py`
   - `tests/test_writing_skill_contract.py`
   - `tests/test_writing_skill_preflight_route.py`
   - `tests/test_find_skill_contract.py`
   - `tests/test_second_batch_skills_contract.py`
   - `tests/test_python_testing_practices_skill_contract.py`
   - `tests/test_fourth_batch_skills_contract.py`
   - `tests/test_dxf_skill_scope_contract.py`
   - `tests/test_phase6_skill_preflight_gate.py`
   - `tests/test_phase6_release_packaging_policy.py`
   - `tests/test_release_integrity_gate.py`
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
- Same-repo working workflow `.github/workflows/receiving-divider-broader-acceptance.yml` provisions Python then installs pytest before pytest guards. Replacement run changes only the temporary QA harness to provision `pytest`; formal test scope is unchanged.

## Current state

- T3 Preflight: GREEN on first run.
- Fifth-batch formal contract: GREEN on first run.
- Project guards: PENDING replacement run because first runner lacked pytest runtime.
- Temporary QA cleanup: PENDING terminal replacement run.
- Integration readiness: PENDING final scope/topology audit.
