---
whd_doc_role: REFERENCE
whd_contract: issue364-phase3-preflight
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue #364 / Phase 3 T0 — Bridge ownership / dependency / timing preflight

## Identity

- Master: #363
- Task: #364 / T0
- Fixed Phase 3 root baseline: 0dd6561f3253d0a17714af316d5e9da90e24058f
- Branch: refactor/issue364-phase3-preflight-20260919
- Nature: read-only characterization / inventory
- Production integration: not required for T0
- Status: **IN_PROGRESS**

## Baseline failure evidence source

The frozen baseline failure node sets are sourced from the already accepted Phase 2 final candidate at the exact same SHA:

~~~text
RUN = 35423014088
candidate SHA = 0dd6561f3253d0a17714af316d5e9da90e24058f
Headless failed nodes = 6
Headless errors = 0
Xvfb failed nodes = 47
Xvfb errors = 0
~~~

This avoids a redundant full Xvfb baseline rerun while preserving an exact accepted evidence source.

## Required machine gate

tools/issue364_phase3_preflight.py must prove:

~~~text
BRIDGE_LINES = 9148
TOP_LEVEL_FUNCTIONS = 304
UNKNOWN_FUNCTIONS = 0
UNKNOWN_CALLBACKS = 0
UNKNOWN_STATE_WRITES = 0
UNKNOWN_CLASS_WIRING = 0
UNMAPPED_EVENT_LOOP_PATHS = 0
IMPLEMENTATION_SOURCE_DRIFT = 0
~~~

It must also emit:

- full top-level function ownership inventory
- self read/write attribution
- Tk/widget references
- callback classification
- class wiring inventory
- transitive dependency closure
- event-loop / scheduler / event-dispatch paths
- accepted baseline failure node sets
- protected-source hashes
- evidence-only git drift classification

## Acceptance

This checkpoint remains IN_PROGRESS until a concrete #364 QA RUN reaches terminal GREEN and its exact RUN/job identity plus machine totals are written back here.

T1 / #365 must not start before #364 is accepted and closed.
