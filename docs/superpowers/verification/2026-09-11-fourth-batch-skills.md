# 2026-09-11 第四批 Skill Preflight / Verification Evidence

## 已核准設計

第四批新增兩顆中文 canonical Skill：

- `性質導向測試`：深化 property / invariant / generator / shrinking / counterexample classification；接在 `Python測試實務` 之上，不取代 pytest mechanics、TDD 或 debugging authority。
- `尺寸語意分析`：分析 WHD 中同為 mm 但語意不同的 material / formed / outside / FW / T / datum / flat / collision-envelope 尺寸，找出語意混用；只做分析與驗證，不能自行產生或回灌 production 公式。

`尺寸語意分析` 不照抄 upstream `dimensional-analysis` 的強制 full-auto/subagent pipeline。WHD 版必須 capability-adaptive：有真正 subagent/parallel runtime 才可分工，沒有就由同一執行者逐階段完成；不得假裝已派 agent。

## Branch / baseline

- production target: `cleanup/2d-3d-sync @ 31bbd876c248f16790654339ecc51aec9a17c2ca`
- stacked prerequisite: third-batch accepted branch head `8fb35e1f551faa81776f8bd51d8ce3f82a04bd6f`
- work branch: `feat/add-property-dimension-skills-zh-20260911`
- work branch base: `8fb35e1f551faa81776f8bd51d8ce3f82a04bd6f`
- bootstrap workflow commit: `fc6111a6890d4b4a694c84e2ef12cfe6286d4cd4`

## Required Skills read

READ_SKILL: 寫技能
READ_SKILL: Python測試實務
READ_SKILL: phase6-release-packaging
READ_SKILL: monitoring-remote-qa

## Required References read

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: release_required_artifacts.json

## External source provenance read

- `trailofbits/skills@321ccfe628eca0d314b0ee4eaffcdd8a05639aaf`
- `plugins/property-based-testing/skills/property-based-testing/SKILL.md`
- `property-based-testing/references/generating.md`
- `property-based-testing/references/interpreting-failures.md`
- `plugins/dimensional-analysis/skills/dimensional-analysis/SKILL.md`
- `dimensional-analysis/references/dimension-algebra.md`
- `dimensional-analysis/references/common-dimensions.md`
- `dimensional-analysis/references/bug-patterns.md`

## Planned changed files

- `.agents/skills/engineering/性質導向測試/SKILL.md`
- `.agents/skills/engineering/尺寸語意分析/SKILL.md`
- `.agents/skills/engineering/README.md`
- `.agents/skills/skill_registry.json`
- `tests/test_fourth_batch_skills_contract.py`
- `個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md`
- `release_required_artifacts.json`
- `docs/superpowers/verification/2026-09-11-fourth-batch-skills.md`
- `.github/workflows/fourth-batch-skills-qa-20260911.yml` (temporary QA only)

## Bootstrap attempt 1

- run `34601201626 @ fc6111a6890d4b4a694c84e2ef12cfe6286d4cd4` → FAILURE at Knowledge Preflight.
- setup/dependency/config snapshot all completed before the gate.
- failure showed required Skills/references as `✗` because this evidence file did not yet exist with read markers.
- classification: **Preflight evidence gate failure; not requirement RED and not product/test failure.**
