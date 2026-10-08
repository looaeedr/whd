---
whd_doc_role: REFERENCE
whd_contract: dm8-runtime-facade-design
whd_canonical: .agents/contracts/WHD_DM8_RUNTIME_FACADE_DECISION_V1.json
whd_schema: WHD_DOC_META_V1
---

# DM8-A1 / #1379 — O2 runtime facade Design It Twice

## Inputs

T0 / #1378 established the current behavior that the facade must preserve:

- MERGE / ALREADY_MERGED is readback-only; merge PUT count is zero.
- SYNC_TARGET may discover that target ancestry is already applied; POST /merges count is zero on that path.
- FINALIZE may discover the Issue is already closed/completed; close PATCH count is zero.
- RELEASE_PATHS is not an external mutation merely because of transaction kind.
- stale RELEASE_PATHS becomes a conditional external mutation only when an exact stale branch exists and DELETE is actually required.
- unrelated coord CAS retries must not replay a provider mutation; same-Issue drift must fail closed and rebuild semantics.

## Option A — command-style single runtime entry

Shape:

`execute_runtime_command(kind, record, payload, provider)`

Advantages:
- small call site
- easy migration from the current production executor

Rejected because:
- transaction kind becomes the dominant public identity instead of the exact `ControlTransactionPlan`
- encourages semantic validation, provider branching, and transport handling to reconverge inside one dispatcher
- readback-only fencing becomes a collection of command-specific exceptions
- error ownership becomes ambiguous
- easiest option to grow a second semantic switch parallel to `control_transaction.py`

## Option B — typed runtime object

Shape:

`ControlTransactionRuntime(provider).merge(...).sync_target(...).finalize(...)`

Advantages:
- discoverable typed methods
- provider can be injected for tests

Rejected because:
- largest public surface
- object lifetime invites cached record/plan/provider state
- method-specific lifecycle can become a second state machine
- harder to prove semantic uniqueness
- transport replacement is coupled to object shape and lifetime
- unnecessary for the current stateless effect-resolution boundary

## Option C — pure plan + effect adapter

**Selected.**

Target public shape:

```python
resolve_runtime_effect(
    record: ExecutionRecord,
    plan: ControlTransactionPlan,
    *,
    mode: RuntimeMode,
    provider: RuntimeProvider,
    supplied_effect: Mapping[str, object],
) -> RuntimeEffectEnvelope
```

The returned envelope contains:

- `effect` — the exact effect mapping later reconciled by `control_transaction.execute_transaction`
- `path_class` — `READBACK_ONLY` or `PRE_TRANSITION_EXTERNAL_MUTATION`
- `provider_mutation_performed` — diagnostic/retry evidence only, never semantic authority

The facade **does not** own ExecutionRecord transitions. Exact-plan validation remains public authority in `tools/control_transaction.py`; the runtime facade must call that owner instead of duplicating validation.

## Readback-only mode fence

`RuntimeMode.READBACK_ONLY` is a pre-provider-mutation fence, not a transaction-kind allowlist.

The runtime may perform provider reads needed to discover the live path. If the live path would cross into a provider mutation, it raises `RuntimeMutationFenceError` **before** the provider mutation call.

| Transaction | Readback-only continuation | Mutation branch blocked by READBACK_ONLY |
| --- | --- | --- |
| MERGE | ALREADY_MERGED or TARGET_DRIFT readback | READY_TO_MERGE before PUT merge |
| SYNC_TARGET | work branch already proves prior head + target ancestry | before POST /merges |
| FINALIZE | Issue already closed/completed | before PATCH close |
| RELEASE_PATHS | ACTIVE/non-stale path or stale branch already absent | stale proven branch before DELETE |

`START_BRANCH` and `APPLY_COMMIT` are explicitly outside this external-mutation facade scope. They remain under the existing repository-content writer / mutation-writer guard.

## Error domains

Semantic errors remain owned by `control_transaction.py`:

- `ControlTransactionError`
- `ControlTransactionConflict`
- `ControlTransactionReplay`

Facade-only error:

- `RuntimeMutationFenceError` — the selected runtime mode forbids the provider mutation branch reached after readback.

Provider transport failures may be normalized as `RuntimeProviderError`, but the facade must not reinterpret them as semantic conflicts or mutate ExecutionRecord state by itself.

## Retry boundary for A3

The runtime facade resolves one immutable `RuntimeEffectEnvelope` per exact plan attempt.

- unrelated coord CAS race: reuse the same resolved envelope / post-record; do not re-enter provider mutation
- same-Issue drift: discard the old plan/effect continuation and require a fresh semantic rebuild
- the facade does not own coord CAS retry state
- A3 owns retry orchestration and must preserve the T0 no-replay evidence

## Decision

`PLAN_EFFECT_ADAPTER` is the minimal public facade because it keeps the architecture one-directional:

`ExecutionRecord + ControlTransactionPlan` → semantic validation in `control_transaction.py` → runtime effect resolution/fence → `RuntimeEffectEnvelope.effect` → semantic reconciliation in `control_transaction.py`.

There is no second semantic owner and no second state machine.
