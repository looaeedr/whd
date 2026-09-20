# Issue #431 / T1 — Shared-content host & mutually-exclusive mode controller

## Authority
- Parent: #429
- Predecessor: #430 CLOSED/completed
- Exact T1 base: `95ab91c900e9a531ce0fec25a698123116392cc2`
- Branch: `refactor/issue431-t1-shared-content-host-20260920`

## Preflight / RED
- Knowledge Preflight: RUN `35495987364` — SUCCESS
- RED: RUN `35496092853`, HEAD `7d4c569c5936924120ec0b520f7afd61bbd07fb2`
- RED result: **5 PASS / 3 intended FAIL / 0 SKIP**

The three intended REDs were:
1. inherited #430 direct-host-count contract;
2. dedicated shared-content host missing;
3. shared-content controller missing.

## Minimal GREEN
Production change SHA:
`9b9c4b489f5181883dd8f47bd98aa5c5bd66bf6a`

Only the presentation ownership seam changed:
- one `shared_content_host` is created directly under `self.left`;
- existing normal-part editor, Assembly panel, and Corner Data panel are children of that host;
- `_phase6_mount_shared_content()` is the only direct mode-content pack/pack_forget owner;
- existing `designer_workspace.active_part`, `_phase6_3d_display_mode`, visibility state, Corner Data adapter state, geometry, persistence, and callbacks remain authoritative.

## Stale #384 contract migration
Initial A/B RUN `35496316468` found one candidate-only failure:
`tests/test_issue384_assembly_only_function_presentation.py::test_normal_and_assembly_content_share_same_left_content_owner`

That old test asserted both surfaces were direct children of `app.left`, which conflicts with #429/#431. It was updated test-only to assert:
- `shared_content_host.master is app.left`;
- `fold_editor_host.master is shared_content_host`;
- `assembly_parts_panel.master is shared_content_host`.

The production blob did not change. New exact TESTED_SHA:
`20e10d7cbcf7d6066bb357701f2f156789fc9277`

## Focused revalidation
RUN `35496772616`, exact TESTED_SHA `20e10d7c…`:
```text
11 PASS
0 FAIL
0 SKIP
PRODUCTION_BLOB_UNCHANGED_SINCE_FOCUSED_GREEN=1
SHARED_CONTENT_HOST_COUNT=1
ACTIVE_SHARED_CONTENT_MODE_COUNT=1
SEPARATE_ASSEMBLY_REGION=0
SEPARATE_CORNER_DATA_REGION=0
MODE_SWITCH_CREATES_STATE_AUTHORITY=0
```

Artifact:
- ID `10601600599`
- SHA256 `3fcc2efbce1bc36ea888e9d16c7f97e6c38f62ea576779110d45f2b550e83ed0`

## Final A/B qualification
RUN `35496883180` — SUCCESS.

Source guard:
```text
SHARED_CONTENT_HOST_COUNT=1
ACTIVE_SHARED_CONTENT_MODE_COUNT=1
SEPARATE_ASSEMBLY_REGION=0
SEPARATE_CORNER_DATA_REGION=0
MODE_SWITCH_CREATES_STATE_AUTHORITY=0
```

UI A/B:
```text
UI_AB_EXACT_OUTCOME_PARITY=1
UI_CANDIDATE_ONLY_FAILURES=0
UI_INHERITED_FAILURE_COUNT=6
UI_INHERITED_SKIP_COUNT=1
```

The six UI failures and one skip are exact predecessor-baseline debt; candidate introduced no additional outcome drift.

Manufacturing / DXF / persistence A/B:
```text
MFG_BASELINE_COUNTS {'passed': 21}
MFG_CANDIDATE_COUNTS {'passed': 21}
PART_DXF_PERSISTENCE_AB_EXACT_OUTCOME_PARITY=1
CONFIG_INVARIANT=1
```

Artifacts:
- UI A/B: ID `10600871040`, SHA256 `2e423eeb4e54ac6ef9702705487f08655134782cdf918d94c4ad2a2526ef2444`
- manufacturing A/B: ID `10600579226`, SHA256 `b4210b697eaade116b29a8d51c1635f87820edd4796fae6fd33f96d3f433d28c`

## Accepted conclusion
T1 is accepted at TESTED_SHA `20e10d7cbcf7d6066bb357701f2f156789fc9277`.

The final closing commit may update only this checkpoint/journal and remove temporary #431 QA workflows. No production or test-contract drift after TESTED_SHA is allowed.

## State
```text
STATE=ACCEPTED
TESTED_SHA=20e10d7cbcf7d6066bb357701f2f156789fc9277
FINAL_AB_RUN=35496883180
NEXT_ACTION=#432 / T2
```
