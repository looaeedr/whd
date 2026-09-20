# Issue #433 / T3 — Assembly list mounted into the shared-content host

## Authority
- Parent: #429
- Predecessor: #432 CLOSED/completed
- Exact T3 base: `0cafc232da774019f2b5f1ae818315095f0a56bf`
- Branch: `refactor/issue433-t3-assembly-shared-host-20260920`
- Accepted TESTED_SHA: `4bea390c5c9130abd07f58666a997605ce4da646`

## Knowledge Preflight
- RUN `35497736450`
- result: SUCCESS / `KNOWLEDGE_PREFLIGHT_RC=0`

The dedicated Assembly boundary Skill was also read before characterization:
- `phase6-assembly-view-boundaries`

Its contract confirms that the existing Phase 5 panel owns presentation widgets and ephemeral UI state only; visibility vars, collapse state, multipart physical child registries, Final Scene ports, and Structure Tree shared vars must not be duplicated or replaced by T3.

## Characterization
T1 had already reparented the existing Phase 5 Assembly panel into the one `shared_content_host`. T3 therefore first proved both production files remained byte-identical to predecessor:
- `fold_designer_bridge.py`
- `phase6_assembly_panel.py`

RUN `35497815978`:
```text
6 PASS
1 allowed SKIP
0 FAIL
PRODUCTION_RUNTIME_EDIT=0
ASSEMBLY_PANEL_HOST_IS_SHARED_HOST=true
SEPARATE_ASSEMBLY_REGION=0
ASSEMBLY_WIDGET_TREE_COUNT_WHEN_ACTIVE=1
ASSEMBLY_WIDGET_TREE_COUNT_WHEN_INACTIVE=0
VISIBILITY_SEMANTIC_DRIFT=0
COLLAPSE_SEMANTIC_DRIFT=0
T3_ALREADY_GREEN_AFTER_T1=1
```

The single allowed skip is:
`tests/test_issue376_assembly_collapsible_data.py::test_box_body_physical_piece_rows_are_also_collapsible_when_present`

It is skipped only when the selected family has no resolved BoxBody physical-child rows.

Artifact:
- ID `10600702286`
- SHA256 `cba3e7861d17392b10990d477c2faf74edbcdca20da4c59ad16484b0aa69c3e8`

## Final A/B qualification
RUN `35498132637` — SUCCESS.

Source guard:
```text
PRODUCTION_BRIDGE_EXACT_PREDECESSOR=1
ASSEMBLY_PANEL_MODULE_EXACT_PREDECESSOR=1
PRODUCTION_RUNTIME_EDIT=0
```

Inherited Assembly behavior:
```text
BASELINE_COUNTS {'passed': 5, 'skipped': 1}
CANDIDATE_COUNTS {'passed': 5, 'skipped': 1}
ASSEMBLY_AB_EXACT_OUTCOME_PARITY=1
ASSEMBLY_CANDIDATE_ONLY_FAILURES=0
```

Candidate T3:
```text
4 passed
ASSEMBLY_PANEL_HOST_IS_SHARED_HOST=true
SEPARATE_ASSEMBLY_REGION=0
ASSEMBLY_WIDGET_TREE_COUNT_WHEN_ACTIVE=1
ASSEMBLY_WIDGET_TREE_COUNT_WHEN_INACTIVE=0
VISIBILITY_SEMANTIC_DRIFT=0
COLLAPSE_SEMANTIC_DRIFT=0
T3_ALREADY_GREEN_AFTER_T1=1
```

Accepted:
```text
T3_AB_QUALIFICATION_GREEN=1
BASE_SHA=0cafc232da774019f2b5f1ae818315095f0a56bf
TESTED_SHA=4bea390c5c9130abd07f58666a997605ce4da646
```

A/B artifact:
- ID `10601022298`
- SHA256 `eb6e5b217d5d25d7f32774ed6394d33069537bfde9dc85426bac36af7644ded1`

## Accepted conclusion
T3 is **already GREEN after T1**. The existing Phase 5 Assembly panel is already the only Assembly content tree mounted through `shared_content_host`; its visibility and collapse semantics remain unchanged.

No production change is required or allowed for T3.

The closing commit may only:
- update this checkpoint / journal;
- remove temporary #433 QA workflows.

No production or T3 test-contract drift is allowed after TESTED_SHA.

## State
```text
STATE=ACCEPTED
TESTED_SHA=4bea390c5c9130abd07f58666a997605ce4da646
FINAL_AB_RUN=35498132637
PRODUCTION_RUNTIME_EDIT=0
NEXT_ACTION=#434 / T4
```
