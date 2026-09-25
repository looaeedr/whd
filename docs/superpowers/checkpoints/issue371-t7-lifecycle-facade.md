---
whd_doc_role: REFERENCE
whd_contract: issue371-t7-lifecycle-facade
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #371 / Phase 3 T7 — Update-Intent / Lifecycle Wiring + Bridge Facade Compression

## Identity

- Master: #363
- Task: #371 / T7
- Fixed T7 baseline: `81dbd6f140b6bac8c9ba44f947919d341997ba56`
- Branch: `refactor/issue371-phase3-lifecycle-facade-20260919`
- Accepted behavior/test SHA: `773d527e54da0e5f6924279299d54ffc5cf3e4e3`
- Status: **ACCEPTED**

## Ownership Decision

No new update coordinator was created.

T7 reuses the existing canonical application scheduler:

- `gui_modules/application/command_router.py::_Phase6UpdateScheduler`

It now accepts an injected executor and owns Fold Designer update-intent routing while preserving the existing main-GUI scheduling path.

Extracted/centralized application responsibilities include:

- update-intent submission / flush / coalescing
- 75 ms trailing debounce
- full-update versus display-only routing
- live-publish trigger sequencing
- preview-aware render sequencing
- settings-delta transaction routing
- keyboard binding installation
- Fold Designer factory injection into lifecycle
- compatibility class-wiring installation

## Bridge Compression

Starting T7 baseline:

- `fold_designer_bridge.py`: 9,076 lines
- direct `Phase6FoldDesignerApp.attr = ...` class wiring: 62 assignments

Accepted T7 tree:

- `fold_designer_bridge.py`: 9,051 lines
- direct class wiring assignments: **0**
- class compatibility wiring is installed through one application-owned `install_fold_designer_bridge_facade(...)` composition call
- `gui_modules/application/lifecycle.py` has **0** reverse imports of `fold_designer_bridge`

Residual T7 bridge functions are compatibility/composition/view-binding delegates; T7 update/keyboard facades contain no control-flow loops or domain branches.

## Characterization RED

```text
RUN = 35444785358
result = SUCCESS
T7_BASELINE = 81dbd6f140b6bac8c9ba44f947919d341997ba56
```

The intended RED proved:

- canonical scheduler lacked Fold Designer executor injection
- bridge still owned update/keyboard orchestration
- lifecycle reverse-imported the bridge
- direct class monkey-patch wiring remained in the bridge

## Focused GREEN

Final focused GREEN:

```text
RUN = 35445153741
result = SUCCESS
```

Results:

- T7 ownership / ordering contracts: **32 PASS**
- transaction + Phase 2 manufacturing purity gates: **44 PASS**
- real-Tk bridge lifecycle / 3D / current UI carry-forward: **80 PASS / 1 SKIP**

During GREEN, two Phase 2 tests were updated only to recognize the semantically equivalent application facade installer wiring. Their manufacturing assertions were preserved; no manufacturing purity condition was removed.

## Task-Scoped A/B

Final authoritative A/B:

```text
RUN = 35445320804
result = SUCCESS
baseline = 81dbd6f140b6bac8c9ba44f947919d341997ba56
tested = 773d527e54da0e5f6924279299d54ffc5cf3e4e3
```

Classifier:

```text
Headless: 80 nodes / 0 -> 0 FAIL
Xvfb: 81 nodes / 0 -> 0 FAIL
NEW_RELEVANT_HEADLESS = []
NEW_RELEVANT_XVFB = []
NEW_RELEVANT_ERRORS = []
PROTECTED_DRIFT = 0
UNEXPLAINED_EVENT_ORDER_DELTA = 0
UNEXPLAINED_TEST_OUTCOME_DELTA = 0
ISSUE371_T7_AB_DECISION = GREEN
```

Event-order parity was explicitly probed:

```text
geometry:
  baseline  = publish -> full
  candidate = publish -> full

display/camera:
  baseline  = publish -> committed
  candidate = publish -> committed
```

## Preserved Hard Boundaries

- Phase 2 manufacturing solver ownership was not reopened.
- Domain/service modules do not reverse-import `fold_designer_bridge`.
- settings/corner/structure authority remains in the accepted T2 controller.
- project/persistence remains with the accepted T3 owners.
- registry/diagnostics remains with the accepted T4 owner.
- 2D view ownership remains with the accepted T5 adapter.
- 3D view ownership remains with the accepted T6 adapter.
- config.ini and DXF protected digests remained unchanged.

## QA Cleanup

Temporary T7 RED/GREEN/A-B workflows and the A/B classifier were deleted after acceptance. Durable characterization and ownership tests remain.

## Production Acceptance

The cleaned T7 branch may integrate only via non-force fast-forward from the fixed T7 baseline.

After production readback is identical, the integrated production SHA is the **Phase 3 final candidate** used by T8 cumulative root-baseline A/B.
