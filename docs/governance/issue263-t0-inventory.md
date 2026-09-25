---
whd_doc_role: HISTORICAL
whd_contract: issue263-governance-inventory
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# #263 T0 — Governance inventory and conflict audit

## Frozen identity

- `TASK_ID`: `#263`
- `TARGET`: `cleanup/2d-3d-sync` (X)
- `MASTER_BASE_SHA`: `0e20662d4e36907d5e529346cccb2a5cafbf4f72`
- `CHAIN_BASE_BRANCH`: `governance/issue262-x-independent-task-chain`
- `WORK_BRANCH`: `governance/issue263-t0-inventory`
- `EXPECTED_PARENT_SHA`: `0e20662d4e36907d5e529346cccb2a5cafbf4f72`
- `SCOPE`: evidence-only governance inventory/audit
- `X_MERGE`: forbidden for this stage and for the #262 chain until later explicit authorization

The chain contract is frozen at creation time. An in-flight task chain must not refresh, rebase, or merge newer X into itself, and it must not import sibling task-chain production changes.

## Frozen authorities inventoried

The following authorities were inspected at the frozen base and are in scope for later governance implementation:

- `.agents/skills/engineering/派工/SKILL.md`
- `.agents/skills/engineering/執行開發任務/SKILL.md`
- `.agents/skills/engineering/issue-closure-gate/SKILL.md`
- `.agents/skills/engineering/monitoring-remote-qa/SKILL.md`
- `.agents/skills/engineering/executable-continuity-controller/SKILL.md`
- `.agents/skills/engineering/拆解任務工單/SKILL.md`
- `.agents/skills/skill_registry.json`
- `.agents/skills/skill_catalog.json`
- `tools/execution_claim_guard.py`
- `AGENTS.md`
- `.github/workflows/knowledge-governance-bootstrap.yml`
- frozen `.github/workflows/` inventory

This T0 document records findings only. It does not modify any authority above.

## Decisions and conflict audit

| Area | Frozen state | T0 decision | Required follow-up |
| --- | --- | --- | --- |
| Issue closure | Existing closure governance already separates integration from completion/acceptance. | **Retain.** Do not collapse task acceptance into branch integration. | Later stages must preserve the distinction between Task Acceptance and Integration Acceptance. |
| Execution claim | `派工` requires a shared/atomic execution claim before repo writes; issue assignee/comment/label are not authority. `tools/execution_claim_guard.py` validates supplied claim state. | **Retain hard gate.** | Make claim namespace/lifecycle discoverable and executable; keep pre-write validation fail-closed. |
| Task decomposition | Existing task decomposition does not fully encode frozen X identity, immutable chain base, accepted-parent lineage, or cross-chain isolation. | **Missing governance.** | T1–T3 must add explicit identity and lineage gates with negative tests. |
| Branch model | Existing dispatch language contains an older “工單主分支” model while #262 requires a fresh stage branch from the previous accepted stage HEAD. | **Ambiguous/overlapping contract.** | Clarify/supersede old wording so stage lineage is deterministic and cannot silently chase X. |
| Remote QA | Remote QA governance already requires concrete run/head evidence before treating QA as authoritative. | **Retain, extend identity binding.** | T4 must bind RUN evidence to `TASK_ID`, frozen `BASE_SHA`, `EXPECTED_PARENT_SHA`, exact `CHAIN_HEAD`, and `TARGET=X`. |
| No-RUN behavior | A concrete RUN identity is required for polling, but the full task-chain contract does not yet make `RUN NOT CREATED` a first-class fail-closed transition. | **Missing executable rule.** | T4 must require immediate prerequisite execution/fix when no RUN exists; do not wait/poll without a RUN ID. |
| Continuity | Continuity controller provides restart/continuation structure but does not by itself prove frozen-base/accepted-parent/cross-chain identity. | **Retain, extend.** | Propagate the task-chain identity tuple through continuity/recovery paths. |
| Registry/catalog/AGENTS/knowledge | These are durable discovery/knowledge surfaces, not substitutes for executable gates. | **Do not claim governance complete from documentation alone.** | T7 writes back only after executable enforcement and regression evidence exist. |

## Missing enforcement to implement after T0

1. **Frozen task-base identity** — every independent chain must record and preserve `TARGET=X` and the X SHA captured at task creation.
2. **Accepted-parent lineage** — each next stage must start from the previous stage's accepted HEAD, with `EXPECTED_PARENT_SHA` checked fail-closed.
3. **Cross-chain isolation** — reject newer-X merges/rebases, sibling merges, silent sibling production cherry-picks, and frozen-base replacement while a chain is active.
4. **Identity propagation** — dispatch, preflight, continuity, remote QA, and acceptance evidence must carry the same task/branch/base/parent/head/target identity.
5. **RUN identity transition** — no concrete RUN ID means `RUN NOT CREATED`, not “wait”; execute/fix the prerequisite that should create the RUN.
6. **Atomic chain acceptance** — a partial Tn result cannot authorize integration. Full-chain Task Acceptance is required before Integration Acceptance is even considered.
7. **Current-X integration readiness** — compare completed frozen-lineage work against current X separately; readiness proof is not an X merge.
8. **Validation authority boundary** — tests, expected values, DXF/reference outputs, or collision/reference evidence judge correctness only and must never become production geometry/calculation sources.

## Execution-claim evidence for T0

T0 execution uses the shared coordination ref `claims/issue-263`, not issue assignment/comment metadata.

- claim commit: `e60809e…`
- claim parent: frozen base `0e20662d4e36907d5e529346cccb2a5cafbf4f72`
- claim tree: `39008047badcaf3f06cfc758a0a282e6794eaa9e`
- claim blob: `3a3586a7da25994115038d15a092284437a4c467`
- claim payload binds issue `#263`, the T0 work branch, and the frozen base
- frozen `tools/execution_claim_guard.py --action write` was executed against the claim state and passed before the T0 repo write

### Claim defect recorded for later repair

The live claim tree currently contains a claim-path name with a trailing carriage return (`\r`). The claim blob itself is readable and the shared claim remains resolvable, but the malformed path is a concrete lifecycle/usability defect. T0 records it; T0 does **not** repair claim infrastructure because this stage is evidence-only.

## T0 acceptance gates

T0 is accepted only if all of the following are freshly verified after this audit commit:

- the T0 commit parent is exactly `0e20662d4e36907d5e529346cccb2a5cafbf4f72`;
- the frozen-base → T0 diff contains only this evidence artifact;
- no production file or Skill authority is changed by T0;
- X (`cleanup/2d-3d-sync`) remains unchanged at the frozen SHA;
- there is no merge back to X;
- the T1 branch, when created, starts from the accepted T0 HEAD rather than from current X.

## T1 handoff contract — #264

T1 must implement/encode and test the X identity + frozen-base contract:

- `TASK_ID=#264`
- `TARGET=cleanup/2d-3d-sync`
- immutable chain/frozen `BASE_SHA`
- explicit `EXPECTED_PARENT_SHA=<accepted T0 HEAD>`
- fresh T1 branch from the accepted T0 HEAD
- reject implicit refresh/rebase/merge to newer current X
- fail closed on identity/base mismatch
- include negative tests proving invalid base-refresh behavior is rejected

T1 must not merge to X. Subsequent stages remain `T1 → T2 → T3 → T4 → T5 → T6 → T7`; T7 stops at `ACCEPTED / READY_FOR_X_INTEGRATION` unless a later explicit authorization permits X integration.

## Durable chain rule

> X 建任務、任務凍結；各鏈獨立、鏈內串接；期間不追 X、不吃別鏈；整鏈驗完，最後才合 X。
