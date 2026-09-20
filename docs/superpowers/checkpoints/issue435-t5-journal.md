# Issue #435 / T5 — Switch lifecycle, state preservation & duplicate-tree guards

## Authority
- Parent: #429
- Predecessor: #434 CLOSED/completed
- Exact T5 base: `07a5fe36880d1548c9f42f2f6d071f46a9ac062f`
- Branch: `refactor/issue435-t5-switch-lifecycle-guards-20260920`

## Knowledge Preflight
- RUN `35498891860`
- result: SUCCESS / `KNOWLEDGE_PREFLIGHT_RC=0`

## Characterization plan
Keep production byte-identical to predecessor and run the full lifecycle matrix:
- repeated part → assembly → corner_data → part cycles;
- surface/owner identity and mapped-tree count;
- refresh stale-widget disposal;
- event-binding and callback multiplicity;
- export → reopen state parity;
- dynamic add/delete;
- receiving-family late BoxBody child projection (#119);
- collapse state (#376);
- serialized persistence parity (#41);
- mousewheel safety (#378 + current Phase5 owner wrapper).

## #378 inherited-debt hypothesis
The current runtime binds Assembly scrolling through the long-lived `Phase6AssemblyPanel` owner. Its `scroll()` already handles nonnumeric `event.num` safely.

The legacy #378 test constructs only `SimpleNamespace(assembly_parts_canvas=...)` and omits `_phase6_assembly_panel_owner`. The bridge compatibility wrapper therefore returns `"break"` without scrolling.

Characterization must prove whether the **only** REDs are those four stale #378 owner-contract assertions. If so, migrate #378 test-only to the accepted Phase5 owner seam; do not add a second runtime scroll authority.

## T5 gates
```text
PERMANENT_HIDDEN_SECOND_HOST=0
DUPLICATE_WIDGET_TREE=0
DUPLICATE_EVENT_BINDING=0
CALLBACK_MULTIPLICATION=0
STALE_WIDGET_REFERENCE=0
STATE_PRESERVATION_PARITY=GREEN
MOUSEWHEEL_EXCEPTION=0
```

## State
```text
STATE=CHARACTERIZATION_RED_PENDING
PRODUCTION_RUNTIME_EDIT=0
NEXT_ACTION=Run lifecycle matrix with legacy #378 unchanged; require exact intended RED classification.
```
