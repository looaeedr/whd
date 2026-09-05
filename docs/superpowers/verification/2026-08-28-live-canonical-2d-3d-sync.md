# 2026-08-28 Live Canonical 2D/3D Sync Verification

## Scope
- Remove Fold Designer confirm/cancel production draft semantics.
- Publish all production 3D edits immediately to main canonical state.
- Make 2D / 3D assembly / DXF replay use one Manufacturing PartSpec -> PartRenderData chain.
- Make Head/Tail dynamic relief atomic.
- Reject/clear stale relief fingerprints.

## Direct user-file evidence
Fixture: `/mnt/data/自訂(6).p6fold`.
- Current project assembly semantic: `INSERT_OVERLAY`.
- Saved old relief source: `INSERT`.
- `_end_cap_part_spec(...).resolved_assembly_relief_cuts == ()` before a fresh verified solve.
- Opening live designer and publishing clears the stale relief instead of persisting it as production geometry.
- If one EndCap solver fails, no partial Head/Tail relief is committed.
- Assembly provider EndCap material equals main 2D authoritative EndCap material (`symmetric_difference.area <= 1e-6`).

## Focused fresh regression
Command includes live canonical, real p6fold, GUI open/close/save, settings, assembly and collision integration tests.
Result: **77 passed / 0 failed**.

## Broader comparison
- 3D / assembly / FinalScene batch: working tree **106 passed + 3 failed**. The same three tests fail on unmodified `204426 FULL` with the same assertions; no new regression attributed to this change.
- Corner / Manufacturing legacy batch: working tree **58 passed + 18 failed**. Unmodified `204426 FULL` also has **58 passed + 18 failed**, same named legacy failures. These are baseline debt, not used as a completion gate for live-sync.

## Invariants
1. No `begin_designer()` on the formal 3D open path.
2. No `on_transaction_confirm` / `on_transaction_cancel` wiring on the formal 3D open path.
3. No visible confirm/cancel buttons; reset remains.
4. Close = flush + save visible editor + force live publish + destroy; no rollback.
5. Solver private render is verification-only; production render comes back through the host Manufacturing provider.
6. Head/Tail commits are all-or-nothing.
7. Stale source fingerprint cannot replay production cuts.
8. Live sync does not auto-save the project file or `config.ini`.
