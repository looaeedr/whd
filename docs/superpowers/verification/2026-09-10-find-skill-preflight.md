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

## Required references read

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: release_required_artifacts.json

## Planned changed files

- `.agents/skills/productivity/找技能/SKILL.md`
- `.agents/skills/productivity/README.md`
- `.agents/skills/skill_registry.json`
- `個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md`
- `release_required_artifacts.json`
- `tests/test_find_skill_contract.py`
- temporary one-shot workflow used only for RED/GREEN verification

## Requirement contract

1. Folder basename and frontmatter identity are both `找技能`.
2. Preserve the uploaded source's discovery/quality/recommend/install flow.
3. `npx skills`, `skills.sh`, web/CLI/plugin search and installation are capability-gated: use when actually available, otherwise report the gap and use available search/discovery paths.
4. Never claim a search/install occurred unless a real tool/command result exists.
5. Never auto-install or auto-admit an external Skill into WHD. User approval is required for installation; WHD project admission additionally requires project Skill governance.
6. Register `找技能` in Productivity README and machine-readable Registry.
7. Add durable AI guidance and release artifact protection.
