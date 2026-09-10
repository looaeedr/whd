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

Remote QA, when started, must be monitored to terminal and cleaned before acceptance.

QA trigger note: this commit exists only to trigger the already-registered one-shot branch workflow after its creation commit produced no run.
