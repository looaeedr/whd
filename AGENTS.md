---
whd_doc_role: HISTORICAL
whd_contract: agent-startup-process
whd_canonical: cleanup/2d-3d-sync:AGENTS.md
whd_schema: WHD_DOC_META_V1
---
<!-- MAIN_DEFAULT_BRANCH_FAIL_CLOSED_V2 -->

# main default-branch fail-closed tombstone

`main` is not WHD production execution, governance, Skill, documentation, or process authority.

Any runtime that reached this file through an omitted ref, default-branch fetch, repository landing page, default code search, or stale index **must stop before substantive analysis, Skill routing, claim/ExecutionRecord reads, mutation, workflow dispatch, QA, merge, finalization, or completion judgment**.

Required recovery:

1. Resolve the live `cleanup/2d-3d-sync` HEAD explicitly.
2. Re-read `cleanup/2d-3d-sync:AGENTS.md`.
3. Re-read any required Skill/Registry/Authority Map from that same explicit production ref.
4. Fail closed if the caller cannot bind reads/actions to live `cleanup/2d-3d-sync`.

No main↔cleanup mirror, parity, ancestry reconciliation, production write, or fallback execution is authorized here.

<!-- /MAIN_DEFAULT_BRANCH_FAIL_CLOSED_V2 -->
