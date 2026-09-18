# Issue #351 T6 — compatibility / zero-reverse-import acceptance

## Identity
- Master: #344
- Task: #351 / T6
- Predecessor: #350 accepted HEAD `87318c43f40905918fdd8c44973e4ed850b23461`
- Branch: `refactor/issue351-compatibility-zero-reverse-import-20260918`
- Gate RUN: `35362981062`
- Job: `105658518816`
- Result: **SUCCESS**

## Machine gate
```text
PASS moved_owner_count=22
PASS reverse_bridge_imports=0
PASS class_wiring=4 binder_callbacks=4
PASS instance_shadowing=0
PASS canonical_part_navigation_name=1
```

Runtime/static compatibility suite:
- **7 PASS / 0 FAIL**

## Durable gates
- `tools/issue351_t6_compatibility_gate.py`
- `tests/test_issue351_t6_compatibility_gate.py`

The gate proves:
- every Phase 1 moved symbol has one canonical owner in `phase6_manufacturing_geometry.py`;
- bridge defines none of the moved implementations;
- bridge compatibility re-exports resolve to the exact same objects;
- manufacturing owner imports `fold_designer_bridge` zero times;
- four bridge-owned self-coupled helpers are class-wired;
- the four callbacks are also injected for accepted lightweight legacy facade callers;
- binder execution occurs only after callback functions/wiring exist;
- no instance attribute shadows the four callback names;
- manufacturing resolver uses the canonical part-navigation identity.

No manufacturing semantics changed in T6.

Next: #352 / T7 final A/B acceptance and production integration.
