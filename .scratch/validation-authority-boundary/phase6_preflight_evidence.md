# Validation Authority Boundary — Phase6 Preflight Evidence

- task: 驗證只能拿來判定對不對，不能反過來當 production 計算來源；加入 Skill 與 AI Library
- repository: looaeedr/whd
- branch: docs/validation-authority-boundary
- parent: cleanup/2d-3d-sync@b8f08cfbf6fa83617135da70648c946aefe74bd4

READ_SKILL: phase6-release-packaging
READ_SKILL: phase6-corner-3d-model-integrity
READ_SKILL: tdd

READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: release_required_artifacts.json
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md

## RED baseline
- phase6-corner-3d-model-integrity explicit "validation is not calculation source": false
- explicit ban on pytest expected/tolerance feeding production: false
- explicit ban on validation measurement backfeed: false

## Scope expansion
- Added general TDD authority boundary after locating the project-wide tdd Skill.

## Intended files
- .agents/skills/engineering/tdd/SKILL.md
- .agents/skills/engineering/phase6-corner-3d-model-integrity/SKILL.md
- 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
- 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
