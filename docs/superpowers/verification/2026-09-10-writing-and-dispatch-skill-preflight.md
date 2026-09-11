# 2026-09-10 寫技能 / 派工 Skill Preflight Evidence

Task: 修復使用者提供的 `寫技能`，再用修復後規則修改 `.agents/skills/engineering/派工/SKILL.md`，並依使用者明確指示把 frontmatter 名稱改成 `派工`。

Baseline target: `cleanup/2d-3d-sync @ 925808ab29009bff76670daf7dbbccc232e33b6b`

Work branches:
- `chore/repair-writing-skill-20260910`
- `chore/repair-dispatching-skill-20260910`

## Skills read / applied

- 寫技能
- 派工
- diagnosing-bugs
- tdd
- phase6-release-packaging

## Required reference evidence

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: release_required_artifacts.json

## Baseline snapshot

Original uploaded `寫技能` was 485 lines and contained Claude/Cowork-specific hard assumptions including `claude-with-access-to-the-skill`, background runs, required eval-viewer flow, `run_loop.py`, and an unconditional existing-skill name-preservation rule.

Original repo `派工` blob: `9e84b1f9634d44bdd46dfac1a420c583b0c2d47b`.
Original frontmatter: `name: dispatching`.
Original section ordering was structurally drifted (`3.5.2` before `3.5.1`, `3.7/3.8` before `3.6`, and `3.5.4` after section 6).

## Approved correction authority

- Existing skill identity is preserved by default.
- User explicitly requested this rename, so the canonical dispatch skill identity is now `name: 派工`.
- Rename must propagate to Skill frontmatter, Registry, tests and durable AI guidance.
- Validation evidence judges correctness only; it is not a production/domain calculation source.

## Verification scope

Targeted contracts:
- `tests/test_writing_skill_contract.py`
- `tests/test_writing_skill_preflight_route.py`
- `tests/test_dispatching_skill_timeout_contract.py`
- `tests/test_phase6_skill_preflight_gate.py`
- release packaging policy around mandatory Skill artifacts

## Remote QA history

- Run `34493460914` at `e426f64dd29fe2d44dcb5f2d010f4b10baa4a626`: Preflight PASS; targeted contracts 34 PASS / 1 FAIL. Failure was a contract false negative: exact substring `不存在的背景` was required even though the Skill already enforced no fake background runtime. Production/Skill behavior was not relaxed; the contract was corrected to assert the behavior instead of one exact phrase.
- Final tested run `34493539025` at `c37c8e6609db882d718b383103833651e36dd754`: `completed + success`.
- Final Preflight on that run: `寫技能`, `派工`, `phase6-release-packaging`, `diagnosing-bugs`, `tdd` all PASS; global AI pitfall, WHD skill-authoring AI rule and `release_required_artifacts.json` references all PASS.
- Final targeted contracts: **35 passed / 0 failed / 0.34s**.

## Cleanup / drift audit basis

- One-shot QA workflow `.github/workflows/skill-contract-check-20260910.yml` was deleted after terminal GREEN in cleanup commit `32d1058b5069636deca60b2f5224890e9c3755aa`.
- Re-read after deletion returned 404/Not Found as expected.
- Push-run count remained 3 after cleanup; no replacement non-terminal run was created.
- Tested head for behavior: `c37c8e6609db882d718b383103833651e36dd754`.
- Final branch drift must be limited to QA workflow deletion plus this durable verification evidence update; any Skill/test/Registry/AI-policy drift after tested head is not acceptable.
