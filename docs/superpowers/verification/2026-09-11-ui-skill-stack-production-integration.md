# UI / testing Skill stack → production integration evidence

## Authority

- User explicitly authorized integration with `合`.
- Fresh production base: `cleanup/2d-3d-sync @ b100babcd87ac3e3dda1c091f8ae9d19a9bd9288`.
- Accepted payload: `qa/issue117-ui-design-combined-acceptance-20260911 @ cd0e6bef5d05eabfb39c6add07257bcaf6745e6d`.
- Integration branch: `integration/ui-design-skill-stack-20260911` from exact fresh production base.
- Production must only move by non-force fast-forward after integrated-head Combined Acceptance is GREEN.

## Fresh reads

READ_PROJECT_RULES: AGENTS.md
READ_SKILL: 寫技能
READ_SKILL: resolving-merge-conflicts
READ_SKILL: phase6-release-packaging
READ_SKILL: monitoring-remote-qa
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: release_required_artifacts.json
READ_EVIDENCE: docs/superpowers/verification/2026-09-11-issue117-ui-design-combined-acceptance.md

## Planned accepted payload

Integrate the already-accepted testing/property/dimensional/UI Skill stack without modifying production geometry/UI source behavior:

- `.agents/skills/engineering/Python測試實務/SKILL.md`
- `.agents/skills/engineering/性質導向測試/SKILL.md`
- `.agents/skills/engineering/尺寸語意分析/SKILL.md`
- `.agents/skills/engineering/UI設計與去AI味/SKILL.md`
- `.agents/skills/engineering/README.md`
- `.agents/skills/skill_registry.json`
- `tests/test_python_testing_practices_skill_contract.py`
- `tests/test_fourth_batch_skills_contract.py`
- `tests/test_ui_design_de_ai_skill_contract.py`
- `release_required_artifacts.json`
- `個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md`
- accepted verification evidence files.

Existing production-only governance/source changes must be preserved; conflicts are resolved by intent, never by replacing current production wholesale.

## State

- Integration Preflight: PENDING.
- Accepted payload merge: NOT STARTED.
- Integrated Combined Acceptance: PENDING.
- Production update: NOT STARTED.
