# 2026-09-10 找技能 Skill Preflight Evidence

Task: 依使用者上傳的 `找技能` SKILL.md 新增 WHD productivity Skill；保留「理解需求 → leaderboard/search → 品質驗證 → 呈現候選 → 使用者同意後安裝」的來源流程，但把 `npx skills` / `skills.sh` / 安裝能力改成 capability-adaptive，不得假裝已執行。外部 Skill 被找到不代表自動成為 WHD 專案 Skill；納入本專案需使用者明確決定並走 WHD 寫技能/Preflight/Registry 流程。

Baseline: `chore/normalize-chinese-skill-names-20260910 @ 0caac353ce0d1975df1397cb9b3db20ff3f451ed`
Work branch: `feat/add-find-skill-20260910`

## Source basis

User-provided file: `SKILL(1).md`
Canonical source identity: `name: 找技能`
Source workflow retained:
- understand what the user needs;
- check skills.sh leaderboard first when available;
- search using Skills CLI when available;
- verify quality before recommending;
- present options with source/install information;
- install only when user wants to proceed.

Source quality heuristics retained as heuristics rather than universal hard gates:
- prefer 1K+ installs;
- be cautious under 100 installs;
- inspect source reputation;
- inspect repository evidence such as GitHub stars; source says <100 stars deserves skepticism.

## Skills read / applied

- 寫技能
- phase6-release-packaging
- monitoring-remote-qa

## Required references read

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: release_required_artifacts.json

## Changed files

- `.agents/skills/productivity/找技能/SKILL.md`
- `.agents/skills/productivity/README.md`
- `.agents/skills/skill_registry.json`
- `個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md`
- `release_required_artifacts.json`
- `tests/test_find_skill_contract.py`
- temporary one-shot workflow used only for RED/GREEN verification, removed after terminal GREEN

## Requirement contract

1. Folder basename and frontmatter identity are both `找技能`.
2. Preserve the uploaded source's discovery/quality/recommend/install flow.
3. `npx skills`, `skills.sh`, web/CLI/catalog search and installation are capability-gated: use when actually available, otherwise report the gap and use available discovery paths.
4. Never claim a search/install occurred unless a real tool/command result exists.
5. Never auto-install or auto-admit an external Skill into WHD. User approval is required for installation; WHD project admission additionally requires project Skill governance.
6. Register `找技能` in Productivity README and machine-readable Registry.
7. Add durable AI guidance and release artifact protection.

## RED evidence

- run: `34499415197`
- head: `cd7897ab33a4a4b7c516d9d6cea2be9d7f14bfcd`
- Knowledge Preflight: PASS
  - required Skills: `寫技能`, `phase6-release-packaging`
  - required references: global pitfall library, WHD skill-authoring rules, release manifest
- contract: `tests/test_find_skill_contract.py`
- result: **8 failed / 0 passed / 0.19s**
- failures were requirement failures: missing `找技能/SKILL.md`, missing `skill-discovery` Registry route, missing Productivity README entry, missing AI durable boundary, missing release artifacts. No setup/import failure.

## Implementation summary

- Added `.agents/skills/productivity/找技能/SKILL.md` with canonical `name: 找技能`.
- Preserved source six-step discovery flow and source quality heuristics.
- Added capability detection: no fake `skills.sh`, `npx skills`, installs/stars/search/install results.
- Added explicit user-approval gate before installation.
- Added WHD admission boundary: external Skill discovery/install does not auto-create a WHD project Skill; project admission routes through `寫技能` + Preflight + branch-first + contracts/Registry/AI/release writeback.
- Added Productivity README entry and `skill-discovery` machine-readable Registry route.
- Added AI Library durable rules and release manifest protection.

## Targeted GREEN evidence

- run: `34499852951`
- head: `ce325d077532a19a330ae2d562dfe7cc0a11c81c`
- terminal conclusion: SUCCESS
- Knowledge Preflight: PASS
  - required Skills: `寫技能`, `找技能`, `phase6-release-packaging`
  - required references: global pitfall library, WHD skill-authoring rules, release manifest
- `tests/test_find_skill_contract.py`: **8 passed / 0 failed / 0.09s**

## Remote-run hygiene correction

The first one-shot workflow initially triggered on every branch push, causing intermediate implementation commits to create extra runs. Those intermediate runs are not final evidence. The trigger was narrowed to this evidence file only before the final matrix. The evidence update itself therefore produced one final equivalent verification run; that newest terminal run is the acceptance authority below.

## Final GREEN evidence

- final run: `34500275931`
- tested head: `18540328ad20e95c4fe07ff2df2bf3f91a5fb326`
- terminal conclusion: **SUCCESS**
- Knowledge Preflight: PASS
  - required Skills: `寫技能`, `找技能`, `phase6-release-packaging`
  - required references: global pitfall library, WHD skill-authoring rules, release manifest
- final regression matrix: **61 passed / 0 failed / 0.71s**
- matrix included:
  - `tests/test_find_skill_contract.py`
  - `tests/test_chinese_skill_identity_contract.py`
  - `tests/test_writing_skill_contract.py`
  - `tests/test_writing_skill_preflight_route.py`
  - `tests/test_dxf_skill_scope_contract.py`
  - `tests/test_phase6_skill_preflight_gate.py`
  - `tests/test_phase6_release_packaging_policy.py`
  - `tests/test_release_integrity_gate.py`

## Cleanup

- one-shot workflow: `.github/workflows/find-skill-contract-20260910.yml`
- cleanup commit: `e1fd158e103c75ddb89f9e841f0b1fe28213eef1`
- remote re-read after deletion: **404 Not Found**, expected.
- No further remote QA run can be triggered by this evidence update because the workflow is no longer present.

## Drift audit basis

Compare tested head `18540328ad20e95c4fe07ff2df2bf3f91a5fb326` to final branch head. Accept only:
1. deletion of the one-shot workflow;
2. this verification evidence update.

Any Skill, test, Registry, AI Library, release-policy, production, or configuration drift after the tested head invalidates the GREEN evidence.
