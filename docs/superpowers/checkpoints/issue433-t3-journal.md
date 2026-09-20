# Issue #433 / T3 — Assembly list mounted into the shared-content host

## Authority
- Parent: #429
- Predecessor: #432 CLOSED/completed
- Exact T3 base: `0cafc232da774019f2b5f1ae818315095f0a56bf`
- Branch: `refactor/issue433-t3-assembly-shared-host-20260920`

## Knowledge Preflight
- RUN `35497736450`
- result: SUCCESS

## T3 characterization strategy
T1 already reparented the existing Phase 5 Assembly panel into `shared_content_host`. T3 must not create another panel or state owner.

Characterization therefore keeps both production files byte-identical to predecessor:
- `fold_designer_bridge.py`
- `phase6_assembly_panel.py`

The behavior matrix verifies:
1. the existing `Phase6AssemblyPanel` owner remains the one Assembly content tree;
2. its host is a child of `shared_content_host`;
3. exactly one Assembly tree is mounted in assembly mode and zero when inactive;
4. Structure Tree visibility uses the exact panel-owned Tk var;
5. visibility value/identity survive mode roundtrip;
6. collapsible detail state/data survive mode roundtrip.

Existing #376 collapse regressions are also run unchanged.

If all gates are GREEN with production byte-identical to predecessor:
`T3_ALREADY_GREEN_AFTER_T1=1`; no production change is needed.

## Gates
```text
ASSEMBLY_PANEL_HOST_IS_SHARED_HOST=true
SEPARATE_ASSEMBLY_REGION=0
ASSEMBLY_WIDGET_TREE_COUNT_WHEN_ACTIVE=1
ASSEMBLY_WIDGET_TREE_COUNT_WHEN_INACTIVE=0
VISIBILITY_SEMANTIC_DRIFT=0
COLLAPSE_SEMANTIC_DRIFT=0
PRODUCTION_RUNTIME_EDIT=0
```

## State
```text
STATE=CHARACTERIZATION_PENDING
NEXT_ACTION=Run exact Xvfb T3 characterization. Production must remain unchanged.
```
