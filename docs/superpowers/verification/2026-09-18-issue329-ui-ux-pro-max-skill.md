# Issue #329 — UI UX Pro Max → WHD canonical UI skill

- owning issue: https://github.com/looaeedr/whd/issues/329
- target: `cleanup/2d-3d-sync`
- frozen base/head before write: `7de32d6c53864ae48b276d4817f4a00e3baaa846`
- work branch: `skill/issue329-ui-ux-pro-max-20260918`
- worker: `chatgpt-gpt5.6-sol`
- upstream inspected: `nextlevelbuilder/ui-ux-pro-max-skill@15de38fb70bc80ae9276fa7703b48ae861a672e6`
- upstream canonical skill: `.claude/skills/ui-ux-pro-max/SKILL.md`

## Knowledge preflight

REQUIRED_SKILL: UI設計與去AI味
REQUIRED_SKILL: 寫技能
REQUIRED_SKILL: phase6-release-packaging
REQUIRED_SKILL: monitoring-remote-qa
REQUIRED_SKILL: long-log-context-safe-execution
REQUIRED_SKILL: executable-continuity-controller

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: release_required_artifacts.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md

## RED

Baseline lacks both the UI UX Pro Max registry aliases and the pinned canonical upstream marker, so the new contract is intentionally RED on the frozen base.

## Design decision

Do not create a competing `ui-ux-pro-max` CURRENT skill. Integrate it as capability-checked external design intelligence under WHD's existing canonical `UI設計與去AI味` authority, then filter through WHD's Tkinter/ttk, functionality-first, domain-preservation and real-GUI acceptance rules.

## Intended changed files

- `.agents/skills/engineering/UI設計與去AI味/SKILL.md`
- `.agents/skills/skill_registry.json`
- `tests/test_ui_design_de_ai_skill_contract.py`
- `個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md`
- this evidence file

## Verification

Focused remote QA will execute the UI contract, Skill-authoring/governance guards, and changed-file Phase6 Knowledge Preflight against the exact QA head. The one-shot workflow is temporary and must be removed after terminal evidence; file write alone is not acceptance.
