# Issue #646 Phase6 Skill Preflight Evidence

TASK: Synchronize WHD scheduler/continuity governance surfaces with accepted #641-#645 machine behavior without changing scheduler cadence, automation IDs, lane owners, or machine ownership.

PLANNED_CHANGED_FILES:
- .agents/skills/engineering/executable-continuity-controller/SKILL.md
- .agents/skills/engineering/remote-execution-guard/SKILL.md
- .agents/skills/engineering/派工/SKILL.md
- docs/governance/whd_scheduler_takeover_usage.md
- 個人AI檔案庫/第二層_專案與SOP/11_WHD_Scheduled_Resume_ChatGPT自動續跑規則.md
- 個人AI檔案庫/第二層_專案與SOP/09_WHD_Canonical_Authority_Map.md
- 個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md
- 個人AI檔案庫/踩坑庫/scheduler_prompt_authoring_pitfall.md

REQUIRED SKILLS COMPLETED:
寫技能
派工
issue-closure-gate
遠端執行守門
monitoring-remote-qa
long-log-context-safe-execution
executable-continuity-controller
phase6-release-packaging

REQUIRED REFERENCES COMPLETED:
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/executable_continuity_controller_pitfall.md
READ_REFERENCE: release_required_artifacts.json

BASELINE:
workorder/issue640-guard-turn-exit-helper-hardening-20260925@d254729ec20f0d5da8542cf778c7cc0115abb776

MATRIX FINDINGS:
- executable-continuity-controller Skill still contains a stale one-argument assert_turn_exitable(checkpoint) example.
- accepted machine turn-exit requires checkpoint + claim/Guard transaction/Master context; trusted remote exit requires closed/completed Issue, RELEASED claim, no active remote run, no delegated work, exact identity, and TURN_EXIT_PERMITTED.
- checkpoint fingerprints must use load_checkpoint -> checkpoint_fingerprint / authorize-finalization canonical normalization; raw JSON SHA256 is invalid (#641).
- Guard transaction recovery must recognize PENDING / MUTATION_DONE_RECONCILE_ONLY / EXPIRED_UNCONSUMED / AMBIGUOUS and equivalent duplicate GREEN grouping (#643/#651).
- stale takeover must traverse delegated/helper/proof/blocking repair before parent staleness; helper reservation is atomic parent-claim CAS (#645).
- scheduler prompts/docs must point to canonical machine owners and must not hardcode issue IDs or duplicate stale algorithms.
