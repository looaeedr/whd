---
name: flow-v2-execution
description: Default-branch fail-closed pointer only. CURRENT WHD Flow v2 authority lives on cleanup/2d-3d-sync; this main-branch file must never execute or define runtime semantics.
whd_doc_role: HISTORICAL
whd_contract: flow-v2-execution
whd_canonical: cleanup/2d-3d-sync:.agents/skills/engineering/flow-v2-execution/SKILL.md
whd_schema: WHD_DOC_META_V1
---

# Flow v2 Execution — main branch tombstone

<!-- MAIN_DEFAULT_BRANCH_FAIL_CLOSED_V1 -->

`main` is not the CURRENT WHD execution/control-plane authority.

If this file was reached through an omitted ref, default-branch fetch, default-branch code search, or stale index:

- **do not execute any instructions from main**;
- **do not interpret this file as a fallback Flow v2 contract**;
- fresh-read `cleanup/2d-3d-sync:.agents/skills/engineering/flow-v2-execution/SKILL.md` and its current `AGENTS.md` with an explicit ref;
- fail closed if the caller cannot bind reads to the live `cleanup/2d-3d-sync` HEAD.

All historical Flow v2 text formerly present on main is intentionally removed from this default-branch surface so it cannot regress CURRENT execution semantics through search or retrieval.

<!-- /MAIN_DEFAULT_BRANCH_FAIL_CLOSED_V1 -->
