---
whd_doc_role: REFERENCE
whd_contract: issue1379-o2-runtime-facade-design
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #1379 / DM8-A1 — O2 runtime facade Design It Twice

## Decision

Selected: **PLAN_EFFECT_ADAPTER**.

The runtime facade must remain a small, stateless provider/effect boundary. `tools/control_transaction.py` remains the single semantic owner and the only owner of public exact-plan validation.

Proposed shape:

`resolve_runtime_effect(record, plan, mode, provider, supplied_effect) -> RuntimeEffectEnvelope`

The returned envelope contains the resolved effect, the classified runtime path, and whether a provider mutation was performed. The caller still reconciles through `tools.control_transaction.execute_transaction(...)`.

There is no second semantic owner and no second state machine.

## Option A — command-style single runtime entry

Shape: `execute_runtime_command(kind, record, payload, provider)`

Rejected. The command-first shape tends to combine semantic validation, provider branching, mutation fencing, and transport failures in one dispatcher. That weakens exact-plan visibility and turns READBACK_ONLY into command-specific exceptions.

## Option B — typed runtime object

Shape: `ControlTransactionRuntime(provider).<method>(...)`

Rejected. The object surface is larger and invites cached runtime/lifecycle state, creating pressure toward a second stateful owner beside `control_transaction.py`.

## Option C — pure plan + effect adapter

Shape: `resolve_runtime_effect(record, plan, mode, provider, supplied_effect) -> RuntimeEffectEnvelope`

**Selected.**

This is the smallest surface that keeps semantic validation in `control_transaction.py`, makes provider and READBACK_ONLY fencing injectable, keeps error domains explicit, and lets A3 reuse one immutable resolved effect across unrelated coord CAS retries without replaying provider mutation.

## Evaluation dimensions

- interface surface: one narrow stateless entry
- error domain: semantic, runtime-fence, and provider-transport failures remain distinct
- test setup: explicit provider/mode injection
- diagnosability: RuntimeEffectEnvelope reports effect, path class, and whether provider mutation occurred
- mutation-fence enforceability: READBACK_ONLY raises before provider mutation
- transport replaceability: provider is injected
- semantic-owner uniqueness: `tools/control_transaction.py` remains authoritative

## READBACK_ONLY fence

READBACK_ONLY may perform provider reads required to classify the live path, but it must raise before any provider mutation branch.

Exact PRE_TRANSITION external mutation paths:

- MERGE: only READY_TO_MERGE before `PUT /pulls/{pr}/merge`
- SYNC_TARGET: only the branch requiring `POST /merges`
- FINALIZE: only when fresh Issue readback is not already closed/completed, before PATCH close
- RELEASE_PATHS: only stale RELEASED cleanup when the exact stale branch exists and DELETE is required

Explicitly excluded:

- START_BRANCH
- APPLY_COMMIT

## Error domains

- semantic: `ControlTransactionError`, `ControlTransactionConflict`, `ControlTransactionReplay`
- runtime fence: `RuntimeMutationFenceError`
- provider transport: `RuntimeProviderError`

## Retry contract for A3

- provider effect resolution occurs exactly once per immutable plan attempt
- unrelated coord CAS retry reuses the same RuntimeEffectEnvelope/post-record and does not replay provider mutation
- same-Issue drift invalidates the old plan/effect continuation and requires a fresh semantic rebuild
- retry orchestration belongs to the caller/orchestrator, not the facade

## Non-goals

- No runtime implementation in #1379
- No second ExecutionRecord/state machine
- No START_BRANCH/APPLY_COMMIT migration
- No retry restructuring before A3
