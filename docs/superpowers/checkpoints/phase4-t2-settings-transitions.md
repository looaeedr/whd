# Phase 4 T2 — Pure Settings transition kernel

## Identity
- Master: #388
- Task: #391 / T2
- Fixed Phase 4 root: `fdcc9b0a08f7ed19f5c17984f2793c16d6f49be4`
- Predecessor T1 accepted candidate: `a1b20315d9c7efcac07ceaa994cb7b21b314292f`
- Branch: `refactor/issue391-phase4-t2-settings-transitions-20260920`

## RED
Clean intended RED RUN: `35461682442` / job `105946559131`
- **3 failed**
- missing `phase6_settings_transitions.py`
- controller had no transition-kernel import/delegation
- marker: `ISSUE391_T2_EXPECTED_RED=1`

## GREEN
Final GREEN RUN: `35461996285` / job `105947393770`
- T2 kernel contracts: **3 passed**
- existing Settings transition regressions: **22 passed / 2 skipped**
- task-scoped predecessor↔candidate semantic JSON: exact match
- `ISSUE391_T2_KERNEL_GREEN=1`
- `ISSUE391_T2_EXISTING_SETTINGS_GREEN=1`
- `ISSUE391_T2_SEMANTIC_AB_DELTA=0`
- `SETTINGS_TRANSITION_SELF_REFS=0`
- `SETTINGS_TRANSITION_TK_REFS=0`
- `SETTINGS_TRANSITION_REVERSE_IMPORTS=0`
- `ISSUE391_T2_SCOPE_GREEN=1`
- `ISSUE391_T2_PROTECTED_DRIFT=0`

An earlier GREEN RUN `35461919622` reached kernel **3 PASS** and existing regressions **22 PASS / 2 SKIP**, but its A/B harness used an incorrect worktree Python path and failed before comparison. No implementation remediation was made for that harness-only failure.

## Implementation
Added `phase6_settings_transitions.py` as the pure semantic kernel for:
- normalization / commit calculation
- box-structure transitions
- EndCap FW / bottom-wrap / edge relation
- corner normalization / pair / type / mode / parameters
- assembly intent
- external sync/model planning
- symmetry/default payload
- width reconciliation
- family/model transition calculation

`Phase6SettingsTransactionController` now delegates semantic calculation to the kernel while retaining:
- mutable compatibility state application
- workspace commits / dirty effects
- debounce state
- transaction-id state

Those remaining effect/rebinding responsibilities are intentionally T3 scope.

## Protected scope
Unchanged vs T1 predecessor:
- `fold_designer_bridge.py`
- `phase6_settings_panel.py`
- Workspace / Project / Registry / 2D owners
- Phase 2 manufacturing owners/contracts
- `config.ini`
- cabinet-family policy files

Next: #392 T3 Settings orchestration/effects isolation + bridge rebinding removal.
