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
READ_SKILL: Python測試實務

Supplementary boundary skills read:

READ_SKILL: tdd
READ_SKILL: diagnosing-bugs

> `Python測試實務` 是本工單新建 Skill；candidate 由 pinned upstream 與已核准 WHD adaptation contract 寫成。final acceptance 前後已以 remote re-read 確認實際 branch 內容。

## Required References read

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: release_required_artifacts.json

## Changed files

- `.agents/skills/engineering/Python測試實務/SKILL.md`
- `.agents/skills/engineering/README.md`
- `.agents/skills/skill_registry.json`
- `tests/test_python_testing_practices_skill_contract.py`
- `個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md`
- `release_required_artifacts.json`
- `docs/superpowers/verification/2026-09-11-python-testing-practices-skill.md`
- `.github/workflows/python-testing-practices-skill-qa-20260911.yml`（temporary QA only；final cleanup 已刪除）

## Bootstrap Preflight evidence

- bootstrap head: `97251f33d52c8fad655068730ae5a31d03c8ebe1`
- run `34599014288` → **SUCCESS**。
- Knowledge Preflight：`寫技能`、`phase6-release-packaging`、`monitoring-remote-qa` 全部 PASS；required references 全部 PASS。
- `config.ini` before / after SHA256：`980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`。
- bootstrap 階段尚未建立 contract，只驗施工環境與知識閘門，不算功能 GREEN。

## RED evidence

- RED commit: `d7caec32701c242231a9aaad05ed17e310104bc9`。
- RED run: `34599128016` → FAILURE at `Third batch contracts and project guards`；setup、dependency install、config snapshot、Knowledge Preflight 都先 PASS。
- summary：**8 failed / 51 passed / 0.71s**。
- 8 個 failure 對應已核准缺口：`Python測試實務` 尚不存在、Registry route 缺失、README/AI08/release 尚未納入，以及 isolation/validation-authority/mock/skip contract 尚未有 Skill 實體承接。
- 這是 requirement RED，不是 setup/import/harness failure。

## GREEN / final acceptance evidence

- implementation commit / tested head: `69a14cec7b3ffa566c861346a9f4cbca925261f7`。
- final acceptance run: `34599710352` → **SUCCESS**。
- Knowledge Preflight：`寫技能`、`Python測試實務`、`phase6-release-packaging`、`monitoring-remote-qa` 全部 PASS；required references 全部 PASS。
- focused + project guards：**59 passed / 0 failed / 0.51s**。
- `config.ini` before / after SHA256 均為 `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`。
- `git diff --exit-code` PASS。
- remote re-read 已確認 `.agents/skills/engineering/Python測試實務/SKILL.md` 的中文 identity、pytest mechanics responsibility、isolation、one-way validation authority、real-seam mocking boundary、SKIP/PASS 與 focused/final acceptance 邊界。
- Registry 已反讀確認 `python-testing-practices → Python測試實務`；AI08 與 release manifest 亦已反讀確認 durable 納入。

## Temporary QA cleanup

- temporary workflow cleanup commit: `54d1d36974e0960912f2a9f2c84340ebdba6f177`。
- cleanup 後 branch Actions listing 仍為原本 **3 runs**；沒有 cleanup accidental rerun。
- `.github/workflows/python-testing-practices-skill-qa-20260911.yml` 在 cleanup commit 遠端 re-read → **404 Not Found**。
- evidence 不在 workflow path trigger，因此本 final evidence update 不會產生額外 QA run。

## Final drift policy

- tested head：`69a14cec7b3ffa566c861346a9f4cbca925261f7`。
- cleaned head 只可比 tested head 多：temporary workflow removal + 本 evidence terminal/cleanup 記錄。
- 不允許 Skill / Registry / tests / AI Library / release policy 在 GREEN 後發生未驗證 drift。
