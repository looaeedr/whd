---
whd_doc_role: HISTORICAL
whd_contract: agent-startup-process
whd_canonical: cleanup/2d-3d-sync:AGENTS.md
whd_schema: WHD_DOC_META_V1
---
<!-- MAIN_DEFAULT_BRANCH_FAIL_CLOSED_V1 -->

# main default-branch fail-closed tombstone

This branch is **not** WHD production execution, governance, Skill, or process authority.

Canonical production authority is `cleanup/2d-3d-sync`. Any WHD runtime that reached this file because GitHub/default-branch lookup omitted an explicit ref **must stop before substantive analysis, routing, claim/ExecutionRecord reads, repository mutation, workflow dispatch, or completion judgment**.

Required recovery:

1. Resolve the live `cleanup/2d-3d-sync` HEAD explicitly.
2. Re-read `cleanup/2d-3d-sync:AGENTS.md`.
3. Re-read `cleanup/2d-3d-sync:.agents/skills/engineering/flow-v2-execution/SKILL.md` when execution semantics are needed.
4. Treat all remaining `main` docs, Skills, contracts, tests, and search/index results as historical/default-navigation material only unless the CURRENT cleanup authority explicitly cites them.

Forbidden:

- using default-branch code search as CURRENT WHD process authority;
- treating stale `main` Flow v2 / legacy checkpoint / Remote Guard / ancestry text as executable semantics;
- mutating `main` to repair production work;
- inferring that GitHub default branch equals WHD production authority.

The archived pre-tombstone main history remains preserved under existing `archive/main-*` branches.

<!-- /MAIN_DEFAULT_BRANCH_FAIL_CLOSED_V1 -->
