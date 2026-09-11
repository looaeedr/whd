# 2026-09-11 Python測試實務 Skill Preflight / Verification Evidence

## 任務與已核准設計

第三批只新增一顆中文 canonical Skill：`Python測試實務`。它只負責 Python/pytest 工程實務（fixture、isolation、parameterization、mock/monkeypatch、async、marker、property-based、coverage/CI mechanics），不取代 `tdd` 的 seam/RED→GREEN/validation-authority，也不取代 `diagnosing-bugs` 的 repro/diagnosis 流程。

WHD adaptation 必須固定：
- 測試不得污染 `config.ini`、基準檔或 tracked source tree；優先 `tmp_path`/temporary workspace，必要時前後 hash/diff invariant。
- fixture / expected value / property counterexample / tolerance 只能驗證，不能回灌 production/domain authority。
- mock/monkeypatch 只能隔離真正外部邊界，不得 mock 掉要驗的 geometry、DXF export→reopen、Save→Reload、multipart/physical-part、2D/3D parity 等 authoritative seam。
- parameterization 用來擴大同一 invariant coverage，不把大量現況輸出 hard-code 成規格。
- `skip/xfail` 必須有明確原因；SKIP 不得計為 PASS，focused GREEN 不得冒充 final acceptance。
- property/fuzz finding 只能指出違反 invariant 的案例，不能自動變成 production formula/offset。

## Branch / baseline

- authoritative target: `cleanup/2d-3d-sync`
- target HEAD at branch creation: `31bbd876c248f16790654339ecc51aec9a17c2ca`
- work branch: `feat/add-python-testing-practices-zh-20260911`
- work branch initial HEAD re-read: `31bbd876c248f16790654339ecc51aec9a17c2ca`
- existing Registry baseline blob: `f3a4a4b5c01be22b2863a540abe9e0b24f9e82a4`
- existing Engineering README baseline blob: `6a71422bec0bfc53c7117c81e5ee3225ef40504a`
- existing AI08 baseline blob: `f137e78b677b7cd1df2db335380e51ae0a9e51ca`
- existing release manifest baseline blob: `b6460449e11f546a337602b023530e815510c211`

## External source provenance

- source repository: `wshobson/agents`
- pinned commit: `a30778f8c4e6b0a87567941b7cca4f534bf642b6`
- source Skill: `plugins/python-development/skills/python-testing-patterns/SKILL.md`
- supporting references read: `references/details.md`, `references/advanced-patterns.md`
- external examples are input only; WHD project rules and current pytest/test topology remain authoritative.

## Required Skills read

READ_SKILL: 寫技能
READ_SKILL: phase6-release-packaging
READ_SKILL: monitoring-remote-qa

Supplementary boundary skills read:

READ_SKILL: tdd
READ_SKILL: diagnosing-bugs

## Required References read

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: release_required_artifacts.json

## Planned changed files

- `.agents/skills/engineering/Python測試實務/SKILL.md`
- `.agents/skills/engineering/README.md`
- `.agents/skills/skill_registry.json`
- `tests/test_python_testing_practices_skill_contract.py`
- `個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md`
- `release_required_artifacts.json`
- `docs/superpowers/verification/2026-09-11-python-testing-practices-skill.md`
- `.github/workflows/python-testing-practices-skill-qa-20260911.yml` (temporary QA only; delete after terminal GREEN)

## RED → GREEN plan

1. Bootstrap Preflight must pass before contract/Skill implementation.
2. Add contract first and prove requirement RED while existing project guards remain green.
3. Implement minimal `Python測試實務` + README/Registry/AI08/release durable writeback.
4. Run targeted contract plus Chinese identity, writing-skill, Preflight, release/integrity guards.
5. Require `config.ini` before/after SHA equality and `git diff --exit-code`.
6. Lock remote QA by `run_id + head_sha` until terminal; then delete temporary workflow, remote-read 404, and drift-audit tested head → cleaned head.
