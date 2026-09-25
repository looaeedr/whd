# Issue #434 / T4 — Corner Data mounted into the shared-content host

## Authority
- Parent: #429
- Predecessor: #433 CLOSED/completed
- Exact T4 base: `bbd499786cbebc1b5e68ff032f2591cc308060cd`
- Branch: `refactor/issue434-t4-corner-data-shared-host-20260920`
- Accepted TESTED_SHA: `9e6ad347dd99a52e657a02f5107bd64f11852063`

## Knowledge Preflight
- RUN `35498340890`
- result: SUCCESS / `KNOWLEDGE_PREFLIGHT_RC=0`

## Ownership readback
Production already has the T4 ownership model:
- `corner_data_panel` is lazily constructed directly under `shared_content_host`;
- `_phase6_mount_shared_content(..., "corner_data")` owns presentation mount/unmount;
- `Phase6CornerDataViewAdapter._selected_part_key` owns Corner Data selection;
- `_phase6_corner_data_selected_part_key` is compatibility mirror only;
- workspace `available_parts` remains topology authority;
- unfold/render data comes from authoritative manufacturing render-data sinks;
- no legacy Notebook or independent Corner Data window is used.

## Characterization
First RUN `35498495529`:
- production exact predecessor: PASS
- inherited Corner Data tests: **21 PASS**
- 2 new #434 tests failed because the test harness asked a directly-constructed Fold Designer to render an unfold without the main-GUI final-scene provider.

This was test overreach, not a production defect. The new tests were corrected to use:
- `refresh_view=False` for pure selection-owner assertions;
- the direct shared-content mount seam for ownership/mount roundtrips;
- panel refresh while Corner Data render is inactive.

No production file changed.

Accepted characterization RUN `35498592796`, JOB `106046113503`:
```text
23 PASS
0 FAIL
0 SKIP
PRODUCTION_RUNTIME_EDIT=0
CORNER_DATA_HOST_IS_SHARED_HOST=true
SEPARATE_CORNER_DATA_REGION=0
CORNER_DATA_WIDGET_TREE_COUNT_WHEN_ACTIVE=1
CORNER_DATA_WIDGET_TREE_COUNT_WHEN_INACTIVE=0
CORNER_DATA_BEHAVIOR_DRIFT=0
CORNER_DATA_STATE_AUTHORITY_DUPLICATION=0
T4_ALREADY_GREEN_AFTER_T1=1
```

Artifact:
- ID `10601423804`
- SHA256 `de9aa953c55fe25964881578bba0b0e0b0ae6a11021b442ac364077bcace4091`

## Final A/B qualification
RUN `35498676434` — SUCCESS.

Source guard:
```text
PRODUCTION_BRIDGE_EXACT_PREDECESSOR=1
CORNER_DATA_ADAPTER_EXACT_PREDECESSOR=1
PRODUCTION_RUNTIME_EDIT=0
```

Inherited Corner Data A/B:
```text
BASELINE_COUNTS {'passed': 19}
CANDIDATE_COUNTS {'passed': 19}
CORNER_DATA_AB_EXACT_OUTCOME_PARITY=1
CORNER_DATA_CANDIDATE_ONLY_FAILURES=0
CORNER_DATA_BASELINE=19_PASS
CORNER_DATA_CANDIDATE=19_PASS
```

Candidate T4:
```text
4 passed
CORNER_DATA_HOST_IS_SHARED_HOST=true
SEPARATE_CORNER_DATA_REGION=0
CORNER_DATA_WIDGET_TREE_COUNT_WHEN_ACTIVE=1
CORNER_DATA_WIDGET_TREE_COUNT_WHEN_INACTIVE=0
CORNER_DATA_BEHAVIOR_DRIFT=0
CORNER_DATA_STATE_AUTHORITY_DUPLICATION=0
T4_ALREADY_GREEN_AFTER_T1=1
```

Accepted:
```text
T4_AB_QUALIFICATION_GREEN=1
BASE_SHA=bbd499786cbebc1b5e68ff032f2591cc308060cd
TESTED_SHA=9e6ad347dd99a52e657a02f5107bd64f11852063
```

A/B artifact:
- ID `10601062871`
- SHA256 `357687c67fd114b6d9cbb178af5c3ff18ad6267d1002eb0a0d3e7d96355d0322`

## Accepted conclusion
T4 is **already GREEN after T1**. The existing Corner Data content is already the sole Corner Data content tree mounted through the one `shared_content_host`, with adapter/state/callback semantics preserved.

No production change is required or allowed for T4.

The closing commit may only:
- update this checkpoint / journal;
- remove temporary #434 QA workflows.

No production or T4 test-contract drift is allowed after TESTED_SHA.

## State
```text
STATE=ACCEPTED
TESTED_SHA=9e6ad347dd99a52e657a02f5107bd64f11852063
FINAL_AB_RUN=35498676434
PRODUCTION_RUNTIME_EDIT=0
NEXT_ACTION=#435 / T5
```
