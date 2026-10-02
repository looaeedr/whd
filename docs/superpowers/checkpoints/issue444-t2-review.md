# Issue #444 / T2 — Review & Acceptance Evidence

- Master: #441
- Task: #444 — BendingUI owner + symmetry/profile compatibility seam
- Accepted predecessor: `76661e3908894d29c2e2704e646e68ea5ac638e0`
- Tested head: `a992b2d637dfef58ec2a94c99e65b433aef12916`
- Cleaned head before review: `d266b3b13a2d530badb789ea0d9d99fae3caf890`
- Remote QA: RUN `35544127302` / job `106166915891` / SUCCESS
- Focused result: `8 passed in 1.88s`

## Acceptance gates

```text
BENDING_UI_OWNER=phase6_bending_ui.py
BENDING_UI_DEFINED_IN_BRIDGE=0
BRIDGE_REVERSE_IMPORT=0
PROFILE_RESOLVER_BRIDGE_COMPAT=1
SYMMETRY_TRANSACTION_DELEGATE_COMMIT_SYMMETRY=1
OWNER_ACTION_BEFORE_PREDECESSOR_INIT=1
MONKEY_PATCH_NORMAL_RESTORE=1
MONKEY_PATCH_EXCEPTION_RESTORE=1
STALE_SOURCE_TEST_MIGRATIONS=2
INVARIANT_WEAKENING=0
FACADE_BINDINGS_BASELINE=69
FACADE_BINDINGS_HEAD=69
FACADE_BINDING_GROWTH=0
TESTED_TO_CLEANED_DRIFT=WORKFLOW_DELETE_ONLY
T2_DECISION=GREEN
```

## Evidence

- The extracted owner module defines `Phase6BendingUI`; bridge no longer defines the class and imports the compatibility delegates from `phase6_bending_ui.py`.
- The bridge retains `_phase6_on_box_symmetry_changed` and its `commit_symmetry` delegate.
- Constructor remains `(parent, state, update_cb)`; no fourth DI argument was added.
- Temporary `original.BendingUI` replacement is restored on both normal and injected-exception predecessor init paths.
- The two stale source tests now read the BendingUI owner file while preserving the original assertions that the symmetry control exists in the fold editor and not in the Settings owner.
- The T0 facade census baseline was 69 bindings; exact dictionary-key recount at the cleaned T2 head remains 69.
- RUN `35544127302` tested exact HEAD `a992b2d637dfef58ec2a94c99e65b433aef12916` and reported `8 passed in 1.88s`.
- The only tested-head → cleaned-head change is removal of `.github/workflows/qa-issue444-t2-focused-20260921.yml`.

## Decision

T2 is accepted on its canonical #443 lineage. No production/X merge is performed here. The closing HEAD from this review becomes the authoritative predecessor for #445.
