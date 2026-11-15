---
name: resolving-merge-conflicts
description: Resolve verified GitHub PR or authorized git merge/rebase conflicts without losing either side's accepted changes, inventing local state, or bypassing localX CI and release gates.
whd_doc_role: CURRENT
whd_contract: resolving-merge-conflicts
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Resolving Merge Conflicts

## WHD source and authority

1. Fresh-read GitHub `localX` **latest exact HEAD** `AGENTS.md`, the current work PR/branch base/head SHA, both conflicting diffs and affected CURRENT domain rules. WHD development/Governance merges target GitHub `localX`. The historic `main` and release X=`cleanup/2d-3d-sync` must not become a daily conflict-resolution baseline; formal X needs the user's current `/推推` and trusted gate.
2. Verify **real conflicts** using the PR mergeable state and exact base/head comparison, or an already-authorized executor's real git status. A GitHub Connector without an authorized checkout can inspect and modify a scoped work branch via available GitHub APIs; it cannot claim a local rebase, staging or test execution. No Windows/DC/RC probing or shell escalation.
3. For each conflicting hunk, read both change intents, source functions, owning Issue/PR, related tests and independent authority. Keep both accepted changes where compatible. If incompatible or authority is unknown, **fail closed with `MERGE_CONFLICT_AUTHORITY_UNRESOLVED`**, report the precise conflict and continue read-only investigation. Do **not** force a resolution, reset, rebase, overwrite history or invent product geometry.
4. Only after resolving the verified conflict in the authorized work branch, run true targeted tests in a permitted executor when available (`TARGETED_NOT_RUN` otherwise), then require fresh exact HEAD GitHub CI. A conflict-free text merge alone is not a passing regression.
5. Recheck branch/base drift, scope, mergeable and all required CI on the final exact PR head; use safe GitHub PR merge with `expected_head_sha` and read back the resulting GitHub `localX` HEAD. Never force push or treat a PR merge as formal X publication.

When a merge/rebase is genuinely in progress in an **explicitly authorized git workspace**, use its real status and permitted commands; if a safe resolution is impossible, preserve both sides and stop with a concrete blocker. No unconditional "always resolve" or "never abort" rule overrides data integrity or GitHub authority.
