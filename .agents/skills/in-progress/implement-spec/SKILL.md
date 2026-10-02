---
name: implement-spec
description: "Implement an accepted specification in code. Fail closed when the specification or task authority is not accepted."
disable-model-invocation: true
whd_doc_role: REFERENCE
whd_contract: implement-spec
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Implement Spec

This skill starts **after specification authority is established**. It does not create a new phase, architecture, ownership boundary, task graph, or implementation scope.

## SPEC_AUTHORITY_GATE_V1

Before creating an implementation branch, PR, test, ticket, worktree, or product-code change, fresh-read the durable project sources and prove all of the following:

1. An **accepted specification** exists for the requested implementation scope.
2. The specification identifies the concrete scope/goal and protected boundaries.
3. The associated tickets/tasks are approved implementation work, not merely proposed ideas.
4. The current task is on the allowed task frontier and its predecessor/base is known.
5. Any required acceptance, A/B, invariant, cleanup, or closure gates are defined.
6. The requested work does not silently expand beyond the accepted specification.

If any required authority is missing, ambiguous, draft-only, or belongs to a completed prior phase:

```text
SPECIFICATION_REQUIRED
```

Fail closed. Return to specification/planning work. Do **not** create implementation tickets/branches, do RED/GREEN implementation, mutate runtime/product code, or merge QA/bootstrap changes to production.

A user message such as `繼續`, `GO`, or `輪` continues the **current accepted scope only**. It is not authorization to invent a new Phase or architecture.

Exploration done before acceptance is evidence for spec drafting only. Pre-spec exploratory code/tests/runs MUST NOT be treated as accepted implementation evidence or as the predecessor for a formal task unless the accepted spec explicitly adopts them.

## Execution model

You have been provided an **accepted** spec. This spec should have approved tickets associated with it, describing how to implement the spec.

The tickets are not a list of steps. They are a **task graph** with blocking relationships between them. This means there is always a **frontier** of tickets which are ready to be grabbed.

Communication to and from subagents should be sparse. Communicate primarily through **context pointers**: to the accepted spec, tickets, research notes, checkpoints, and previous accepted commits. Don't duplicate information already available via pointers.

Implementer subagents may be used concurrently only when the accepted task graph permits it. Concurrency must not violate predecessor, ownership, protected-file, or acceptance constraints.

## Steps

1. Fresh-read the accepted spec and approved tickets. Confirm the current frontier, predecessor/base, protected scope, and acceptance gates.

2. If authority is missing or the request would start a new unspecified phase/ownership boundary, stop implementation and return `SPECIFICATION_REQUIRED`.

3. Perform any allowed exploration required by the ticket. Exploration may produce notes/evidence but must not silently change the accepted scope.

4. Create the implementation branch/worktree and draft PR exactly as permitted by the accepted task contract.

5. Execute each ready ticket according to its required process (for example RED → intended RED → minimal GREEN → focused regression → A/B/invariant → integration/readback), without skipping gates merely because exploratory work already exists.

6. When a task completes, persist its accepted evidence/checkpoint before advancing the task frontier.

7. Start newly unblocked work only when the accepted graph allows it.

8. Once all implementation tickets are complete, run the required review/acceptance defined by the spec. Fix only in-scope findings.

9. Mark the PR ready or integrate/close only when the accepted specification's finalization/closure gates pass.

10. Clean up temporary worktrees, workflows, helpers, and exploratory artifacts as required by the accepted spec.

## Prohibited shortcuts

- `continuity` or "keep going" does not bypass spec authority.
- A completed prior phase does not authorize inventing the next phase.
- A technical recommendation is not an approved architecture decision.
- A GREEN exploratory run is not accepted evidence by itself.
- Do not substitute a newer baseline/predecessor unless the accepted spec explicitly permits it.
