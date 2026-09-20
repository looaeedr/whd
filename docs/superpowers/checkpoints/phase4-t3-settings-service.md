# Phase 4 T3 — Settings orchestration/effects isolation

## Identity
- Master: #388
- Task: #392 / T3
- Fixed Phase 4 root: `fdcc9b0a08f7ed19f5c17984f2793c16d6f49be4`
- Predecessor T2 accepted candidate: `080385b15e82e0efb8ac13430e3fb999d5589de9`
- Final GREEN tested HEAD: `c42e85fc62a3d9a403ad5c03c31ced22ae4bc40a`

## RED
Intended RED RUN: `35462175350` / job `105947877463`
- 5 FAIL
- `phase6_settings_service.py` missing
- bridge still called `controller.bind_state(...)`
- scalar mirror writes remained
- command router still required `sync_mirrors`
- runtime Settings map identity was not stable
- marker: `ISSUE392_T3_EXPECTED_RED=1`

## GREEN
Final GREEN RUN: `35469515011`
- Headless job `105967798332`: SUCCESS
- Xvfb job `105967798472`: SUCCESS

Headless:
- T3 ownership contracts: **5 PASS**
- Settings focused regressions: **26 PASS / 2 SKIP**
- predecessor↔candidate semantic A/B: exact match
- `ISSUE392_T3_SEMANTIC_AB_DELTA=0`
- `ISSUE392_T3_BIND_STATE_CALLS=0`
- `ISSUE392_T3_SCALAR_MIRROR_WRITES=0`
- `ISSUE392_T3_REVERSE_IMPORTS=0`
- `ISSUE392_T3_SCOPE_GREEN=1`
- `ISSUE392_T3_PROTECTED_DRIFT=0`

Xvfb:
- Settings UI/runtime regressions: **20 PASS**
- `ISSUE392_T3_XVFB_GREEN=1`

## Implementation
Added `phase6_settings_service.py` owning:
- pending/staged orchestration state
- debounce token ownership
- external revision ordering
- active transaction scope

Controller remains compatibility/semantic-state application facade and delegates orchestration state to the service.

Bridge:
- no `controller.bind_state(...)`
- no `_phase6_sync_settings_transaction_compatibility_mirrors`
- no writes to compatibility scalar mirrors
- stable mapping identity for Settings runtime state
- read-through compatibility properties for legacy scalar readers

Command router:
- no `sync_mirrors` callback

## Recovery notes
Earlier GREEN runs:
- `35469070181`: one stale structural gate + Xvfb runner missing matplotlib
- `35469225349`: structural gate fixed; remaining T2 structural expectation updated for T3 orchestration seam; Xvfb still missing matplotlib
Both were classified and repaired without changing product semantics.

Next: #393 T4 typed Final Scene dependency/runtime contracts.
