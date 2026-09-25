# Issue #443 / T1 — Review & Acceptance Evidence

- Master: #441
- Accepted predecessor: #442
- Accepted predecessor HEAD: `cf14e2e6b7ba9d28109d94cd1010867a29e8c157`
- T1 GREEN head before closing seal: `9786a04911552cda257b6d2da31107711f93c22c`
- Intended RED RUN: `35513330235` / `PASS EXPECTED_T1_RED=1`
- Baseline A/B RUN: `35513915340`
- GREEN RUN: `35514014820`

## Production delta

Exactly two zero-caller historical builders were deleted from `fold_designer_bridge.py`:

- `_phase6_build_assembly_settings`
- `_phase6_build_box_symmetry_settings`

No replacement wrapper or duplicate Settings UI was added.

## Machine evidence

```text
T1_DEAD_GLUE_GREEN=1
focused ownership = 3 passed
baseline A/B = INHERITED_BASELINE_DEBT
candidate-only GUI failure = 0
manufacturing/DXF acceptance = 12 passed
DXF_GIT_OBJECT_INVARIANT=1
CONFIG_GIT_OBJECT_INVARIANT=1
PROTECTED_DRIFT=0
```

The only GUI regression seen in the focused bridge suite was:

`tests/test_phase6_ui_state_regressions.py::test_real_tk_part_selector_menu_opens_part_and_delete_shares_selector_row`

RUN `35513915340` proved the exact same `assert 1 == 2` on both accepted predecessor and candidate, therefore it is inherited baseline debt and not candidate-only regression.

## Two-axis review

### Standards / repository constraints

PASS.

- Fresh child branch from accepted #442 predecessor.
- Requirement-level RED was established before production deletion.
- Production change is delete-only; no duplicate owner was introduced.
- Validation remains judge-only.
- Temporary A/B workflow was removed after evidence capture.
- DXF/config Git objects are unchanged.

### #443 specification

PASS.

- Runtime call/getattr/facade dispatch for both target builders is zero.
- Both historical builder definitions are absent.
- Settings panel did not gain duplicate symmetry/assembly UI.
- Candidate-only regression count is zero.
- Manufacturing/DXF acceptance is GREEN.
- Protected production drift outside the intended bridge deletion is zero.

## Decision

```text
STANDARDS_REVIEW=PASS
SPEC_REVIEW=PASS
T1_DECISION=GREEN
```
