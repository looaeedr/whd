# Issue #432 / T2 — General part input/display content on the shared host

## Authority
- Parent: #429
- Predecessor: #431 CLOSED/completed
- Exact T2 base: `7ac2c3a1f3743e74750ed148e132be4004e340e5`
- Branch: `refactor/issue432-t2-general-part-shared-host-20260920`

## Preflight
- first fail-closed run: `35497154030` — missing DM7 / entry-convergence evidence
- missing authority was read and persisted
- retry run: `35497204537` — SUCCESS / `KNOWLEDGE_PREFLIGHT_RC=0`

## T2 characterization strategy
T1 may already satisfy T2. Do not manufacture a fake RED.

The characterization therefore keeps production byte-identical to the #431 closing SHA and tests:
1. part mode uses `shared_content_host`;
2. Assembly and Corner Data trees are not mounted in part mode;
3. mode roundtrip preserves active part and existing editor identity;
4. external callback bindings are not replaced;
5. add/delete part semantics keep normal-part presentation on the shared host.

If all gates are GREEN with `fold_designer_bridge.py` byte-identical to predecessor, classify:
`T2_ALREADY_GREEN_AFTER_T1=1` and make no production change.

## Gates
```text
PART_CONTENT_HOST_IS_SHARED_HOST=true
ASSEMBLY_WIDGET_TREE_MOUNTED_IN_PART_MODE=0
CORNER_DATA_WIDGET_TREE_MOUNTED_IN_PART_MODE=0
PART_INPUT_CALLBACK_PARITY=GREEN
PART_DISPLAY_PARITY=GREEN
ADD_DELETE_PART_PARITY=GREEN
PRODUCTION_RUNTIME_EDIT=0
```

## State
```text
STATE=CHARACTERIZATION_PENDING
NEXT_ACTION=Run exact Xvfb T2 characterization. Production must remain unchanged.
```
